"""Build the pilot annotation spreadsheet (.xlsx) for import into Google Sheets.

Every allowed value comes from taxonomy.yaml: the four attributes from `load_taxonomy()`, the
annotation-only columns from `load_annotation_fields()`. Texts are masked (`privacy.mask`) and each
one must pass the last barrier (`privacy.assert_masked`) or nothing is written.

Conditional formatting only warns, in yellow, and never marks a row as correct. The strict reader
(`annotation.reader`) is the final check.

openpyxl is imported here and nowhere the API can reach (tests/unit/test_annotation_isolation.py).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from govbr_classifier.annotation.fields import load_annotation_fields
from govbr_classifier.annotation.pilot import TRUNCATED_LENGTH
from govbr_classifier.privacy import MARKERS, assert_masked, capitalized_mid_sentence, mask
from govbr_classifier.settings import PROJECT_ROOT
from govbr_classifier.taxonomy import load_taxonomy

RUBRIC_PATH = PROJECT_ROOT / "docs" / "rubric" / "annotation_rubric.pt.md"
SHEET_PATH = PROJECT_ROOT / "data" / "pilot" / "pilot_annotation.xlsx"
BLIND_PATH = PROJECT_ROOT / "data" / "pilot" / "pilot_annotation_blind.xlsx"

PROTECTED = ("item_id", "texto", "cortado")
DATETIME_FORMAT = "yyyy-mm-dd hh:mm:ss"
SESSION_COLUMNS = ("data", "inicio", "fim", "itens_anotados", "pausas_min", "observacoes")
SESSION_ROWS = 30
YELLOW = PatternFill(start_color="FFF2A8", end_color="FFF2A8", fill_type="solid")


def tema_columns() -> list[str]:
    """One checkbox column per tema value, in taxonomy order."""
    return [f"tema_{label}" for label in load_taxonomy().attributes["tema"].labels]


def annotation_columns() -> list[str]:
    """The `anotacao` header, in order. The strict reader expects exactly this."""
    return [
        "item_id",
        "texto",
        "cortado",
        "ood_manual",
        *tema_columns(),
        "tipo",
        "bloqueio",
        "acionabilidade",
        "obrigatoriedade",
        "duvida",
        "nota_duvida",
        "hora_fim",
    ]


def list_values() -> dict[str, tuple[str, ...]]:
    """Columns with a closed list, and their values, all read from taxonomy.yaml."""
    attributes = load_taxonomy().attributes
    fields = load_annotation_fields()
    return {
        "ood_manual": fields.ood_manual,
        "tipo": attributes["tipo"].labels,
        "bloqueio": attributes["bloqueio"].labels,
        "acionabilidade": attributes["acionabilidade"].labels,
        "duvida": fields.duvida,
    }


@dataclass(frozen=True)
class MaskReport:
    """What the mask did on the pilot texts, without any text."""

    items_masked: dict[str, int]
    name_item_ids: list[str]


def build_items(link: pd.DataFrame, texts: pd.Series) -> tuple[pd.DataFrame, MaskReport]:
    """Return item_id, masked texto and cortado per item, plus counts.

    `link` is data/pilot/link.csv; `texts` maps review_id to the raw review text. Raises
    `PersonalDataLeakError` (naming the item only) if any masked text fails the last barrier.
    """
    rows = []
    items_masked = dict.fromkeys(MARKERS, 0)
    flagged = []
    for item in link.sort_values("item_id").itertuples(index=False):
        raw = str(texts[item.review_id])
        masked = mask(raw)
        assert_masked(masked.text, str(item.item_id))
        for kind, count in masked.counts.items():
            items_masked[kind] += int(count > 0)
        if capitalized_mid_sentence(masked.text):
            flagged.append(str(item.item_id))
        rows.append(
            {
                "item_id": item.item_id,
                "texto": masked.text,
                "cortado": "sim" if int(item.original_length) == TRUNCATED_LENGTH else "nao",
            }
        )
    return pd.DataFrame(rows), MaskReport(items_masked=items_masked, name_item_ids=flagged)


def _letters(columns: Sequence[str]) -> dict[str, str]:
    return {name: get_column_letter(i) for i, name in enumerate(columns, start=1)}


def _warning_formulas(col: dict[str, str]) -> dict[str, str]:
    """Row-level warnings, written for row 2 and applied to every row."""
    tema = [col[name] for name in tema_columns()]
    tema_range = f"${tema[0]}2:${tema[-1]}2"
    checked = f"COUNTIF({tema_range},TRUE)"
    exclusive = "+".join(
        f"(${col[f'tema_{label}']}2=TRUE)" for label in load_taxonomy().attributes["tema"].exclusive
    )
    ood, tipo, bloq, acion = (
        f"${col[c]}2" for c in ("ood_manual", "tipo", "bloqueio", "acionabilidade")
    )
    obrig, nota = f"${col['obrigatoriedade']}2", f"${col['nota_duvida']}2"
    nenhum, outro = f"${col['tema_nenhum']}2", f"${col['tema_outro']}2"
    anything = f'OR({checked}>0,{tipo}<>"",{bloq}<>"",{acion}<>"",{obrig}=TRUE)'
    return {
        "ood other than nao with attributes": f'AND({ood}<>"",{ood}<>"nao",{anything})',
        "ood nao with an empty attribute": (
            f'AND({ood}="nao",OR({checked}=0,{tipo}="",{bloq}="",{acion}=""))'
        ),
        "ood empty with something filled": f'AND({ood}="",{anything})',
        "exclusive tema combined": f"AND(({exclusive})>=1,{checked}>=2)",
        "tipo nenhum needs tema nenhum, bloqueio nao, acionabilidade nao": (
            f'AND({tipo}="nenhum",OR({nenhum}<>TRUE,{bloq}<>"nao",{acion}<>"nao"))'
        ),
        "tema nenhum needs tipo nenhum or pedido_funcionalidade": (
            f'AND({nenhum}=TRUE,{tipo}<>"",{tipo}<>"nenhum",{tipo}<>"pedido_funcionalidade")'
        ),
        "tema outro needs nota_duvida": f'AND({outro}=TRUE,{nota}="")',
    }


def _annotation_sheet(ws: Worksheet, items: pd.DataFrame) -> None:
    columns = annotation_columns()
    col = _letters(columns)
    last_row = len(items) + 1
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    checkboxes = {*tema_columns(), "obrigatoriedade"}
    for item in items.itertuples(index=False):
        row_values: list[object] = []
        for name in columns:
            if name in PROTECTED:
                row_values.append(getattr(item, name))
            elif name in checkboxes:
                row_values.append(False)
            else:
                row_values.append(None)
        ws.append(row_values)

    for row in ws.iter_rows(min_row=2, max_row=last_row):
        for cell, name in zip(row, columns, strict=True):
            cell.protection = Protection(locked=name in PROTECTED)
            cell.alignment = Alignment(wrap_text=name in ("texto", "nota_duvida"), vertical="top")
            if name == "hora_fim":
                cell.number_format = DATETIME_FORMAT
    ws.protection.sheet = True
    ws.protection.formatRows = False
    ws.protection.formatColumns = False
    ws.protection.sort = False
    ws.protection.autoFilter = False

    for name, values in list_values().items():
        validation = DataValidation(
            type="list",
            formula1='"' + ",".join(values) + '"',
            allow_blank=True,
            showErrorMessage=True,
            errorStyle="stop",
            errorTitle="Valor fora da lista",
            error=f"Use um valor da lista de {name}, ou deixe em branco.",
        )
        validation.add(f"{col[name]}2:{col[name]}{last_row}")
        ws.add_data_validation(validation)
    moment = DataValidation(
        type="date",
        operator="greaterThan",
        formula1="DATE(2026,1,1)",
        allow_blank=True,
        showErrorMessage=True,
        errorStyle="stop",
        errorTitle="Data e hora",
        error="Use Cmd+Option+Shift+; para gravar a data e a hora atuais.",
    )
    moment.add(f"{col['hora_fim']}2:{col['hora_fim']}{last_row}")
    ws.add_data_validation(moment)

    whole_rows = f"A2:{get_column_letter(len(columns))}{last_row}"
    for formula in _warning_formulas(col).values():
        ws.conditional_formatting.add(whole_rows, FormulaRule(formula=[formula], fill=YELLOW))

    ws.freeze_panes = "C2"
    widths = {"item_id": 9, "texto": 60, "cortado": 9, "ood_manual": 17, "nota_duvida": 40}
    for name, letter in col.items():
        ws.column_dimensions[letter].width = widths.get(name, 20 if "_" in name else 16)


def _rubric_sheet(ws: Worksheet, rubric: str) -> None:
    ws.column_dimensions["A"].width = 120
    for line in rubric.splitlines():
        ws.append([line])
        ws.cell(ws.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
        if line.startswith("#"):
            ws.cell(ws.max_row, 1).font = Font(bold=True)
    ws.protection.sheet = True


def _sessions_sheet(ws: Worksheet) -> None:
    ws.append(list(SESSION_COLUMNS))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    formats = {"data": "yyyy-mm-dd", "inicio": "hh:mm:ss", "fim": "hh:mm:ss"}
    for row in range(2, SESSION_ROWS + 2):
        for index, name in enumerate(SESSION_COLUMNS, start=1):
            cell = ws.cell(row, index)
            cell.number_format = formats.get(name, "General")
    for index, name in enumerate(SESSION_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(index)].width = 40 if name == "observacoes" else 15
    ws.freeze_panes = "A2"


README_LINES = (
    "Leia-me: piloto de anotação",
    "",
    "O que é: 50 avaliações do Google Play para medir a sua velocidade e achar onde a rubrica gera "
    "dúvida. Não é o conjunto de teste. Os mesmos itens serão reanotados pelo menos três semanas "
    "depois.",
    "",
    "Como preencher a aba anotacao, item por item:",
    "1. Decida ood_manual. Se for nao, preencha tema (uma ou mais caixas), tipo, bloqueio e "
    "acionabilidade. Se for outro valor, deixe tudo vazio, inclusive a caixa obrigatoriedade.",
    "2. Marque obrigatoriedade quando o texto diz que a pessoa é obrigada a usar o app ou um "
    "mecanismo dele. Não é rótulo.",
    "3. duvida: uma categoria só, a principal, explicada em nota_duvida. Em branco quando não há "
    "dúvida. O assunto do tema outro também vai em nota_duvida.",
    "4. Ao terminar o item, clique em hora_fim e aperte Cmd+Option+Shift+; (grava data e hora). "
    "Não use Cmd+Shift+;, que grava só a hora.",
    "",
    "O que não mexer: item_id, texto e cortado; o cabeçalho; os nomes das abas. O leitor estrito "
    "recusa a planilha se o cabeçalho mudar.",
    "",
    "Pode ordenar e filtrar à vontade: o tempo por item vem de hora_fim e da aba sessoes, não da "
    "posição da linha.",
    "",
    "Aba sessoes: uma linha por sessão de anotação, com data, hora de início e de fim, itens "
    "anotados, minutos de pausa e observações. Uma sessão não deve passar da meia-noite.",
    "",
    "Amarelo é só aviso de combinação suspeita, nunca de acerto. Não existe verde. A verificação "
    "definitiva é o leitor estrito, rodado depois.",
    "",
    "Os textos estão mascarados: [CPF], [TELEFONE], [EMAIL], [PERFIL], [NOME], [NUMERO].",
)


def _readme_sheet(ws: Worksheet, blind: bool) -> None:
    ws.column_dimensions["A"].width = 110
    lines = list(README_LINES)
    if blind:
        lines[0] += " (cópia cega para reanotação: não abra a primeira passada)"
    for line in lines:
        ws.append([line])
        ws.cell(ws.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(1, 1).font = Font(bold=True, size=14)
    ws.protection.sheet = True


def write_workbook(items: pd.DataFrame, path: Path, rubric: str, blind: bool = False) -> None:
    """Write the four sheets. Refuses to overwrite: an existing file may hold annotations."""
    if path.exists():
        raise FileExistsError(f"{path} exists; it may hold annotations. Move it away first.")
    workbook = Workbook()
    annotation = workbook.active
    assert annotation is not None
    annotation.title = "anotacao"
    _annotation_sheet(annotation, items)
    _rubric_sheet(workbook.create_sheet("rubrica"), rubric)
    _sessions_sheet(workbook.create_sheet("sessoes"))
    _readme_sheet(workbook.create_sheet("leia-me"), blind)
    workbook.properties.created = datetime(2026, 1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


POST_IMPORT_STEPS = (
    "Abra o Google Sheets > Arquivo > Importar > Upload, escolha o .xlsx e 'Criar nova planilha'.",
    "Aba anotacao: selecione as colunas tema_* e obrigatoriedade (linhas 2 a 51) e use "
    "Inserir > Caixa de seleção. Os FALSE viram caixas desmarcadas.",
    "Refaça a proteção: Dados > Proteger páginas e intervalos, proteja item_id, texto e cortado "
    "(A1:C51) e a linha 1 (cabeçalho), e as abas rubrica e leia-me inteiras.",
    "Confira a validação das listas: clique numa célula de ood_manual, tipo, bloqueio, "
    "acionabilidade e duvida, veja o menu suspenso, e em Dados > Validação de dados confirme "
    "'Rejeitar entrada' (não 'Mostrar aviso').",
    "Confira hora_fim: Formatar > Número > Data e hora personalizadas = aaaa-mm-dd hh:mm:ss. "
    "Teste Cmd+Option+Shift+; numa célula e apague depois.",
    "Confira o congelamento: linha 1 e colunas item_id e texto (Ver > Congelar).",
    "Confira a formatação condicional: Formatar > Formatação condicional deve listar 7 regras "
    "amarelas na aba anotacao.",
    "Aba sessoes: confira o formato de data (aaaa-mm-dd) e de hora (hh:mm:ss) nas colunas data, "
    "inicio e fim.",
)

LOST_ON_IMPORT = (
    "A proteção de colunas e abas: o Sheets não importa a proteção do .xlsx.",
    "As caixas de seleção: chegam como TRUE/FALSE e precisam ser reconvertidas.",
    "As mensagens de erro personalizadas das listas podem virar a mensagem padrão do Sheets, e o "
    "modo 'rejeitar' pode chegar como 'mostrar aviso' (por isso o passo de conferência).",
    "A validação de data em hora_fim pode não vir; o formato da célula costuma vir.",
)

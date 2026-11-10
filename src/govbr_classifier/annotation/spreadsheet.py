"""Build the pilot annotation spreadsheet (.xlsx) for import into Google Sheets.

Every allowed value comes from taxonomy.yaml: the four attributes from `load_taxonomy()`, the
annotation-only columns from `load_annotation_fields()`. Texts are masked (`privacy.mask`) and each
one must pass the last barrier (`privacy.assert_masked`) or nothing is written.

Conditional formatting only warns, in yellow, and never marks a row as correct. The strict reader
(`annotation.reader`) is the final check.

Layout version 4 (rubric v4) adds `assunto_outro` after the tema columns and drops the `sessoes`
sheet: sessions are inferred from hora_fim (`annotation.summary`). Version 3 is the layout of the
pilot's first pass, kept so the reader can still read that frozen file.

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
LAYOUT_VERSIONS = (3, 4)
CURRENT_LAYOUT = 4
YELLOW = PatternFill(start_color="FFF2A8", end_color="FFF2A8", fill_type="solid")


def tema_columns() -> list[str]:
    """One checkbox column per tema value, in taxonomy order."""
    return [f"tema_{label}" for label in load_taxonomy().attributes["tema"].labels]


def annotation_columns(version: int = CURRENT_LAYOUT) -> list[str]:
    """The `anotacao` header of a layout version, in order; the strict reader expects exactly it."""
    if version not in LAYOUT_VERSIONS:
        raise ValueError(f"unknown layout version {version}; known: {LAYOUT_VERSIONS}")
    return [
        "item_id",
        "texto",
        "cortado",
        "ood_manual",
        *tema_columns(),
        *(["assunto_outro"] if version >= 4 else []),
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
    obrig, subject = f"${col['obrigatoriedade']}2", f"${col['assunto_outro']}2"
    nenhum, outro = f"${col['tema_nenhum']}2", f"${col['tema_outro']}2"
    hora_fim = f"${col['hora_fim']}2"
    anything = f'OR({checked}>0,{tipo}<>"",{bloq}<>"",{acion}<>"",{obrig}=TRUE,{subject}<>"")'
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
        "tema outro needs assunto_outro": f'AND({outro}=TRUE,{subject}="")',
        "annotated without hora_fim": f'AND({ood}<>"",{hora_fim}="")',
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
            cell.alignment = Alignment(
                wrap_text=name in ("texto", "assunto_outro", "nota_duvida"), vertical="top"
            )
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
    widths = {
        "item_id": 9,
        "texto": 60,
        "cortado": 9,
        "ood_manual": 17,
        "assunto_outro": 25,
        "nota_duvida": 40,
    }
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


PILOT_PURPOSE = (
    "O que é: 50 avaliações do Google Play para medir a sua velocidade e achar onde a rubrica gera "
    "dúvida. Não é o conjunto de teste. Os mesmos itens são reanotados pelo menos três semanas "
    "depois, sem olhar a primeira passada."
)

README_LINES = (
    "Como preencher a aba anotacao, item por item:",
    "1. Decida ood_manual. Se for nao, preencha tema (uma ou mais caixas), tipo, bloqueio e "
    "acionabilidade. Se for outro valor, deixe tudo vazio, inclusive a caixa obrigatoriedade.",
    "2. Marque obrigatoriedade quando o texto diz que a pessoa é obrigada a usar o app ou um "
    "mecanismo dele. Não é rótulo.",
    "3. Tema outro: escreva o assunto em assunto_outro (obrigatório). Um assunto de fora da lista "
    "ao lado de um tema da lista também pode ir em assunto_outro, para registro.",
    "4. duvida: uma categoria só, a principal, explicada em nota_duvida. Em branco quando não há "
    "dúvida. O assunto do tema outro nunca vai em nota_duvida.",
    "5. Ao terminar o item, clique em hora_fim e aperte Cmd+Option+Shift+; (grava data e hora). "
    "Não use Cmd+Shift+;, que grava só a hora. Linha anotada sem hora_fim fica amarela.",
    "",
    "O que não mexer: item_id, texto e cortado; o cabeçalho; os nomes das abas. O leitor estrito "
    "recusa a planilha se o cabeçalho mudar.",
    "",
    "Pode ordenar e filtrar à vontade: o tempo por item vem só de hora_fim, não da posição da "
    "linha. As sessões são deduzidas: mais de 60 minutos sem anotar abre uma sessão nova, e mais "
    "de 10 minutos dentro da sessão conta como pausa.",
    "",
    "Amarelo é só aviso de combinação suspeita, nunca de acerto. Não existe verde. A verificação "
    "definitiva é o leitor estrito, rodado depois.",
    "",
    "Os textos estão mascarados: [CPF], [TELEFONE], [EMAIL], [PERFIL], [NOME], [NUMERO].",
)


def _readme_sheet(ws: Worksheet, purpose: str, blind: bool) -> None:
    ws.column_dimensions["A"].width = 110
    title = "Leia-me: anotação"
    if blind:
        title += " (cópia cega para reanotação: não abra a primeira passada)"
    lines = [title, "", purpose, "", *README_LINES]
    for line in lines:
        ws.append([line])
        ws.cell(ws.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.cell(1, 1).font = Font(bold=True, size=14)
    ws.protection.sheet = True


def write_workbook(
    items: pd.DataFrame,
    path: Path,
    rubric: str,
    blind: bool = False,
    purpose: str = PILOT_PURPOSE,
) -> None:
    """Write the three sheets. Refuses to overwrite: an existing file may hold annotations."""
    if path.exists():
        raise FileExistsError(f"{path} exists; it may hold annotations. Move it away first.")
    workbook = Workbook()
    annotation = workbook.active
    assert annotation is not None
    annotation.title = "anotacao"
    _annotation_sheet(annotation, items)
    _rubric_sheet(workbook.create_sheet("rubrica"), rubric)
    _readme_sheet(workbook.create_sheet("leia-me"), purpose, blind)
    workbook.properties.created = datetime(2026, 1, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


_CHECK_STEPS = (
    "Confira a validação das listas: clique numa célula de ood_manual, tipo, bloqueio, "
    "acionabilidade e duvida, veja o menu suspenso, e em Dados > Validação de dados confirme "
    "'Rejeitar entrada' (não 'Mostrar aviso').",
    "Confira hora_fim: Formatar > Número > Data e hora personalizadas = aaaa-mm-dd hh:mm:ss. "
    "Teste Cmd+Option+Shift+; numa célula e apague depois.",
    "Confira o congelamento: linha 1 e colunas item_id e texto (Ver > Congelar).",
    "Confira a formatação condicional: Formatar > Formatação condicional deve listar 8 regras "
    "amarelas na aba anotacao.",
)


def post_import_steps(n_items: int) -> tuple[str, ...]:
    """Manual steps in Google Sheets after importing a workbook with `n_items` rows."""
    last = n_items + 1
    return (
        "Abra o Google Sheets > Arquivo > Importar > Upload, escolha o .xlsx e "
        "'Criar nova planilha'.",
        f"Aba anotacao: selecione as colunas tema_* e obrigatoriedade (linhas 2 a {last}) e use "
        "Inserir > Caixa de seleção. Os FALSE viram caixas desmarcadas.",
        "Refaça a proteção: Dados > Proteger páginas e intervalos, proteja item_id, texto e "
        f"cortado (A1:C{last}) e a linha 1 (cabeçalho), e as abas rubrica e leia-me inteiras.",
        *_CHECK_STEPS,
    )


LOST_ON_IMPORT = (
    "A proteção de colunas e abas: o Sheets não importa a proteção do .xlsx.",
    "As caixas de seleção: chegam como TRUE/FALSE e precisam ser reconvertidas.",
    "As mensagens de erro personalizadas das listas podem virar a mensagem padrão do Sheets, e o "
    "modo 'rejeitar' pode chegar como 'mostrar aviso' (por isso o passo de conferência).",
    "A validação de data em hora_fim pode não vir; o formato da célula costuma vir.",
)

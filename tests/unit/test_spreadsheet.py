"""The pilot spreadsheet: masked text, strict lists, protection, warnings, blind copy.

Synthetic texts only.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from govbr_classifier.annotation import spreadsheet
from govbr_classifier.annotation.spreadsheet import (
    annotation_columns,
    build_items,
    list_values,
    tema_columns,
    write_workbook,
)
from govbr_classifier.privacy import Masked, PersonalDataLeakError
from govbr_classifier.taxonomy import load_taxonomy

LINK = pd.DataFrame(
    {
        "item_id": ["p002", "p001", "p003"],
        "review_id": ["r2", "r1", "r3"],
        "original_length": [500, 20, 10],
    }
)
TEXTS = pd.Series(
    {
        "r1": "meu cpf 123.456.789-09 nao valida",
        "r2": "x" * 500,
        "r3": "a atendente Maria sumiu",
    }
)
RUBRIC = "# Rubrica\n\nVersão 3\n"


@pytest.fixture
def items() -> pd.DataFrame:
    return build_items(LINK, TEXTS)[0]


def test_items_are_masked_ordered_and_marked_as_cut() -> None:
    items, report = build_items(LINK, TEXTS)
    assert items["item_id"].tolist() == ["p001", "p002", "p003"]
    assert items.loc[0, "texto"] == "meu cpf [CPF] nao valida"
    assert items["cortado"].tolist() == ["nao", "sim", "nao"]
    assert report.items_masked["cpf"] == 1
    assert report.name_item_ids == ["p003"]


def test_generation_stops_if_the_mask_lets_a_cpf_through(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate a broken mask: the barrier must still stop the spreadsheet, naming only the item.
    monkeypatch.setattr(spreadsheet, "mask", lambda text: Masked(text=text, counts={}))
    with pytest.raises(PersonalDataLeakError) as error:
        build_items(LINK, TEXTS)
    assert "p001" in str(error.value)
    assert "123.456.789-09" not in str(error.value)


def test_columns_come_from_the_taxonomy() -> None:
    labels = load_taxonomy().attributes["tema"].labels
    assert tema_columns() == [f"tema_{label}" for label in labels]
    columns = annotation_columns()
    assert columns[:4] == ["item_id", "texto", "cortado", "ood_manual"]
    assert columns[-4:] == ["obrigatoriedade", "duvida", "nota_duvida", "hora_fim"]
    # v4: assunto_outro right after the tema columns; v3 (pilot first pass) has none
    assert columns[columns.index(tema_columns()[-1]) + 1] == "assunto_outro"
    assert annotation_columns(3) == [c for c in columns if c != "assunto_outro"]
    with pytest.raises(ValueError):
        annotation_columns(2)
    assert "vazio" not in list_values()["duvida"]


def test_workbook_layout(items: pd.DataFrame, tmp_path: Path) -> None:
    path = tmp_path / "sheet.xlsx"
    write_workbook(items, path, RUBRIC)
    workbook = load_workbook(path)
    assert workbook.sheetnames == ["anotacao", "rubrica", "leia-me"]  # no sessoes in v4
    ws = workbook["anotacao"]
    header = [cell.value for cell in ws[1]]
    assert header == annotation_columns()
    assert ws.freeze_panes == "C2"
    assert ws.protection.sheet

    col = {name: i for i, name in enumerate(header, start=1)}
    for row in range(2, 5):
        assert ws.cell(row, col["item_id"]).protection.locked
        assert ws.cell(row, col["texto"]).protection.locked
        assert not ws.cell(row, col["ood_manual"]).protection.locked
        for name in [*tema_columns(), "obrigatoriedade"]:
            assert ws.cell(row, col[name]).value is False
        for name in ["ood_manual", "assunto_outro", "tipo", "duvida", "nota_duvida", "hora_fim"]:
            assert ws.cell(row, col[name]).value is None
    assert ws.cell(2, col["hora_fim"]).number_format == "yyyy-mm-dd hh:mm:ss"


def test_lists_are_strict_and_hold_exactly_the_taxonomy_values(
    items: pd.DataFrame, tmp_path: Path
) -> None:
    path = tmp_path / "sheet.xlsx"
    write_workbook(items, path, RUBRIC)
    ws = load_workbook(path)["anotacao"]
    found = {}
    for validation in ws.data_validations.dataValidation:
        if validation.type == "list":
            assert validation.errorStyle == "stop"
            assert validation.showErrorMessage
            values = tuple(validation.formula1.strip('"').split(","))
            found[str(validation.sqref).split(":")[0].rstrip("0123456789")] = values
    header = annotation_columns()
    expected = {
        spreadsheet.get_column_letter(header.index(name) + 1): values
        for name, values in list_values().items()
    }
    assert found == expected


def test_warnings_are_yellow_only(items: pd.DataFrame, tmp_path: Path) -> None:
    path = tmp_path / "sheet.xlsx"
    write_workbook(items, path, RUBRIC)
    ws = load_workbook(path)["anotacao"]
    rules = [rule for ranges in ws.conditional_formatting for rule in ranges.rules]
    assert len(rules) == 8
    formulas = [rule.formula[0] for rule in rules]
    col = {name: spreadsheet.get_column_letter(i) for i, name in enumerate(annotation_columns(), 1)}
    assert f'AND(${col["tema_outro"]}2=TRUE,${col["assunto_outro"]}2="")' in formulas
    assert f'AND(${col["ood_manual"]}2<>"",${col["hora_fim"]}2="")' in formulas
    colors = {rule.dxf.fill.fgColor.rgb for rule in rules}
    assert colors == {"00FFF2A8"}


def test_blind_copy_has_the_same_items_and_no_annotation(
    items: pd.DataFrame, tmp_path: Path
) -> None:
    main, blind = tmp_path / "main.xlsx", tmp_path / "blind.xlsx"
    write_workbook(items, main, RUBRIC)
    write_workbook(items, blind, RUBRIC, blind=True)
    first, second = load_workbook(main)["anotacao"], load_workbook(blind)["anotacao"]
    assert [[c.value for c in row] for row in first.iter_rows()] == [
        [c.value for c in row] for row in second.iter_rows()
    ]
    assert "cópia cega" in load_workbook(blind)["leia-me"].cell(1, 1).value


def test_an_existing_file_is_never_overwritten(items: pd.DataFrame, tmp_path: Path) -> None:
    path = tmp_path / "sheet.xlsx"
    write_workbook(items, path, RUBRIC)
    with pytest.raises(FileExistsError):
        write_workbook(items, path, RUBRIC)


def test_blind_copy_flag_writes_a_separate_unannotated_file(tmp_path: Path) -> None:
    link_path, interim_path = tmp_path / "link.csv", tmp_path / "reviews.parquet"
    LINK.to_csv(link_path, index=False)
    TEXTS.rename_axis("review_id").rename("text").reset_index().to_parquet(interim_path)
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_pilot_sheet.py"
    command = [
        sys.executable,
        str(script),
        "--link",
        str(link_path),
        "--interim",
        str(interim_path),
    ]
    result = subprocess.run(
        [*command, "--out-dir", str(tmp_path), "--blind-copy"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / spreadsheet.BLIND_PATH.name).exists()
    assert not (tmp_path / spreadsheet.SHEET_PATH.name).exists()
    assert "123.456.789-09" not in result.stdout  # counts and item ids only
    assert "linhas 2 a 4" in result.stdout  # post-import steps follow the item count

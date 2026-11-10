"""Strict annotation reader and per-item timing. Synthetic annotations only."""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

from govbr_classifier.annotation.reader import AnnotationError, read_annotations
from govbr_classifier.annotation.spreadsheet import annotation_columns, write_workbook
from govbr_classifier.annotation.summary import time_items, time_stats

IDS = ["p001", "p002", "p003"]
FILLED = {
    "p001": {"ood_manual": "nao", "tema_travamento": True, "tipo": "bug", "bloqueio": "sim",
             "acionabilidade": "nao", "hora_fim": datetime(2026, 11, 3, 10, 1, 0)},
    "p002": {"ood_manual": "nao", "tema_nenhum": True, "tipo": "nenhum", "bloqueio": "nao",
             "acionabilidade": "nao", "hora_fim": datetime(2026, 11, 3, 10, 2, 30)},
    "p003": {"ood_manual": "low_text_quality"},
}  # fmt: skip


@pytest.fixture
def link(tmp_path: Path) -> Path:
    path = tmp_path / "link.csv"
    pd.DataFrame({"item_id": IDS, "original_length": [40, 5, 2]}).to_csv(path, index=False)
    return path


def make_sheet(tmp_path: Path, rows: dict[str, dict[str, object]], name: str = "a.xlsx") -> Path:
    path = tmp_path / name
    items = pd.DataFrame({"item_id": IDS, "texto": ["sintetico"] * 3, "cortado": ["nao"] * 3})
    write_workbook(items, path, "# rubrica")
    workbook = load_workbook(path)
    ws = workbook["anotacao"]
    col = {name: i for i, name in enumerate(annotation_columns(), start=1)}
    for row in range(2, ws.max_row + 1):
        for column, value in rows.get(ws.cell(row, 1).value, {}).items():
            ws.cell(row, col[column]).value = value
    workbook.save(path)
    return path


def problems(path: Path, link: Path, **kwargs: bool) -> list[tuple[str, str]]:
    with pytest.raises(AnnotationError) as error:
        read_annotations(path, link, **kwargs)
    message = str(error.value)
    assert "sintetico" not in message  # never the text
    return [(p.item_id, p.column) for p in error.value.problems]


def with_change(item: str, **changes: object) -> dict[str, dict[str, object]]:
    rows = {key: dict(value) for key, value in FILLED.items()}
    rows[item].update(changes)
    return rows


def test_a_valid_sheet_is_read_without_the_text(tmp_path: Path, link: Path) -> None:
    result = read_annotations(make_sheet(tmp_path, FILLED), link, require_complete=True)
    assert "texto" not in result.frame.columns
    assert result.pending == []
    assert result.frame.set_index("item_id").loc["p001", "tema_travamento"]


def test_header_must_match_exactly(tmp_path: Path, link: Path) -> None:
    path = make_sheet(tmp_path, FILLED)
    workbook = load_workbook(path)
    workbook["anotacao"].cell(1, 4).value = "ood"
    workbook.save(path)
    assert problems(path, link) == [("-", "header")]


@pytest.mark.parametrize(
    ("item", "changes", "expected"),
    [
        ("p001", {"tipo": "falha"}, ("p001", "tipo")),
        ("p001", {"ood_manual": "talvez"}, ("p001", "ood_manual")),
        ("p001", {"duvida": "vazio"}, ("p001", "duvida")),
        ("p001", {"tema_lentidao": "sim"}, ("p001", "tema_lentidao")),
        ("p001", {"hora_fim": "ontem"}, ("p001", "hora_fim")),
        ("p001", {"tema_travamento": False}, ("p001", "tema")),
        ("p001", {"bloqueio": None}, ("p001", "bloqueio")),
        ("p003", {"tipo": "bug"}, ("p003", "tipo")),
        ("p003", {"tema_outro": True}, ("p003", "tema_outro")),
        ("p003", {"obrigatoriedade": True}, ("p003", "obrigatoriedade")),
        ("p003", {"assunto_outro": "navegacao"}, ("p003", "assunto_outro")),
        ("p001", {"tema_nao_especificado": True}, ("p001", "tema_nao_especificado")),
        ("p002", {"bloqueio": "sim"}, ("p002", "bloqueio")),
        ("p002", {"acionabilidade": "sim"}, ("p002", "acionabilidade")),
        ("p001", {"tipo": "nenhum", "bloqueio": "nao"}, ("p001", "tipo")),
        ("p002", {"tipo": "bug"}, ("p002", "tipo")),
        ("p001", {"tema_travamento": False, "tema_outro": True}, ("p001", "assunto_outro")),
        ("p001", {"ood_manual": None}, ("p001", "ood_manual")),
    ],
)
def test_each_rule_rejects_the_sheet(
    tmp_path: Path, link: Path, item: str, changes: dict[str, object], expected: tuple[str, str]
) -> None:
    assert expected in problems(make_sheet(tmp_path, with_change(item, **changes)), link)


def test_two_exclusive_themes_are_rejected(tmp_path: Path, link: Path) -> None:
    rows = with_change(
        "p002", tema_outro=True, assunto_outro="assunto", tipo="pedido_funcionalidade"
    )
    assert ("p002", "tema_outro") in problems(make_sheet(tmp_path, rows), link)


def test_tema_outro_takes_the_subject_from_assunto_outro_not_nota_duvida(
    tmp_path: Path, link: Path
) -> None:
    outro = {"tema_travamento": False, "tema_outro": True, "tipo": "insatisfacao_geral"}
    with_note = with_change("p001", **outro, nota_duvida="assunto", duvida="tema_limite")
    assert ("p001", "assunto_outro") in problems(make_sheet(tmp_path, with_note), link)
    with_subject = with_change("p001", **outro, assunto_outro="navegacao")
    read_annotations(make_sheet(tmp_path, with_subject, "b.xlsx"), link)


def test_assunto_outro_may_sit_next_to_a_listed_theme(tmp_path: Path, link: Path) -> None:
    rows = with_change("p001", assunto_outro="prazo do orgao")
    result = read_annotations(make_sheet(tmp_path, rows), link, require_complete=True)
    assert result.version == 4
    assert result.frame.set_index("item_id").loc["p001", "assunto_outro"] == "prazo do orgao"


def v3_sheet(tmp_path: Path, rows: dict[str, dict[str, object]], name: str = "v3.xlsx") -> Path:
    """The layout of the pilot's first pass: no assunto_outro column."""
    path = make_sheet(tmp_path, rows, name)
    workbook = load_workbook(path)
    ws = workbook["anotacao"]
    ws.delete_cols(annotation_columns().index("assunto_outro") + 1)
    workbook.save(path)
    return path


def test_the_v3_layout_is_read_by_the_v3_rules(tmp_path: Path, link: Path) -> None:
    outro = {"tema_travamento": False, "tema_outro": True, "tipo": "insatisfacao_geral"}
    result = read_annotations(
        v3_sheet(tmp_path, with_change("p001", **outro, nota_duvida="assunto")), link
    )
    assert result.version == 3
    assert "assunto_outro" not in result.frame.columns
    assert ("p001", "nota_duvida") in problems(
        v3_sheet(tmp_path, with_change("p001", **outro), "b.xlsx"), link
    )


def test_a_mixed_header_is_rejected(tmp_path: Path, link: Path) -> None:
    # v4 columns in the v3 order (assunto_outro moved to the end) match neither layout.
    path = make_sheet(tmp_path, FILLED)
    workbook = load_workbook(path)
    ws = workbook["anotacao"]
    position = annotation_columns().index("assunto_outro") + 1
    ws.delete_cols(position)
    ws.cell(1, ws.max_column + 1).value = "assunto_outro"
    workbook.save(path)
    assert problems(path, link) == [("-", "header")]


def test_tema_nenhum_accepts_a_feature_request(tmp_path: Path, link: Path) -> None:
    rows = with_change("p002", tipo="pedido_funcionalidade", acionabilidade="sim")
    read_annotations(make_sheet(tmp_path, rows), link)


def test_item_ids_unknown_duplicated_or_missing(tmp_path: Path, link: Path) -> None:
    path = make_sheet(tmp_path, FILLED)
    workbook = load_workbook(path)
    ws = workbook["anotacao"]
    ws.cell(2, 1).value = "p999"
    ws.cell(3, 1).value = "p003"  # row 4 is p003 too
    workbook.save(path)
    found = problems(path, link)
    assert ("p999", "item_id") in found
    assert ("p003", "item_id") in found

    ws.cell(2, 1).value = None
    workbook.save(path)
    assert ("row 2", "item_id") in problems(path, link)


def test_untouched_rows_are_pending_and_only_fail_when_completeness_is_required(
    tmp_path: Path, link: Path
) -> None:
    rows = {key: value for key, value in FILLED.items() if key != "p003"}
    path = make_sheet(tmp_path, rows)
    assert read_annotations(path, link).pending == ["p003"]
    assert problems(path, link, require_complete=True) == [("p003", "ood_manual")]


def test_the_csv_export_is_read_the_same_way(tmp_path: Path, link: Path) -> None:
    sheet = pd.read_excel(make_sheet(tmp_path, FILLED), sheet_name="anotacao", dtype=object)
    sheet["hora_fim"] = sheet["hora_fim"].map(
        lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else ""
    )
    for column in sheet.columns:
        sheet[column] = sheet[column].map(
            lambda v: "TRUE" if v is True else "FALSE" if v is False else ("" if pd.isna(v) else v)
        )
    path = tmp_path / "export.csv"
    sheet.to_csv(path, index=False)
    result = read_annotations(path, link, require_complete=True)
    assert result.frame.set_index("item_id").loc["p002", "tema_nenhum"]


def test_sessions_are_inferred_from_gaps_between_hora_fim() -> None:
    at = lambda m, s=0: datetime(2026, 11, 3, 10, m, s)  # noqa: E731
    annotations = pd.DataFrame(
        {
            # row order is shuffled on purpose: only hora_fim matters
            "item_id": ["c", "a", "b", "d", "e", "f", "g"],
            "hora_fim": [at(4), at(1), at(3), at(30), None, datetime(2026, 11, 3, 11, 31), at(31)],
        }
    )
    timing = time_items(annotations)
    kinds = dict(zip(timing.intervals["item_id"], timing.intervals["kind"], strict=True))
    seconds = dict(zip(timing.intervals["item_id"], timing.intervals["seconds"], strict=True))
    sessions = dict(zip(timing.intervals["item_id"], timing.intervals["session"], strict=True))
    # d: 26 min after c, a pause in the same session; f: exactly 60 min after g, same session too
    assert kinds == {
        "a": "first", "b": "interval", "c": "interval", "d": "pause", "g": "interval",
        "f": "pause",
    }  # fmt: skip
    assert seconds["b"] == 120 and seconds["c"] == 60 and pd.isna(seconds["a"])
    assert set(sessions.values()) == {1}
    assert timing.no_time == ["e"]

    later = pd.concat(
        [annotations, pd.DataFrame({"item_id": ["h"], "hora_fim": [datetime(2026, 11, 3, 12, 32)]})]
    )
    timing = time_items(later)  # h: 61 min after f, opens session 2
    row = timing.intervals.set_index("item_id").loc["h"]
    assert row["kind"] == "first" and row["session"] == 2 and pd.isna(row["seconds"])
    assert timing.sessions["items"].tolist() == [6, 1]

    stats = time_stats(timing.intervals, pd.Series({"b": 5, "c": 40, "g": 40}))
    assert stats.loc["all", "items"] == 3
    assert stats.loc["all", "median_s"] == 60
    assert stats.loc["<= 12 chars", "median_s"] == 120

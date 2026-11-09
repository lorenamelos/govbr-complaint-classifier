"""Strict reader of the annotation spreadsheet (.xlsx, or .csv exported from Google Sheets).

It raises, never warns and never corrects. Every problem is collected and reported with the item_id
and the column, never the text. The rules are the consistency rules of rubric v3
(docs/rubric/annotation_rubric.pt.md) plus the shape of the sheet:

- the header matches `spreadsheet.annotation_columns()` exactly, order included;
- every list value is in taxonomy.yaml (attributes or the annotation section), checkboxes are
  TRUE/FALSE, hora_fim is a date and time;
- item_id is present, unique and in the pilot link table;
- ood_manual = nao requires tema (at least one box), tipo, bloqueio and acionabilidade;
- ood_manual other than nao requires the four attributes and the obrigatoriedade box empty;
- at most one exclusive tema value, and never next to a specific theme;
- tipo = nenhum requires tema = nenhum, bloqueio = nao and acionabilidade = nao;
- tema = nenhum accepts tipo nenhum or pedido_funcionalidade only;
- tema = outro requires nota_duvida (the subject).

A row with nothing filled is pending; it is an error only with `require_complete`. A blank
ood_manual next to anything filled is an error.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from govbr_classifier.annotation.fields import load_annotation_fields
from govbr_classifier.annotation.pilot import PILOT_DIR
from govbr_classifier.annotation.spreadsheet import annotation_columns, list_values, tema_columns
from govbr_classifier.taxonomy import load_taxonomy

LINK_PATH = PILOT_DIR / "link.csv"
SHEET = "anotacao"
DATETIME_TEXT = "%Y-%m-%d %H:%M:%S"
TEXT_COLUMN = "texto"
TRUE_TEXT, FALSE_TEXT = "TRUE", "FALSE"


@dataclass(frozen=True)
class Problem:
    """One rule broken by one item. Never carries the text."""

    item_id: str
    column: str
    rule: str

    def __str__(self) -> str:
        return f"{self.item_id} | {self.column} | {self.rule}"


class AnnotationError(ValueError):
    """The annotation file breaks at least one rule; `problems` lists every one of them."""

    def __init__(self, problems: list[Problem]) -> None:
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s):\n" + "\n".join(map(str, problems)))


@dataclass(frozen=True)
class Annotations:
    """Validated annotations (without the text column) and the pending item ids."""

    frame: pd.DataFrame
    pending: list[str]


def _load_rows(path: Path) -> tuple[list[str], list[list[object]]]:
    if path.suffix == ".xlsx":
        workbook = load_workbook(path, data_only=True)
        if SHEET not in workbook.sheetnames:
            raise AnnotationError([Problem("-", "-", f"no sheet named {SHEET!r}")])
        rows = list(workbook[SHEET].iter_rows(values_only=True))
        header = ["" if value is None else str(value) for value in rows[0]]
        return header, [list(row) for row in rows[1:] if any(v is not None for v in row)]
    if path.suffix == ".csv":
        table = pd.read_csv(path, dtype=str, keep_default_na=False)
        return list(table.columns), table.to_numpy(dtype=object).tolist()
    raise AnnotationError([Problem("-", "-", f"unsupported file type {path.suffix!r}")])


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _checkbox(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (TRUE_TEXT, FALSE_TEXT):
        return value == TRUE_TEXT
    return None


def _moment(value: object) -> datetime | str | None:
    """A datetime, None when blank, or the string "invalid"."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), DATETIME_TEXT)
    except ValueError:
        return "invalid"


def read_annotations(
    path: Path, link_path: Path = LINK_PATH, require_complete: bool = False
) -> Annotations:
    """Validate the annotation file and return it without the text column."""
    expected = annotation_columns()
    header, rows = _load_rows(path)
    if header != expected:
        raise AnnotationError([Problem("-", "header", f"expected {expected}, found {header}")])
    known_ids = set(pd.read_csv(link_path, dtype=str)["item_id"])
    lists = list_values()
    lists["cortado"] = ("sim", "nao")
    checkboxes = [*tema_columns(), "obrigatoriedade"]
    exclusive = {f"tema_{label}" for label in load_taxonomy().attributes["tema"].exclusive}
    none_value = load_annotation_fields().ood_none_value
    attributes = ("tipo", "bloqueio", "acionabilidade")

    problems: list[Problem] = []
    records, pending, seen = [], [], set()
    for position, raw in enumerate(rows, start=2):
        cells = dict(zip(header, raw, strict=True))
        item = _text(cells["item_id"])
        label = item or f"row {position}"
        if not item:
            problems.append(Problem(label, "item_id", "missing"))
        elif item in seen:
            problems.append(Problem(item, "item_id", "duplicated"))
        elif item not in known_ids:
            problems.append(Problem(item, "item_id", "not in the pilot link table"))
        seen.add(item)

        record: dict[str, object] = {"item_id": item}
        for name in expected:
            if name in ("item_id", TEXT_COLUMN):
                continue
            value = cells[name]
            if name in checkboxes:
                checked = _checkbox(value)
                if checked is None:
                    problems.append(Problem(label, name, "checkbox must be TRUE or FALSE"))
                record[name] = bool(checked)
            elif name == "hora_fim":
                moment = _moment(value)
                if moment == "invalid":
                    problems.append(Problem(label, name, f"not a date and time ({DATETIME_TEXT})"))
                    moment = None
                record[name] = moment
            else:
                text = _text(value)
                if name in lists and text and text not in lists[name]:
                    problems.append(Problem(label, name, "value outside the list"))
                record[name] = text

        themes = [name for name in tema_columns() if record[name]]
        filled = (
            bool(themes)
            or record["obrigatoriedade"]
            or any(record[name] for name in (*attributes, "duvida", "nota_duvida", "hora_fim"))
        )
        ood = record["ood_manual"]
        if not ood:
            if filled:
                problems.append(Problem(label, "ood_manual", "empty while other fields are filled"))
            else:
                pending.append(label)
                if require_complete:
                    problems.append(Problem(label, "ood_manual", "pending (not annotated)"))
            records.append(record)
            continue

        if ood == none_value:
            if not themes:
                problems.append(Problem(label, "tema", "ood_manual = nao needs at least one theme"))
            for name in attributes:
                if not record[name]:
                    problems.append(Problem(label, name, "ood_manual = nao needs a value"))
        else:
            for name in themes:
                problems.append(Problem(label, name, f"ood_manual = {ood} needs no theme"))
            for name in attributes:
                if record[name]:
                    problems.append(Problem(label, name, f"ood_manual = {ood} needs it empty"))
            if record["obrigatoriedade"]:
                problems.append(
                    Problem(label, "obrigatoriedade", f"ood_manual = {ood} needs it empty")
                )

        chosen_exclusive = [name for name in themes if name in exclusive]
        if chosen_exclusive and len(themes) > 1:
            for name in chosen_exclusive:
                problems.append(Problem(label, name, "exclusive theme combined with another theme"))
        if record["tipo"] == "nenhum":
            if themes != ["tema_nenhum"]:
                problems.append(Problem(label, "tipo", "tipo = nenhum needs tema = nenhum only"))
            if record["bloqueio"] != "nao":
                problems.append(Problem(label, "bloqueio", "tipo = nenhum needs bloqueio = nao"))
            if record["acionabilidade"] != "nao":
                problems.append(
                    Problem(label, "acionabilidade", "tipo = nenhum needs acionabilidade = nao")
                )
        if record["tema_nenhum"] and record["tipo"] not in ("", "nenhum", "pedido_funcionalidade"):
            problems.append(
                Problem(label, "tipo", "tema = nenhum needs tipo nenhum or pedido_funcionalidade")
            )
        if record["tema_outro"] and not str(record["nota_duvida"]).strip():
            problems.append(Problem(label, "nota_duvida", "tema = outro needs the subject"))
        records.append(record)

    if problems:
        raise AnnotationError(problems)
    frame = pd.DataFrame(records)
    frame["status"] = ["pending" if item in pending else "annotated" for item in frame["item_id"]]
    return Annotations(frame=frame, pending=pending)

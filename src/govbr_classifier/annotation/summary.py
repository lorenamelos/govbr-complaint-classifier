"""Summary of a pilot annotation pass: counts only, never review text.

Time per item comes from hora_fim and the `sessoes` sheet, never from row order. Within a session
(hora_fim between its start and end), the times are sorted and each item gets the gap since the
previous one; the first item of a session is measured from the session start and reported apart.
A gap above PAUSE_MINUTES is a pause and stays out of the statistics. Items with no hora_fim, or
outside every session, are listed by item_id.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from govbr_classifier.annotation.spreadsheet import tema_columns

PAUSE_MINUTES = 10
SHORT_TEXT_CHARS = 12
ACTIONABLE_WARNING = 0.80
DOUBT_SHARE = 0.10


@dataclass(frozen=True)
class Timing:
    """Per-item seconds plus the items that could not be timed."""

    intervals: pd.DataFrame  # item_id, session, seconds, kind (first, interval, pause)
    no_time: list[str]
    outside_sessions: list[str]


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    return None


def _as_time(value: object) -> time | None:
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    if isinstance(value, str) and value.strip():
        return datetime.strptime(value.strip(), "%H:%M:%S").time()
    return None


def read_sessions(path: Path) -> pd.DataFrame:
    """Sessions from the `sessoes` sheet, as start and end datetimes; blank rows skipped."""
    rows = list(load_workbook(path, data_only=True)["sessoes"].iter_rows(values_only=True))
    sessions = []
    for number, row in enumerate(rows[1:], start=1):
        day, start, end = _as_date(row[0]), _as_time(row[1]), _as_time(row[2])
        if day is None and start is None and end is None:
            continue
        if day is None or start is None or end is None:
            raise ValueError(f"sessoes row {number + 1}: data, inicio and fim are all required")
        sessions.append(
            {
                "session": number,
                "start": datetime.combine(day, start),
                "end": datetime.combine(day, end),
            }
        )
    return pd.DataFrame(sessions, columns=["session", "start", "end"])


def time_items(annotations: pd.DataFrame, sessions: pd.DataFrame) -> Timing:
    """Seconds per item within each session; pauses marked, unplaced items listed."""
    timed = annotations[annotations["hora_fim"].notna()][["item_id", "hora_fim"]]
    no_time = sorted(annotations.loc[annotations["hora_fim"].isna(), "item_id"])
    placed, rows = set(), []
    for session in sessions.itertuples(index=False):
        inside = timed[(timed["hora_fim"] >= session.start) & (timed["hora_fim"] <= session.end)]
        previous = session.start
        for position, item in enumerate(inside.sort_values("hora_fim").itertuples(index=False)):
            seconds = (item.hora_fim - previous).total_seconds()
            if position == 0:
                kind = "first"
            else:
                kind = "pause" if seconds > PAUSE_MINUTES * 60 else "interval"
            rows.append(
                {
                    "item_id": item.item_id,
                    "session": session.session,
                    "seconds": seconds,
                    "kind": kind,
                }
            )
            placed.add(item.item_id)
            previous = item.hora_fim
    outside = sorted(set(timed["item_id"]) - placed)
    intervals = pd.DataFrame(rows, columns=["item_id", "session", "seconds", "kind"])
    return Timing(intervals=intervals, no_time=no_time, outside_sessions=outside)


def time_stats(intervals: pd.DataFrame, lengths: pd.Series) -> pd.DataFrame:
    """Median, p90 and total seconds over `interval` rows, overall and by text length band."""
    usable = intervals[intervals["kind"].eq("interval")].copy()
    usable["band"] = (
        usable["item_id"]
        .map(lengths)
        .map(
            lambda n: (
                f"<= {SHORT_TEXT_CHARS} chars"
                if n <= SHORT_TEXT_CHARS
                else f"> {SHORT_TEXT_CHARS} chars"
            )
        )
    )
    groups = {"all": usable, **{band: g for band, g in usable.groupby("band")}}
    return pd.DataFrame(
        {
            name: {
                "items": len(g),
                "median_s": g["seconds"].median(),
                "p90_s": g["seconds"].quantile(0.9),
                "total_min": g["seconds"].sum() / 60,
            }
            for name, g in groups.items()
        }
    ).T


def attribute_counts(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Counts of each attribute among annotated items with ood_manual = nao."""
    inside = frame[frame["ood_manual"].eq("nao")]
    counts = {name: inside[name].value_counts() for name in ("tipo", "bloqueio", "acionabilidade")}
    counts["tema"] = inside[tema_columns()].sum().rename(lambda c: c.removeprefix("tema_"))
    counts["themes per item"] = inside[tema_columns()].sum(axis=1).value_counts().sort_index()
    return counts

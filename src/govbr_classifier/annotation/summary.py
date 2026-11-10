"""Summary of an annotation pass: counts only, never review text.

Time per item comes from hora_fim alone, never from row order, and is approximate. Sessions are
inferred: the hora_fim values are sorted, and a gap above SESSION_GAP_MINUTES opens a new session.
Within a session each item gets the gap since the previous one. The first item of a session has
no start to measure from and is listed apart. A gap above PAUSE_MINUTES within a session is a
pause and stays out of the statistics. Items with no hora_fim are listed by item_id; their time
is absorbed into the next timed gap, which then reads longer than it was.
"""

from dataclasses import dataclass

import pandas as pd

from govbr_classifier.annotation.spreadsheet import tema_columns

SESSION_GAP_MINUTES = 60
PAUSE_MINUTES = 10
SHORT_TEXT_CHARS = 12
ACTIONABLE_WARNING = 0.80
DOUBT_SHARE = 0.10


@dataclass(frozen=True)
class Timing:
    """Per-item seconds, the inferred sessions and the items that could not be timed."""

    intervals: pd.DataFrame  # item_id, session, seconds (NaN for first), kind
    sessions: pd.DataFrame  # session, start, end, items (start and end are hora_fim values)
    no_time: list[str]


def time_items(annotations: pd.DataFrame) -> Timing:
    """Infer sessions from hora_fim gaps and time each item within its session."""
    timed = (
        annotations.loc[annotations["hora_fim"].notna(), ["item_id", "hora_fim"]]
        .assign(hora_fim=lambda frame: pd.to_datetime(frame["hora_fim"]))
        .sort_values(["hora_fim", "item_id"])
        .reset_index(drop=True)
    )
    no_time = sorted(annotations.loc[annotations["hora_fim"].isna(), "item_id"])
    gaps = timed["hora_fim"].diff().dt.total_seconds()
    opens = gaps.isna() | (gaps > SESSION_GAP_MINUTES * 60)
    session = opens.cumsum().astype(int)
    kind = pd.Series("interval", index=timed.index)
    kind[gaps > PAUSE_MINUTES * 60] = "pause"
    kind[opens] = "first"
    intervals = pd.DataFrame(
        {
            "item_id": timed["item_id"],
            "session": session,
            "seconds": gaps.where(~opens),
            "kind": kind,
        }
    )
    sessions = (
        timed.assign(session=session)
        .groupby("session")
        .agg(start=("hora_fim", "min"), end=("hora_fim", "max"), items=("item_id", "size"))
        .reset_index()
    )
    return Timing(intervals=intervals, sessions=sessions, no_time=no_time)


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

"""Build data/interim/ from raw collection runs: one row per review, no authorship.

Rules (data/README.md):

- Deduplicate by review ID. When the same ID appears more than once with a different text or date,
  the person edited the review during the collection; the most recent version is kept and the
  number of such IDs is recorded.
- Output columns come from an explicit allowlist. The author name, the profile picture URL and the
  text of the government's reply are dropped: the reply often greets the author by name. A field
  the scraper starts returning in the future is dropped until someone decides otherwise.
- Dates come from the raw epoch seconds and are written as UTC with an explicit time zone.
- The review text is kept exactly as collected. Cleaning is studied in notebook 01 and decided
  later; this step must not change what people wrote.
"""

from typing import Any

import pandas as pd

COLUMNS = (
    "review_id",
    "text",
    "score",
    "thumbs_up",
    "app_version",
    "at",
    "has_reply",
    "replied_at",
    "reply_delay_hours",
)
DROPPED_FOR_PRIVACY = ("userName", "userImage", "replyContent")


def build_interim(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return the interim table and the statistics of the step."""
    rows_raw = len(raw)
    ordered = raw.sort_values("at_epoch", ascending=False, kind="stable")
    repeated = ordered[ordered["reviewId"].duplicated(keep=False)]
    changed = repeated.groupby("reviewId")[["content", "at_epoch"]].nunique(dropna=False)
    edited_during_collection = int(changed.gt(1).any(axis=1).sum())
    latest = ordered.drop_duplicates("reviewId", keep="first")

    at = pd.to_datetime(latest["at_epoch"], unit="s", utc=True)
    replied_at = pd.to_datetime(latest["replied_at_epoch"], unit="s", utc=True)
    interim = pd.DataFrame(
        {
            "review_id": latest["reviewId"],
            "text": latest["content"],
            "score": latest["score"].astype("Int64"),
            "thumbs_up": latest["thumbsUpCount"].astype("Int64"),
            "app_version": latest["appVersion"],
            "at": at,
            "has_reply": latest["replied_at_epoch"].notna() | latest["replyContent"].notna(),
            "replied_at": replied_at,
            # Negative when the review was edited after the reply: `at` is the last edit.
            "reply_delay_hours": (replied_at - at).dt.total_seconds() / 3600,
        }
    ).reset_index(drop=True)[list(COLUMNS)]

    version_mismatch = int(
        (raw["appVersion"].fillna("") != raw["reviewCreatedVersion"].fillna("")).sum()
    )
    stats = {
        "rows_raw": rows_raw,
        "rows_interim": len(interim),
        "duplicate_rows": rows_raw - len(interim),
        "duplicate_rate": (rows_raw - len(interim)) / rows_raw if rows_raw else 0.0,
        "ids_edited_during_collection": edited_during_collection,
        "app_version_field_mismatches": version_mismatch,
        "replies_before_last_edit": int((interim["reply_delay_hours"] < 0).sum()),
        "columns_dropped_for_privacy": list(DROPPED_FOR_PRIVACY),
        "review_window_utc": {
            "oldest": at.min().isoformat() if len(at) else None,
            "newest": at.max().isoformat() if len(at) else None,
        },
    }
    return interim, stats

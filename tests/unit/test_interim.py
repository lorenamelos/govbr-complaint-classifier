"""Interim step: deduplication by review ID, no authorship, UTC dates, text untouched."""

import pandas as pd

from govbr_classifier.data.interim import COLUMNS, build_interim

T0 = 1_700_000_000


def raw_row(review_id: str, text: str, at: int, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "reviewId": review_id,
        "userName": "Maria da Silva",
        "userImage": "https://play-lh.googleusercontent.com/a/photo",
        "content": text,
        "score": 1,
        "thumbsUpCount": 0,
        "reviewCreatedVersion": "3.9.0",
        "appVersion": "3.9.0",
        "at": pd.Timestamp(at, unit="s"),
        "at_epoch": at,
        "replyContent": None,
        "repliedAt": None,
        "replied_at_epoch": None,
    }
    return row | extra


def test_duplicates_are_removed_and_counted() -> None:
    raw = pd.DataFrame([raw_row("a", "x", T0), raw_row("a", "x", T0), raw_row("b", "y", T0)])
    interim, stats = build_interim(raw)
    assert sorted(interim["review_id"]) == ["a", "b"]
    assert stats["duplicate_rows"] == 1
    assert stats["duplicate_rate"] == 1 / 3
    assert stats["ids_edited_during_collection"] == 0


def test_review_edited_during_collection_keeps_the_latest_version() -> None:
    raw = pd.DataFrame([raw_row("a", "nao abre", T0), raw_row("a", "agora abre", T0 + 600)])
    interim, stats = build_interim(raw)
    assert interim["text"].tolist() == ["agora abre"]
    assert stats["ids_edited_during_collection"] == 1


def test_authorship_and_reply_text_never_reach_interim() -> None:
    raw = pd.DataFrame(
        [
            raw_row(
                "a",
                "x",
                T0,
                replyContent="Ola, Maria da Silva, obrigado.",
                replied_at_epoch=T0 + 7200,
            )
        ]
    )
    interim, _ = build_interim(raw)
    assert tuple(interim.columns) == COLUMNS
    flat = interim.astype(str).to_string()
    assert "Maria" not in flat
    assert "googleusercontent" not in flat


def test_reply_is_kept_as_presence_time_and_delay() -> None:
    raw = pd.DataFrame(
        [
            raw_row("a", "x", T0, replyContent="ok", replied_at_epoch=T0 + 7200),
            raw_row("b", "y", T0),
        ]
    )
    interim, _ = build_interim(raw)
    by_id = interim.set_index("review_id")
    assert bool(by_id.loc["a", "has_reply"]) is True
    assert by_id.loc["a", "reply_delay_hours"] == 2.0
    assert bool(by_id.loc["b", "has_reply"]) is False
    assert pd.isna(by_id.loc["b", "replied_at"])


def test_reply_before_last_edit_shows_as_negative_delay() -> None:
    # `at` is the date of the last edit, so a review edited after the reply precedes it in time.
    raw = pd.DataFrame([raw_row("a", "x", T0, replyContent="ok", replied_at_epoch=T0 - 3600)])
    interim, stats = build_interim(raw)
    assert interim["reply_delay_hours"].iloc[0] == -1.0
    assert stats["replies_before_last_edit"] == 1


def test_dates_are_utc_from_epoch_seconds() -> None:
    interim, stats = build_interim(pd.DataFrame([raw_row("a", "x", T0)]))
    assert str(interim["at"].dt.tz) == "UTC"
    assert interim["at"].iloc[0] == pd.Timestamp("2023-11-14 22:13:20", tz="UTC")
    assert stats["review_window_utc"]["oldest"] == "2023-11-14T22:13:20+00:00"


def test_text_is_kept_exactly_as_collected() -> None:
    text = "  Não consigo   entrar!! 😡 \n"
    interim, _ = build_interim(pd.DataFrame([raw_row("a", text, T0)]))
    assert interim["text"].iloc[0] == text


def test_columns_the_scraper_adds_later_are_dropped() -> None:
    raw = pd.DataFrame([raw_row("a", "x", T0, userEmail="someone@example.com")])
    interim, _ = build_interim(raw)
    assert "userEmail" not in interim.columns

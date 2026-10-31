"""Collection loop: the end of the history and a failure must never look the same."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from govbr_classifier.data import collect as collect_module
from govbr_classifier.data.collect import (
    EMPTY_PAGE_WITH_TOKEN,
    END_OF_HISTORY,
    ERROR_AFTER_RETRIES,
    MAX_PAGES,
    CollectionState,
    collect,
)
from govbr_classifier.data.raw_store import RawRun


def pages(n: int, size: int = 2) -> dict[str | None, tuple[list[dict], str | None]]:
    """n pages chained by tokens t1, t2, ...; the last one returns no token."""
    chain: dict[str | None, tuple[list[dict], str | None]] = {}
    for i in range(n):
        token = None if i == 0 else f"t{i}"
        rows = [
            {"reviewId": f"r{i}-{j}", "at_epoch": 1_700_000_000 - i * 100 - j} for j in range(size)
        ]
        chain[token] = (rows, f"t{i + 1}" if i < n - 1 else None)
    return chain


class FakeFetch:
    """Serves a page chain, raising a given number of times before answering a token."""

    def __init__(self, chain: dict, failures: dict[str | None, int] | None = None) -> None:
        self.chain = chain
        self.failures = dict(failures or {})
        self.calls: list[str | None] = []

    def __call__(self, token: str | None) -> tuple[list[dict], str | None]:
        self.calls.append(token)
        if self.failures.get(token, 0) > 0:
            self.failures[token] -= 1
            raise ConnectionError("rate limited")
        return self.chain[token]


class Recorder:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.tokens: list[str | None] = []

    def __call__(self, rows: list[dict], token: str | None, state: CollectionState) -> None:
        self.rows.extend(rows)
        self.tokens.append(token)


def run(fetch: FakeFetch, recorder: Recorder, **kwargs) -> CollectionState:
    kwargs.setdefault("sleep", lambda _: None)
    return collect(fetch, on_checkpoint=recorder, **kwargs)


def test_reaches_the_end_of_the_history() -> None:
    recorder = Recorder()
    state = run(FakeFetch(pages(5)), recorder, checkpoint_pages=2)
    assert state.stop_reason == END_OF_HISTORY
    assert state.pages == 5
    assert len(recorder.rows) == 10
    assert recorder.tokens[-1] is None  # nothing left to resume


def test_checkpoints_carry_the_token_to_resume_from() -> None:
    recorder = Recorder()
    run(FakeFetch(pages(5)), recorder, checkpoint_pages=2)
    assert recorder.tokens == ["t2", "t4", None]


def test_page_limit_stops_with_a_resumable_token() -> None:
    recorder = Recorder()
    state = run(FakeFetch(pages(5)), recorder, max_pages=3)
    assert state.stop_reason == MAX_PAGES
    assert recorder.tokens[-1] == "t3"


def test_transient_errors_are_retried_with_backoff() -> None:
    waits: list[float] = []
    fetch = FakeFetch(pages(3), failures={"t1": 2})
    state = run(fetch, Recorder(), sleep=waits.append, pause_seconds=0.5, backoff_seconds=5)
    assert state.stop_reason == END_OF_HISTORY
    assert state.retries == 2
    assert [w for w in waits if w != 0.5] == [5, 10]


def test_repeated_errors_stop_the_run_as_an_error_not_as_the_end() -> None:
    # The library's own reviews() would return an empty token here, which reads as "end".
    recorder = Recorder()
    fetch = FakeFetch(pages(4), failures={"t2": 99})
    state = run(fetch, recorder, max_retries=3)
    assert state.stop_reason == ERROR_AFTER_RETRIES
    assert state.last_error == "ConnectionError: rate limited"
    assert len(recorder.rows) == 4  # the two pages before the failure are kept
    assert recorder.tokens[-1] == "t2"  # resume retries the page that failed


def test_empty_page_with_a_token_is_not_called_the_end() -> None:
    chain = pages(2)
    chain["t1"] = ([], "t2")
    state = run(FakeFetch(chain), Recorder())
    assert state.stop_reason == EMPTY_PAGE_WITH_TOKEN


def test_resumed_run_continues_counters_and_token() -> None:
    fetch = FakeFetch(pages(5))
    state = run(fetch, Recorder(), start_token="t3", state=CollectionState(pages=3, reviews=6))
    assert fetch.calls == ["t3", "t4"]
    assert (state.pages, state.reviews) == (5, 10)


@pytest.mark.parametrize(("tz", "ok"), [("America/Sao_Paulo", False), ("UTC", True)])
def test_collection_refuses_a_non_utc_process(tz: str, ok: bool) -> None:
    # A real process in another time zone, not a mock: the guard reads the actual conversion.
    code = "from govbr_classifier.data.collect import assert_utc_process; assert_utc_process()"
    result = subprocess.run(
        [sys.executable, "-c", code], env={**os.environ, "TZ": tz}, capture_output=True, text=True
    )
    assert (result.returncode == 0) is ok
    if not ok:
        assert "not UTC" in result.stderr


def test_epoch_is_read_from_the_raw_item_without_time_zone() -> None:
    item: list = [None] * 11
    item[5] = [1_700_000_000, 0]
    item[7] = [None, "reply", [1_700_003_600, 0]]
    assert collect_module._epoch(item, (5, 0)) == 1_700_000_000
    assert collect_module._epoch(item, (7, 2, 0)) == 1_700_003_600
    assert collect_module._epoch([None] * 11, (7, 2, 0)) is None


# ---------- raw run on disk ----------


def test_interrupted_run_is_never_marked_complete(tmp_path: Path) -> None:
    raw = RawRun.create(tmp_path, {"app_id": "x"}, {"google_play_scraper": "1.2.7"})
    state = run(FakeFetch(pages(4), failures={"t2": 99}), raw.checkpoint, max_retries=1)  # type: ignore[arg-type]
    metadata = raw.finish(state, {"seconds": 1})
    assert metadata["status"] == "stopped"
    assert metadata["stop_reason"] == ERROR_AFTER_RETRIES
    assert metadata["rows_on_disk"] == 4
    assert json.loads(raw.state_path.read_text())["token"] == "t2"


def test_complete_run_records_its_review_window(tmp_path: Path) -> None:
    raw = RawRun.create(tmp_path, {"app_id": "x"}, {})
    state = run(FakeFetch(pages(3)), raw.checkpoint, checkpoint_pages=1)  # type: ignore[arg-type]
    metadata = raw.finish(state, {"seconds": 1})
    assert metadata["status"] == "complete"
    assert len(list(raw.run_dir.glob("part-*.parquet"))) == 3
    assert metadata["review_window_utc"]["newest"] == "2023-11-14T22:13:20+00:00"
    assert metadata["review_window_utc"]["oldest"] == "2023-11-14T22:09:59+00:00"


def test_resume_point_round_trips(tmp_path: Path) -> None:
    raw = RawRun.create(tmp_path, {}, {})
    run(FakeFetch(pages(5)), raw.checkpoint, max_pages=2)  # type: ignore[arg-type]
    token, state = raw.resume_point()
    assert token == "t2"
    assert (state.pages, state.reviews) == (2, 4)

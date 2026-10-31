"""Collect Google Play reviews of the gov.br app (build step 2).

Two traps in google-play-scraper 1.2.7 shape this module:

- `reviews()` catches every exception and returns an empty continuation token, which is also how
  it signals the end of the history. A rate limit or a network error would end a collection early
  and look exactly like a complete one. So this module calls the one-request function
  `_fetch_review_items` directly and lets errors reach its own retry loop; the end of the history
  and a failure stay distinguishable, and the stop reason is recorded. That function is private,
  so the library version is pinned exactly in pyproject.toml.
- Dates are converted with `datetime.fromtimestamp`, which applies the time zone of the machine
  running the collection and returns naive datetimes. The same review would get a different hour
  on a laptop in Brasilia and on a CI runner in UTC. The raw epoch seconds are therefore kept next
  to the converted values (`at_epoch`, `replied_at_epoch`), and collection refuses to run unless
  the process is in UTC, so the converted columns are UTC too.

The review date is the date of the last edit: Google Play exposes one timestamp per review and no
original date. `appVersion` and `reviewCreatedVersion` are read from the same position of the
response, so they are one field.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

Row = dict[str, Any]
Fetch = Callable[[str | None], tuple[list[Row], str | None]]
Checkpoint = Callable[[list[Row], str | None, "CollectionState"], None]

END_OF_HISTORY = "end_of_history"
MAX_PAGES = "max_pages"
ERROR_AFTER_RETRIES = "error_after_retries"
EMPTY_PAGE_WITH_TOKEN = "empty_page_with_token"


def assert_utc_process() -> None:
    """Fail unless this process converts timestamps in UTC (see the module docstring)."""
    if datetime.fromtimestamp(0) != datetime(1970, 1, 1):
        raise RuntimeError(
            "the process time zone is not UTC; set TZ=UTC and call time.tzset() before importing "
            "google_play_scraper, or converted review dates will depend on the machine"
        )


def _epoch(item: list[Any], path: tuple[int, ...]) -> int | None:
    value: Any = item
    try:
        for index in path:
            value = value[index]
    except (IndexError, TypeError):
        return None
    return int(value) if value is not None else None


def make_fetch(
    app_id: str, lang: str, country: str, page_size: int, newest_first: bool = True
) -> Fetch:
    """Return a function that fetches one page; errors propagate instead of ending the run."""
    assert_utc_process()
    from google_play_scraper import Sort
    from google_play_scraper.constants.element import ElementSpecs
    from google_play_scraper.constants.request import Formats
    from google_play_scraper.features.reviews import _fetch_review_items

    url = Formats.Reviews.build(lang=lang, country=country)
    sort = (Sort.NEWEST if newest_first else Sort.MOST_RELEVANT).value

    def fetch(token: str | None) -> tuple[list[Row], str | None]:
        items, next_token = _fetch_review_items(url, app_id, sort, page_size, None, None, token)
        rows = []
        for item in items:
            row = {key: spec.extract_content(item) for key, spec in ElementSpecs.Review.items()}
            row["at_epoch"] = _epoch(item, (5, 0))
            row["replied_at_epoch"] = _epoch(item, (7, 2, 0))
            rows.append(row)
        # The library treats a list-shaped token as "no more pages".
        return rows, next_token if isinstance(next_token, str) else None

    return fetch


@dataclass
class CollectionState:
    """Progress of one collection run; also what a resumed run starts from."""

    pages: int = 0
    reviews: int = 0
    retries: int = 0
    stop_reason: str | None = None
    last_error: str | None = None
    page_seconds: list[float] = field(default_factory=list)


def collect(
    fetch: Fetch,
    *,
    on_checkpoint: Checkpoint,
    start_token: str | None = None,
    state: CollectionState | None = None,
    max_pages: int | None = None,
    checkpoint_pages: int = 50,
    pause_seconds: float = 0.5,
    max_retries: int = 5,
    backoff_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> CollectionState:
    """Page through reviews until the history ends, a page limit, or repeated errors.

    Rows are handed to `on_checkpoint` every `checkpoint_pages` pages and once at the end, with the
    token to resume from, so a failure late in a long run loses at most one checkpoint of work.
    Whatever stopped the run is recorded in `state.stop_reason`; only `end_of_history` means the
    whole available history was collected.
    """
    state = state or CollectionState()
    token = start_token
    buffer: list[Row] = []
    pages_this_run = 0

    while True:
        if max_pages is not None and pages_this_run >= max_pages:
            state.stop_reason = MAX_PAGES
            break

        rows: list[Row] | None = None
        next_token: str | None = None
        for attempt in range(max_retries + 1):
            started = time.monotonic()
            try:
                rows, next_token = fetch(token)
                state.page_seconds.append(time.monotonic() - started)
                break
            except Exception as error:  # every failure is retried, then recorded
                state.last_error = f"{type(error).__name__}: {error}"[:300]
                if attempt == max_retries:
                    break
                state.retries += 1
                sleep(backoff_seconds * 2**attempt)
        if rows is None:
            state.stop_reason = ERROR_AFTER_RETRIES
            break

        pages_this_run += 1
        state.pages += 1
        state.reviews += len(rows)
        buffer.extend(rows)

        if next_token is None:
            state.stop_reason = END_OF_HISTORY
            break
        if not rows:
            state.stop_reason = EMPTY_PAGE_WITH_TOKEN
            break
        token = next_token

        if pages_this_run % checkpoint_pages == 0:
            on_checkpoint(buffer, token, state)
            buffer = []
        sleep(pause_seconds)

    # The resume token after a stop is the last one that has not been fetched successfully.
    resume_token = None if state.stop_reason == END_OF_HISTORY else token
    on_checkpoint(buffer, resume_token, state)
    return state

"""Collect gov.br app reviews from Google Play into data/raw/<run_id>/.

    python scripts/collect_reviews.py --max-pages 50          # pilot
    python scripts/collect_reviews.py                         # whole available history
    python scripts/collect_reviews.py --resume data/raw/<run_id>

The process time zone is forced to UTC before google_play_scraper is imported, because the library
converts review dates with the local time zone (see govbr_classifier/data/collect.py).
"""

import os
import time

os.environ["TZ"] = "UTC"
time.tzset()

import argparse  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
from importlib.metadata import version  # noqa: E402
from pathlib import Path  # noqa: E402

from govbr_classifier.data.collect import collect, make_fetch  # noqa: E402
from govbr_classifier.data.raw_store import RawRun  # noqa: E402
from govbr_classifier.settings import PROJECT_ROOT, get_settings  # noqa: E402


def app_snapshot(app_id: str, lang: str, country: str) -> dict[str, object]:
    """Store-page numbers at collection time, to compare with what the run actually reached."""
    from google_play_scraper import app

    details = app(app_id, lang=lang, country=country)
    keys = ("title", "developer", "version", "released", "realInstalls", "ratings", "reviews")
    return {key: details.get(key) for key in keys}


def main() -> int:
    """Run or resume a collection and print where it stopped."""
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--pause", type=float, default=0.5, help="seconds between pages")
    parser.add_argument("--checkpoint-pages", type=int, default=50)
    parser.add_argument("--resume", type=Path, default=None, help="run directory to continue")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "data" / "raw")
    args = parser.parse_args()

    app_id, lang, country = settings.play_app_id, settings.play_lang, settings.play_country
    parameters = {
        "app_id": app_id,
        "lang": lang,
        "country": country,
        "sort": "newest",
        "page_size": args.page_size,
        "pause_seconds": args.pause,
        "max_pages": args.max_pages,
    }
    if args.resume:
        run = RawRun(args.resume)
        token, state = run.resume_point()
        if token is None:
            print("nothing to resume: this run already reached the end of the history")
            return 1
    else:
        environment = {
            "google_play_scraper": version("google-play-scraper"),
            "python": platform.python_version(),
            "process_tz": "UTC",
            "app_snapshot": app_snapshot(app_id, lang, country),
        }
        run = RawRun.create(args.out, parameters, environment)
        token, state = None, None

    print(f"run directory: {run.run_dir}")
    fetch = make_fetch(app_id, lang, country, args.page_size)
    started = time.monotonic()
    final = collect(
        fetch,
        on_checkpoint=run.checkpoint,
        start_token=token,
        state=state,
        max_pages=args.max_pages,
        checkpoint_pages=args.checkpoint_pages,
        pause_seconds=args.pause,
    )
    metadata = run.finish(
        final,
        {"parameters": parameters, "seconds": round(time.monotonic() - started, 1)},
    )
    print(
        f"stop_reason={metadata['stop_reason']} pages={metadata['pages']} "
        f"rows_on_disk={metadata['rows_on_disk']} retries={metadata['retries']} "
        f"window={metadata['review_window_utc']}"
    )
    return 0 if final.stop_reason in ("end_of_history", "max_pages") else 1


if __name__ == "__main__":
    sys.exit(main())

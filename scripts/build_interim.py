"""Build data/interim/reviews.parquet from one or more raw collection runs.

    python scripts/build_interim.py data/raw/<run_id>
    python scripts/build_interim.py data/raw/<pilot_id> --allow-incomplete   # partial history

A run that did not reach the end of the history is refused unless --allow-incomplete is given, and
the metadata then says the interim table does not cover the whole history.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from govbr_classifier.data.interim import build_interim
from govbr_classifier.data.raw_store import RawRun
from govbr_classifier.settings import PROJECT_ROOT


def main() -> int:
    """Build the interim table and its metadata, and print the step statistics."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", type=Path, nargs="+")
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "data" / "interim")
    args = parser.parse_args()

    frames, sources = [], []
    for run_dir in args.runs:
        run = RawRun(run_dir)
        metadata = json.loads(run.metadata_path.read_text())
        if metadata["status"] != "complete" and not args.allow_incomplete:
            print(f"refusing {run_dir}: status={metadata['status']} ({metadata['stop_reason']})")
            return 1
        frames.append(run.load())
        sources.append(
            {key: metadata.get(key) for key in ("run_id", "status", "stop_reason", "pages")}
        )

    interim, stats = build_interim(pd.concat(frames, ignore_index=True))
    args.out.mkdir(parents=True, exist_ok=True)
    interim.to_parquet(args.out / "reviews.parquet", index=False)
    metadata = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "complete_history": all(s["status"] == "complete" for s in sources),
        "sources": sources,
        "stats": stats,
    }
    (args.out / "reviews.metadata.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

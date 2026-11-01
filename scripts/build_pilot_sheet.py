"""Build the pilot annotation spreadsheet from data/pilot/link.csv.

    python scripts/build_pilot_sheet.py               # data/pilot/pilot_annotation.xlsx
    python scripts/build_pilot_sheet.py --blind-copy  # data/pilot/pilot_annotation_blind.xlsx

Prints counts and item ids only, never text. Refuses to overwrite an existing file, since it may
already hold annotations.
"""

import argparse
from pathlib import Path

import pandas as pd

from govbr_classifier.annotation.pilot import PILOT_DIR
from govbr_classifier.annotation.spreadsheet import (
    BLIND_PATH,
    LOST_ON_IMPORT,
    POST_IMPORT_STEPS,
    RUBRIC_PATH,
    SHEET_PATH,
    build_items,
    write_workbook,
)
from govbr_classifier.settings import PROJECT_ROOT


def main() -> int:
    """Mask the 50 texts, report, and write the workbook."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--blind-copy", action="store_true", help="same items, no annotations")
    parser.add_argument("--link", type=Path, default=PILOT_DIR / "link.csv")
    parser.add_argument(
        "--interim", type=Path, default=PROJECT_ROOT / "data" / "interim" / "reviews.parquet"
    )
    parser.add_argument("--out-dir", type=Path, default=SHEET_PATH.parent)
    args = parser.parse_args()

    link = pd.read_csv(args.link, dtype={"review_id": str, "item_id": str})
    reviews = pd.read_parquet(args.interim, columns=["review_id", "text"])
    texts = reviews.set_index("review_id")["text"].fillna("")
    items, report = build_items(link, texts)

    print("items with at least one mask, by type:")
    for kind, count in report.items_masked.items():
        print(f"  {kind}: {count}")
    print(
        f"items with a capitalized word mid-sentence ({len(report.name_item_ids)}), "
        "to read in the .xlsx before importing:"
    )
    print("  " + (", ".join(report.name_item_ids) or "none"))

    path = args.out_dir / (BLIND_PATH if args.blind_copy else SHEET_PATH).name
    write_workbook(items, path, RUBRIC_PATH.read_text(encoding="utf-8"), blind=args.blind_copy)
    print(f"\nwrote {path} ({len(items)} items)")
    print("\nManual steps after importing into Google Sheets:")
    for number, step in enumerate(POST_IMPORT_STEPS, start=1):
        print(f"  {number}. {step}")
    print("\nWhat is lost on import:")
    for item in LOST_ON_IMPORT:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

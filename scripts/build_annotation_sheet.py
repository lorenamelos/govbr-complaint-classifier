"""Build an annotation spreadsheet (layout v4) from a link table: the pilot or a sample wave.

    python scripts/build_annotation_sheet.py --set pilot               # data/pilot/
    python scripts/build_annotation_sheet.py --set pilot --blind-copy  # same, blind copy
    python scripts/build_annotation_sheet.py --set wave1               # data/sample/wave1/

Prints counts and item ids only, never text. Refuses to overwrite an existing file, since it may
already hold annotations.
"""

import argparse
from pathlib import Path

import pandas as pd

from govbr_classifier.annotation.final_sample import SAMPLE_DIR
from govbr_classifier.annotation.pilot import PILOT_DIR
from govbr_classifier.annotation.spreadsheet import (
    BLIND_PATH,
    LOST_ON_IMPORT,
    PILOT_PURPOSE,
    RUBRIC_PATH,
    SHEET_PATH,
    WAVE1_PATH,
    WAVE1_PURPOSE,
    build_items,
    post_import_steps,
    write_workbook,
)
from govbr_classifier.settings import PROJECT_ROOT

SETS = {
    "pilot": (PILOT_DIR / "link.csv", SHEET_PATH, PILOT_PURPOSE),
    "wave1": (SAMPLE_DIR / "wave1" / "link.csv", WAVE1_PATH, WAVE1_PURPOSE),
}


def main() -> int:
    """Mask the texts, report, and write the workbook."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--set", choices=sorted(SETS), default="pilot")
    parser.add_argument("--blind-copy", action="store_true", help="same items, no annotations")
    parser.add_argument("--link", type=Path, help="override the set's link table")
    parser.add_argument(
        "--interim", type=Path, default=PROJECT_ROOT / "data" / "interim" / "reviews.parquet"
    )
    parser.add_argument("--out-dir", type=Path, help="override the set's folder")
    args = parser.parse_args()

    default_link, default_sheet, purpose = SETS[args.set]
    link = pd.read_csv(args.link or default_link, dtype={"review_id": str, "item_id": str})
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

    name = BLIND_PATH.name if args.blind_copy else default_sheet.name
    path = (args.out_dir or default_sheet.parent) / name
    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    write_workbook(items, path, rubric, blind=args.blind_copy, purpose=purpose)
    print(f"\nwrote {path} ({len(items)} items)")
    print("\nManual steps after importing into Google Sheets:")
    for number, step in enumerate(post_import_steps(len(items)), start=1):
        print(f"  {number}. {step}")
    print("\nWhat is lost on import:")
    for item in LOST_ON_IMPORT:
        print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

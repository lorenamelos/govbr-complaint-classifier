"""Draw wave 1 of the final annotation sample and write the manifest and the link table.

    python scripts/select_wave1.py                # seed 20261110, writes data/sample/wave1/
    python scripts/select_wave1.py --dry-run      # strata and allocation only, writes nothing

Prints counts only, never review text. The universe is every unique text minus the 50 pilot texts
(by text key). The manifest records, per item, the stratum (rating|signal group), the selection
probability, the wave and the signal that directed it; none of this goes to the spreadsheet.
"""

import argparse
from pathlib import Path

import pandas as pd

from govbr_classifier.annotation.final_sample import (
    MANIFEST_COLUMNS,
    SAMPLE_DIR,
    WAVE1_SEED,
    add_signals,
    allocate,
    select_wave,
    stratum_sizes,
)
from govbr_classifier.annotation.pilot import pilot_excluded_texts, unique_texts
from govbr_classifier.guards.text_quality import has_letters_or_digits
from govbr_classifier.settings import PROJECT_ROOT

LINK_COLUMNS = [
    *MANIFEST_COLUMNS,
    "score",
    "original_length",
    "copies",
    "ratings",
    "guard_low_text_quality",
    "guard_language",
    "guard_off_domain",
]


def main() -> int:
    """Draw wave 1, write data/sample/wave1/, and print the counts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=WAVE1_SEED)
    parser.add_argument(
        "--interim", type=Path, default=PROJECT_ROOT / "data" / "interim" / "reviews.parquet"
    )
    parser.add_argument("--out", type=Path, default=SAMPLE_DIR / "wave1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest_path = args.out / "manifest.csv"
    if manifest_path.exists() and not args.dry_run:
        raise FileExistsError(f"{manifest_path} exists; a drawn wave is never redrawn in place.")

    reviews = pd.read_parquet(args.interim, columns=["review_id", "text", "score", "at"])
    every_text = unique_texts(reviews)
    excluded = pilot_excluded_texts()
    universe = add_signals(every_text[~every_text["text_key"].isin(excluded)].copy())
    print(
        f"universe: {len(universe):,} unique texts "
        f"({len(every_text):,} minus {int(every_text['text_key'].isin(excluded).sum())} pilot)"
    )

    sizes = stratum_sizes(universe)
    random_part, targeted = allocate(sizes)
    counts = random_part + targeted
    print("\nN_h, unique texts per stratum (rating x signal group):")
    print(sizes.to_string())
    print("\nn_h, items drawn per stratum (random part + targeted part):")
    print(counts.assign(total=counts.sum(axis=1)).to_string())
    print(f"total: {int(counts.to_numpy().sum())}")

    if args.dry_run:
        return 0

    sample = select_wave(universe, wave=1, seed=args.seed, prefix="w1_")
    sample["original_length"] = sample["text"].str.len()
    sample["guard_low_text_quality"] = [
        "classified" if has_letters_or_digits(text) else "low_text_quality"
        for text in sample["text"]
    ]
    sample["guard_language"] = "not_built"
    sample["guard_off_domain"] = "not_built"

    args.out.mkdir(parents=True, exist_ok=True)
    sample.loc[:, list(MANIFEST_COLUMNS)].to_csv(manifest_path, index=False)
    sample[LINK_COLUMNS].to_csv(args.out / "link.csv", index=False)

    drawn = pd.crosstab(sample["rating_stratum"], sample["signal"].replace("", "sem_sinal"))
    print("\ndrawn, per rating and signal group:")
    print(drawn.to_string())
    print("API guard on the wave:", sample["guard_low_text_quality"].value_counts().to_dict())
    print(f"\nwrote {manifest_path} and {args.out / 'link.csv'} (seed {args.seed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

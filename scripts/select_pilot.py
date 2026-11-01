"""Select the 50 items of the annotation pilot and write the manifest and the link table.

    python scripts/select_pilot.py            # seed 20261101, writes data/pilot/
    python scripts/select_pilot.py --seed 7   # another draw, for comparison only

Prints counts only, never review text. The manifest (item_id, review_id, text_key, origin, stratum,
selection probability, stress rule, use) is what keeps the pilot out of the final sample; the link
table adds the rating, the original length and the API guard result.
"""

import argparse
from pathlib import Path

import pandas as pd

from govbr_classifier.annotation.pilot import (
    MANIFEST_PATH,
    OTHER_LANGUAGE_REVIEW,
    PILOT_DIR,
    SEED,
    STRESS_RULES,
    owner_confirmed_other_language,
    select_pilot,
    unique_texts,
    write_manifest,
)
from govbr_classifier.guards.text_quality import has_letters_or_digits
from govbr_classifier.settings import PROJECT_ROOT

LINK_COLUMNS = [
    "item_id",
    "review_id",
    "text_key",
    "score",
    "stratum",
    "selection_probability",
    "origin",
    "stress_rule",
    "original_length",
    "copies",
    "ratings",
    "guard_low_text_quality",
    "guard_language",
    "guard_off_domain",
]


def main() -> int:
    """Select the pilot, write data/pilot/, and print the counts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--interim", type=Path, default=PROJECT_ROOT / "data" / "interim" / "reviews.parquet"
    )
    parser.add_argument("--out", type=Path, default=PILOT_DIR)
    args = parser.parse_args()

    reviews = pd.read_parquet(args.interim, columns=["review_id", "text", "score", "at"])
    universe = unique_texts(reviews)
    confirmed = owner_confirmed_other_language(OTHER_LANGUAGE_REVIEW)
    pilot = select_pilot(universe, confirmed, seed=args.seed)

    pilot["original_length"] = pilot["text"].str.len()
    pilot["guard_low_text_quality"] = [
        "classified" if has_letters_or_digits(text) else "low_text_quality"
        for text in pilot["text"]
    ]
    pilot["guard_language"] = "not_built"
    pilot["guard_off_domain"] = "not_built"

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = args.out / MANIFEST_PATH.name
    write_manifest(pilot, manifest)
    pilot[LINK_COLUMNS].to_csv(args.out / "link.csv", index=False)

    print(f"universe: {len(universe):,} unique texts from {len(reviews):,} reviews")
    print(
        f"unique texts with more than one distinct rating: {int((universe['ratings'] > 1).sum()):,}"
    )
    per_stratum = universe["stratum"].value_counts().sort_index()
    print("unique texts per stratum:", {int(k): int(v) for k, v in per_stratum.items()})
    remaining = universe[
        ~universe["text_key"].isin(pilot.loc[pilot["origin"].eq("aleatorio"), "text_key"])
    ]
    for rule in STRESS_RULES:
        print(f"stress pool {rule.name}: {int(remaining['text'].map(rule.matches).sum()):,}")
    print(f"stress pool other_language_owner_confirmed: {len(confirmed)} confirmed ids")
    print("\nitems per origin:", pilot["origin"].value_counts().to_dict())
    print(pd.crosstab(pilot["origin"], pilot["stratum"], margins=True).to_string())
    print(
        "\nstress items per rule:", pilot["stress_rule"].replace("", "-").value_counts().to_dict()
    )
    print("API guard on the pilot:", pilot["guard_low_text_quality"].value_counts().to_dict())
    print(f"\nwrote {manifest} and {args.out / 'link.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

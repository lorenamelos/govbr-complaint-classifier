"""Validate a pilot annotation pass and print its summary, without any review text.

    python scripts/summarize_pilot.py data/pilot/annotations_pass1.xlsx --require-complete

Stops at the strict reader's first report: every broken rule, by item_id and column. The notes in
nota_duvida are the annotator's own and are printed, grouped by doubt category.
"""

import argparse
from pathlib import Path

import pandas as pd

from govbr_classifier.annotation.reader import LINK_PATH, AnnotationError, read_annotations
from govbr_classifier.annotation.summary import (
    ACTIONABLE_WARNING,
    DOUBT_SHARE,
    attribute_counts,
    read_sessions,
    time_items,
    time_stats,
)


def main() -> int:
    """Read strictly, then summarize."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--link", type=Path, default=LINK_PATH)
    args = parser.parse_args()

    try:
        result = read_annotations(args.path, args.link, require_complete=args.require_complete)
    except AnnotationError as error:
        print(f"REJECTED: {len(error.problems)} problem(s) (item_id | column | rule)")
        for problem in error.problems:
            print(f"  {problem}")
        return 1

    frame = result.frame
    link = pd.read_csv(args.link, dtype={"item_id": str}).set_index("item_id")
    annotated = frame[frame["status"].eq("annotated")]
    print(f"OK: {len(annotated)} annotated, {len(result.pending)} pending {result.pending or ''}")

    print("\n== ood_manual against the API guard (language and off_domain are not built)")
    guard = annotated["item_id"].map(link["guard_low_text_quality"])
    print(pd.crosstab(annotated["ood_manual"], guard, margins=True).to_string())

    print("\n== attributes among items with ood_manual = nao")
    for name, counts in attribute_counts(annotated).items():
        print(f"-- {name}\n{counts.to_string()}")

    inside = annotated[annotated["ood_manual"].eq("nao")]
    share = inside["acionabilidade"].eq("sim").mean()
    flag = "  WARNING: above 80%" if share > ACTIONABLE_WARNING else ""
    print(f"\n== acionabilidade = sim: {share:.0%} of {len(inside)}{flag}")

    print(f"\n== duvida (share of {len(annotated)} annotated items)")
    doubts = annotated["duvida"].replace("", pd.NA).dropna().value_counts()
    for category, count in doubts.items():
        mark = "  > 10%" if count / len(annotated) > DOUBT_SHARE else ""
        print(f"  {category}: {count} ({count / len(annotated):.0%}){mark}")
    print(f"  no doubt: {int(annotated['duvida'].eq('').sum())}")

    print(f"\n== obrigatoriedade box checked: {int(annotated['obrigatoriedade'].sum())}")
    print("   (examples collected; not a frequency: 2 of the 50 items were picked for it)")

    print("\n== time per item")
    sessions = read_sessions(args.path) if args.path.suffix == ".xlsx" else pd.DataFrame()
    print(f"  sessions in the sessoes sheet: {len(sessions)}")
    if sessions.empty:
        sessions = pd.DataFrame(columns=["session", "start", "end"])
    timing = time_items(annotated, sessions)
    first = timing.intervals[timing.intervals["kind"].eq("first")]
    pauses = timing.intervals[timing.intervals["kind"].eq("pause")]
    if timing.intervals["kind"].eq("interval").any():
        stats = time_stats(timing.intervals, link["original_length"])
        print(stats.round(1).to_string())
    else:
        print("  no timed intervals")
    print(
        "  first item of each session (from inicio): "
        f"{first[['item_id', 'seconds']].to_dict('records')}"
    )
    print(f"  pauses (> 10 min, excluded): {pauses[['item_id', 'seconds']].to_dict('records')}")
    print(f"  no hora_fim ({len(timing.no_time)}): {', '.join(timing.no_time) or 'none'}")
    print(
        f"  outside every session ({len(timing.outside_sessions)}): "
        f"{', '.join(timing.outside_sessions) or 'none'}"
    )

    print("\n== nota_duvida by doubt category (annotator's notes)")
    notes = annotated[annotated["nota_duvida"].str.strip().ne("")]
    for category, group in notes.groupby(notes["duvida"].replace("", "(no doubt marked)")):
        print(f"-- {category}")
        for row in group.itertuples(index=False):
            print(f"  {row.item_id}: {row.nota_duvida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

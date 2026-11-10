"""Validate a pilot annotation pass and print its summary, without any review text.

    python scripts/summarize_pilot.py data/pilot/annotations_pass1.xlsx --require-complete

Reads layout v4 and the v3 layout of the pilot's frozen first pass. Stops at the strict reader's
first report: every broken rule, by item_id and column. The notes in nota_duvida and assunto_outro
are the annotator's own and are printed.
"""

import argparse
from pathlib import Path

import pandas as pd

from govbr_classifier.annotation.reader import LINK_PATH, AnnotationError, read_annotations
from govbr_classifier.annotation.summary import (
    ACTIONABLE_WARNING,
    DOUBT_SHARE,
    PAUSE_MINUTES,
    SESSION_GAP_MINUTES,
    attribute_counts,
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
    print(
        f"OK (layout v{result.version}): {len(annotated)} annotated, "
        f"{len(result.pending)} pending {result.pending or ''}"
    )

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

    print(
        "\n== time per item (APPROXIMATE: sessions inferred from hora_fim, "
        f"gap > {SESSION_GAP_MINUTES} min opens one, gap > {PAUSE_MINUTES} min inside is a pause)"
    )
    timing = time_items(annotated)
    for session in timing.sessions.itertuples(index=False):
        print(
            f"  session {session.session}: {session.start:%Y-%m-%d %H:%M:%S} to "
            f"{session.end:%H:%M:%S}, {session.items} items"
        )
    if timing.intervals["kind"].eq("interval").any():
        stats = time_stats(timing.intervals, link["original_length"])
        print(stats.round(1).to_string())
    else:
        print("  no timed intervals")
    kinds = timing.intervals.groupby("kind")["item_id"].apply(list)
    print(f"  first item of each session (not timed): {kinds.get('first', [])}")
    pauses = timing.intervals[timing.intervals["kind"].eq("pause")]
    print(f"  pauses (excluded): {pauses[['item_id', 'seconds']].to_dict('records')}")
    print(f"  no hora_fim ({len(timing.no_time)}): {', '.join(timing.no_time) or 'none'}")
    if timing.no_time:
        print("  (their time is absorbed into the next timed gap, which reads longer)")

    if result.version >= 4:
        print("\n== assunto_outro (annotator's subjects)")
        subjects = annotated[annotated["assunto_outro"].str.strip().ne("")]
        for row in subjects.itertuples(index=False):
            where = "tema outro" if row.tema_outro else "next to a listed theme"
            print(f"  {row.item_id} ({where}): {row.assunto_outro}")
        if subjects.empty:
            print("  none")

    print("\n== nota_duvida by doubt category (annotator's notes)")
    notes = annotated[annotated["nota_duvida"].str.strip().ne("")]
    for category, group in notes.groupby(notes["duvida"].replace("", "(no doubt marked)")):
        print(f"-- {category}")
        for row in group.itertuples(index=False):
            print(f"  {row.item_id}: {row.nota_duvida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Pilot selection and its exclusion from the final sample. Synthetic reviews only."""

from pathlib import Path

import pandas as pd
import pytest

from govbr_classifier.annotation.pilot import (
    MANIFEST_COLUMNS,
    ORIGIN_RANDOM,
    ORIGIN_STRESS,
    PER_STRATUM,
    final_sample_universe,
    pilot_excluded_texts,
    select_pilot,
    unique_texts,
    write_manifest,
)

T0 = pd.Timestamp("2026-01-01", tz="UTC")


def review(review_id: str, text: str, score: int, days: int = 0) -> dict[str, object]:
    return {
        "review_id": review_id,
        "text": text,
        "score": score,
        "at": T0 + pd.Timedelta(days=days),
    }


def synthetic_reviews() -> pd.DataFrame:
    rows = []
    for score in range(1, 6):
        rows += [
            review(f"r{score}-{i}", f"texto comum nota {score} numero {i}", score)
            for i in range(20)
        ]
    rows += [review(f"pw{i}", f"atendimento otimo caso {i}", 5) for i in range(12)]
    rows += [review(f"em{i}", f"pessimo demais {i} !!!!!!", 1) for i in range(12)]
    rows += [review(f"tr{i}", f"{i} " + "x" * (500 - len(f"{i} ")), 2) for i in range(12)]
    rows += [review(f"ob{i}", f"me obrigam a usar caso {i}", 1) for i in range(12)]
    rows += [review(f"co{i}", f"colocam a gente para fazer caso {i}", 1) for i in range(12)]
    rows += [
        review(f"emo{i}", mark, 1)
        for i, mark in enumerate(["👍", "😡😡", "!!!", "???", "🙏", "...", "👎", "?!"])
    ]
    rows += [review(f"en{i}", f"very good app number {i}", 5) for i in range(12)]
    return pd.DataFrame(rows)


ENGLISH_IDS = ["en0", "en1", "en2"]


@pytest.fixture(scope="module")
def universe() -> pd.DataFrame:
    return unique_texts(synthetic_reviews())


@pytest.fixture(scope="module")
def pilot(universe: pd.DataFrame) -> pd.DataFrame:
    return select_pilot(universe, ENGLISH_IDS, seed=7)


def test_stratum_is_the_most_frequent_rating_lowest_on_a_tie() -> None:
    reviews = pd.DataFrame(
        [
            review("a", "ok", 5),
            review("b", "OK!", 5),
            review("c", "ok", 4),
            review("d", "bom", 4),
            review("e", "Bom", 2),
        ]
    )
    table = unique_texts(reviews).set_index("text_key")
    assert table.loc["ok", "stratum"] == 5
    assert table.loc["bom", "stratum"] == 2  # one 4 and one 2: tie, lowest wins
    assert table.loc["ok", "copies"] == 3
    assert table.loc["ok", "ratings"] == 2


def test_representative_is_the_most_recent_copy() -> None:
    reviews = pd.DataFrame(
        [review("old", "Não abre", 1, days=0), review("new", "nao abre!", 1, days=9)]
    )
    assert unique_texts(reviews).loc[0, "review_id"] == "new"


def test_forty_random_items_eight_per_stratum(pilot: pd.DataFrame, universe: pd.DataFrame) -> None:
    random_items = pilot[pilot["origin"].eq(ORIGIN_RANDOM)]
    assert len(random_items) == 40
    assert random_items["stratum"].value_counts().to_dict() == {s: PER_STRATUM for s in range(1, 6)}
    sizes = universe["stratum"].value_counts()
    for stratum, probability in (
        random_items.groupby("stratum")["selection_probability"].first().items()
    ):
        assert probability == pytest.approx(PER_STRATUM / sizes[stratum])


def test_ten_stress_items_by_rule_without_probability(pilot: pd.DataFrame) -> None:
    stress = pilot[pilot["origin"].eq(ORIGIN_STRESS)]
    assert len(stress) == 10
    assert stress["selection_probability"].isna().all()
    assert stress["stress_rule"].value_counts().to_dict() == {
        "praise_with_theme": 2,
        "emphasis": 2,
        "truncated_500": 2,
        "obligation_obrigam": 1,
        "obligation_colocam": 1,
        "emoji_or_punctuation_only": 1,
        "other_language_owner_confirmed": 1,
    }
    english = stress[stress["stress_rule"].eq("other_language_owner_confirmed")]
    assert english["review_id"].iloc[0] in ENGLISH_IDS


def test_no_text_is_picked_twice_and_ids_are_opaque(pilot: pd.DataFrame) -> None:
    assert pilot["text_key"].is_unique
    assert pilot["item_id"].tolist() == [f"p{i:03d}" for i in range(1, 51)]


def test_same_seed_same_pilot_other_seed_other_pilot(universe: pd.DataFrame) -> None:
    first = select_pilot(universe, ENGLISH_IDS, seed=7)
    again = select_pilot(universe, ENGLISH_IDS, seed=7)
    other = select_pilot(universe, ENGLISH_IDS, seed=8)
    pd.testing.assert_frame_equal(first, again)
    assert first["text_key"].tolist() != other["text_key"].tolist()


def test_order_is_shuffled_not_grouped(pilot: pd.DataFrame) -> None:
    assert pilot["origin"].tolist() != sorted(pilot["origin"].tolist())


def test_too_few_candidates_fails_loudly(universe: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="other_language"):
        select_pilot(universe, ["no-such-id"], seed=7)


def test_pilot_texts_never_return_to_the_final_universe(
    pilot: pd.DataFrame, tmp_path: Path
) -> None:
    manifest = tmp_path / "manifest.csv"
    write_manifest(pilot, manifest)
    excluded = pilot_excluded_texts(manifest)
    assert len(excluded) == 50

    picked = pilot.iloc[0]
    later = pd.DataFrame(
        [
            # The same text under another review_id, written differently, collected after the pilot.
            {"review_id": "collected-later", "text": picked["text"].upper() + "  !!", "score": 3},
            {"review_id": picked["review_id"], "text": picked["text"], "score": 3},
            {"review_id": "fresh", "text": "um texto que nunca esteve no piloto", "score": 1},
        ]
    )
    remaining = final_sample_universe(later, excluded)
    assert remaining["review_id"].tolist() == ["fresh"]


def test_manifest_has_the_text_key_and_the_use(pilot: pd.DataFrame, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    write_manifest(pilot, manifest)
    table = pd.read_csv(manifest, dtype=str, keep_default_na=False)
    assert tuple(table.columns) == MANIFEST_COLUMNS
    assert set(table["use"]) == {"reanotacao_apenas"}


def test_a_tampered_manifest_is_refused(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame({"review_id": ["x"]}).to_csv(manifest, index=False)
    with pytest.raises(ValueError, match="columns"):
        pilot_excluded_texts(manifest)

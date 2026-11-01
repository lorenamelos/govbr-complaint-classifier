"""Select the 50 items of the annotation pilot and keep them out of the final sample.

The unit is the unique text (`data.text_key.text_key`). Each unique text belongs to one rating
stratum: the most frequent rating among its copies, the lowest on a tie. The pilot is:

- 40 random items, 8 per stratum, drawn by simple random sampling within the stratum from the full
  universe. Each carries its selection probability, 8 / number of unique texts in the stratum.
- 10 stress items chosen by fixed rules, drawn after the random ones from what is left, with no
  selection probability (they never enter weighted estimates).

The pilot is re-annotated weeks later to measure self-agreement and never enters the test set.
The final sample is drawn from the universe minus every copy of these 50 texts, by text key, so a
copy with another review_id, even one collected later, can never come back (ADR-07).
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from govbr_classifier.data.text_key import text_key
from govbr_classifier.models.keyword_baseline import TEMA_KEYWORDS, normalize, predict_tema
from govbr_classifier.settings import PROJECT_ROOT

PILOT_DIR = PROJECT_ROOT / "data" / "pilot"
MANIFEST_PATH = PILOT_DIR / "manifest.csv"
OTHER_LANGUAGE_REVIEW = PROJECT_ROOT / "data" / "review" / "other_language.csv"

SEED = 20261101
PER_STRATUM = 8
STRATA = (1, 2, 3, 4, 5)
ORIGIN_RANDOM = "aleatorio"
ORIGIN_STRESS = "estresse"
USE = "reanotacao_apenas"
TRUNCATED_LENGTH = 500

MANIFEST_COLUMNS = (
    "item_id",
    "review_id",
    "text_key",
    "origin",
    "stratum",
    "selection_probability",
    "stress_rule",
    "use",
)

_REPEATED_CHAR = re.compile(r"(.)\1{5,}")
_REPEATED_PUNCTUATION = re.compile(r"[!?.]{3,}")
_WORDS = re.compile(r"\w+")


def unique_texts(reviews: pd.DataFrame) -> pd.DataFrame:
    """One row per unique text: key, stratum, copies and a representative review.

    The representative is the most recently dated copy (ties broken by review_id); its raw text is
    what the annotator reads. Blank texts have no key and are not part of the universe.
    """
    frame = reviews[["review_id", "text", "score", "at"]].copy()
    frame["text"] = frame["text"].fillna("")
    frame["text_key"] = frame["text"].map(text_key)
    frame = frame[frame["text_key"].ne("")]

    counts = frame.groupby(["text_key", "score"]).size().rename("n").reset_index()
    counts = counts.sort_values(["text_key", "n", "score"], ascending=[True, False, True])
    stratum = counts.drop_duplicates("text_key").set_index("text_key")["score"].rename("stratum")

    representative = (
        frame.sort_values(["text_key", "at", "review_id"], ascending=[True, False, True])
        .drop_duplicates("text_key")
        .set_index("text_key")[["review_id", "text", "score", "at"]]
    )
    table = representative.join(stratum)
    table["copies"] = frame.groupby("text_key").size()
    table["ratings"] = frame.groupby("text_key")["score"].nunique()
    return table.reset_index()


def _praise_terms() -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(rf"\b{re.escape(term)}\b") for term in TEMA_KEYWORDS["nenhum"])


_PRAISE = _praise_terms()


def _praise_with_theme(text: str) -> bool:
    """A praise word and a problem theme in one text, the shape of "atendimento ótimo"."""
    normalized = normalize(text)
    if not any(pattern.search(normalized) for pattern in _PRAISE):
        return False
    labels, _ = predict_tema(text)
    return any(label != "nenhum" for label in labels)


def _emphasis(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    mostly_caps = (
        len(letters) >= 10 and sum(char.isupper() for char in letters) / len(letters) > 0.8
    )
    return bool(_REPEATED_CHAR.search(text) or _REPEATED_PUNCTUATION.search(text)) or mostly_caps


def _has_word(word: str) -> Callable[[str], bool]:
    return lambda text: word in _WORDS.findall(normalize(text))


def _no_word(text: str) -> bool:
    return not _WORDS.search(text)


@dataclass(frozen=True)
class StressRule:
    """A named rule for picking stress items."""

    name: str
    count: int
    matches: Callable[[str], bool]


STRESS_RULES = (
    StressRule("praise_with_theme", 2, _praise_with_theme),
    StressRule("emphasis", 2, _emphasis),
    StressRule("truncated_500", 2, lambda text: len(text) == TRUNCATED_LENGTH),
    StressRule("obligation_obrigam", 1, _has_word("obrigam")),
    StressRule("obligation_colocam", 1, _has_word("colocam")),
    StressRule("emoji_or_punctuation_only", 1, _no_word),
)
OTHER_LANGUAGE_RULE = "other_language_owner_confirmed"


def _draw(rng: np.random.Generator, keys: Iterable[str], count: int, rule: str) -> list[str]:
    """Draw `count` keys without replacement from a sorted pool, failing if it is too small."""
    pool = sorted(keys)
    if len(pool) < count:
        raise ValueError(f"rule {rule}: {len(pool)} candidates, {count} needed")
    return [str(key) for key in rng.choice(pool, size=count, replace=False)]


def select_pilot(
    universe: pd.DataFrame, other_language_ids: Iterable[str], seed: int = SEED
) -> pd.DataFrame:
    """Return the 50 pilot items, shuffled, with item ids p001 to p050.

    `universe` is the output of `unique_texts`. `other_language_ids` are review ids the owner
    confirmed as another language; the language stress item comes from their texts.
    """
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    taken: set[str] = set()

    for stratum in STRATA:
        pool = universe.loc[universe["stratum"].eq(stratum), "text_key"]
        for key in _draw(rng, pool, PER_STRATUM, f"stratum {stratum}"):
            rows.append(
                {
                    "text_key": key,
                    "origin": ORIGIN_RANDOM,
                    "stratum": stratum,
                    "selection_probability": PER_STRATUM / len(pool),
                    "stress_rule": "",
                }
            )
            taken.add(key)

    remaining = universe[~universe["text_key"].isin(taken)]
    for rule in STRESS_RULES:
        candidates = remaining.loc[remaining["text"].map(rule.matches), "text_key"]
        for key in _draw(rng, set(candidates) - taken, rule.count, rule.name):
            rows.append({"text_key": key, "origin": ORIGIN_STRESS, "stress_rule": rule.name})
            taken.add(key)

    confirmed = set(other_language_ids)
    candidates = remaining.loc[remaining["review_id"].isin(confirmed), "text_key"]
    for key in _draw(rng, set(candidates) - taken, 1, OTHER_LANGUAGE_RULE):
        rows.append({"text_key": key, "origin": ORIGIN_STRESS, "stress_rule": OTHER_LANGUAGE_RULE})
        taken.add(key)

    picked = pd.DataFrame(rows)
    picked = picked.merge(universe, on="text_key", how="left", suffixes=("", "_universe"))
    picked["stratum"] = picked["stratum_universe"]
    picked = picked.drop(columns="stratum_universe")
    picked = picked.iloc[rng.permutation(len(picked))].reset_index(drop=True)
    picked.insert(0, "item_id", [f"p{i:03d}" for i in range(1, len(picked) + 1)])
    picked["use"] = USE
    return picked


def owner_confirmed_other_language(path: Path = OTHER_LANGUAGE_REVIEW) -> list[str]:
    """Review ids the owner labeled true_positive in the other_language review file."""
    table = pd.read_csv(path, dtype=str, keep_default_na=False)
    return table.loc[table["owner_label"].eq("true_positive"), "review_id"].tolist()


def write_manifest(pilot: pd.DataFrame, path: Path = MANIFEST_PATH) -> None:
    """Write the exclusion manifest. It is the source of `pilot_excluded_texts`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pilot.loc[:, list(MANIFEST_COLUMNS)].to_csv(path, index=False)


def pilot_excluded_texts(path: Path = MANIFEST_PATH) -> frozenset[str]:
    """Text keys of the 50 pilot items. The final sampler drops every review with one of them."""
    manifest = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(manifest.columns) != list(MANIFEST_COLUMNS):
        raise ValueError(f"{path.name}: unexpected columns {list(manifest.columns)}")
    if manifest["text_key"].eq("").any() or manifest["text_key"].duplicated().any():
        raise ValueError(f"{path.name}: empty or duplicated text_key")
    return frozenset(manifest["text_key"])


def final_sample_universe(reviews: pd.DataFrame, excluded: frozenset[str]) -> pd.DataFrame:
    """The reviews the final sample may draw from: every copy of a pilot text removed.

    Exclusion is by text key, so a pilot text that reappears under another review_id, including one
    collected after the pilot, is still out. Selection probabilities of the final sample are
    computed on this reduced universe.
    """
    keys = reviews["text"].fillna("").map(text_key)
    return reviews[~keys.isin(excluded)]

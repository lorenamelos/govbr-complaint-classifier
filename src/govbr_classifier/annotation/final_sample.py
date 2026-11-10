"""Draw a wave of the final annotation sample: stratified by rating and signal group.

The unit is the unique text (`pilot.unique_texts`), and the universe excludes every pilot text by
text key (`pilot.pilot_excluded_texts`). Each text falls in exactly one stratum, rating x signal
group, so its inclusion probability is well defined: n_h / N_h, with one simple random draw per
stratum.

Signal groups point at the rare classes of the pilot. A text with several signals goes to the
rarest group, in SIGNAL_ORDER; a text with none goes to NO_SIGNAL.

- atendimento, travamento: the keyword baseline terms for that theme.
- servico_nao_carrega: the baseline terms minus "nao funciona", which the rubric labels
  nao_especificado when it has no subject.
- pedido_funcionalidade: FEATURE_REQUEST_TERMS, a list reviewed by the owner. The forms of
  "falta" are left out (mostly "falta de respeito"), and "deveria(m) ter" followed by zero,
  nenhuma, menos or 0 estrela(s) does not count.

The n_h of a stratum adds two allocations, both by largest remainder:

- random part: PER_RATING items per rating, split across the groups of that rating in proportion
  to their size, as if the rating stratum were drawn alone;
- targeted part: PER_SIGNAL items per signal group, split across ratings in proportion to size.

Signals are a sampling device, never a label. The precision of each signal is measured on the
annotated wave and decides the design of the next one.
"""

import re

import numpy as np
import pandas as pd

from govbr_classifier.models.keyword_baseline import TEMA_KEYWORDS, normalize
from govbr_classifier.settings import PROJECT_ROOT

SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
WAVE1_SEED = 20261110
PER_RATING = 40
PER_SIGNAL = 25
RATINGS = (1, 2, 3, 4, 5)
NO_SIGNAL = "sem_sinal"

FEATURE_REQUEST_TERMS = (
    "poderia ter",
    "poderiam ter",
    "poderia colocar",
    "poderiam colocar",
    "poderiam adicionar",
    "deveria ter",
    "deveriam ter",
    "deveriam colocar",
    "devia ter",
    "coloquem",
    "colocar opcao",
    "adicionem",
    "incluam",
    "implementem",
    "seria bom se",
    "seria otimo se",
    "seria legal se",
    "seria bom ter",
    "seria interessante",
    "gostaria que tivesse",
    "queria que tivesse",
    "sugiro",
    "sugestao",
    "modo escuro",
    "tema escuro",
)
# Removed from the text before matching, so "deveria ter zero estrelas" is no request.
NOT_A_REQUEST = re.compile(r"\bdeveriam?\s+ter\s+(?:zero|nenhuma|menos|0)\s+estrelas?\b")
SERVICE_TERMS_LEFT_OUT = ("nao funciona",)

SIGNAL_ORDER = ("pedido_funcionalidade", "atendimento", "travamento", "servico_nao_carrega")
GROUPS = (*SIGNAL_ORDER, NO_SIGNAL)

MANIFEST_COLUMNS = (
    "item_id",
    "review_id",
    "text_key",
    "wave",
    "stratum",
    "rating_stratum",
    "signal",
    "signals_matched",
    "selection_probability",
)


def _compile(term: str) -> re.Pattern[str]:
    """Whole words, any whitespace between them (the baseline's matching rule)."""
    return re.compile(r"\b" + r"\s+".join(re.escape(word) for word in term.split()) + r"\b")


def _signal_patterns() -> dict[str, tuple[re.Pattern[str], ...]]:
    service = [t for t in TEMA_KEYWORDS["servico_nao_carrega"] if t not in SERVICE_TERMS_LEFT_OUT]
    terms = {
        "pedido_funcionalidade": FEATURE_REQUEST_TERMS,
        "atendimento": TEMA_KEYWORDS["atendimento"],
        "travamento": TEMA_KEYWORDS["travamento"],
        "servico_nao_carrega": tuple(service),
    }
    return {name: tuple(map(_compile, terms[name])) for name in SIGNAL_ORDER}


_PATTERNS = _signal_patterns()


def signals(text: str) -> list[str]:
    """Signal groups a text matches, in SIGNAL_ORDER (rarest first)."""
    normalized = normalize(text)
    request_text = NOT_A_REQUEST.sub(" ", normalized)
    found = []
    for name, patterns in _PATTERNS.items():
        target = request_text if name == "pedido_funcionalidade" else normalized
        if any(pattern.search(target) for pattern in patterns):
            found.append(name)
    return found


def _largest_remainder(sizes: pd.Series, total: int) -> pd.Series:
    """Split `total` in proportion to `sizes`, integers summing to `total`."""
    raw = total * sizes / sizes.sum()
    base = np.floor(raw).astype(int)
    order = (raw - base).sort_values(ascending=False, kind="stable").index
    base[order[: total - int(base.sum())]] += 1
    return base


def stratum_sizes(universe: pd.DataFrame) -> pd.DataFrame:
    """N_h: unique texts per rating (rows) and signal group (columns)."""
    table = universe.groupby(["stratum", "signal"]).size().unstack(fill_value=0)
    return table.reindex(index=list(RATINGS), columns=list(GROUPS), fill_value=0)


def allocate(sizes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Random and targeted allocations per stratum; n_h is their sum."""
    random_part = pd.DataFrame(
        {rating: _largest_remainder(sizes.loc[rating], PER_RATING) for rating in sizes.index}
    ).T
    targeted = pd.DataFrame(0, index=sizes.index, columns=sizes.columns)
    for group in SIGNAL_ORDER:
        targeted[group] = _largest_remainder(sizes[group], PER_SIGNAL)
    return random_part, targeted


def add_signals(universe: pd.DataFrame) -> pd.DataFrame:
    """Add `signals_matched` (joined with "|") and `signal`, the stratum group."""
    matched = universe["text"].map(signals)
    return universe.assign(
        signals_matched=matched.map("|".join),
        signal=matched.map(lambda found: found[0] if found else NO_SIGNAL),
    )


def select_wave(universe: pd.DataFrame, wave: int, seed: int, prefix: str) -> pd.DataFrame:
    """Draw one wave, shuffled, with item ids `{prefix}001` onwards.

    `universe` is `add_signals(unique_texts(...))` without the pilot (and without earlier waves).
    """
    rng = np.random.default_rng(seed)
    sizes = stratum_sizes(universe)
    random_part, targeted = allocate(sizes)
    counts = random_part + targeted
    picked = []
    for rating in RATINGS:
        for group in GROUPS:
            n, size = int(counts.loc[rating, group]), int(sizes.loc[rating, group])
            if n == 0:
                continue
            pool = universe[universe["stratum"].eq(rating) & universe["signal"].eq(group)]
            keys = sorted(pool["text_key"])
            chosen = set(rng.choice(keys, size=n, replace=False).tolist())
            drawn = pool[pool["text_key"].isin(chosen)].assign(selection_probability=n / size)
            picked.append(drawn)
    sample = pd.concat(picked).sort_values("text_key")
    sample = sample.iloc[rng.permutation(len(sample))].reset_index(drop=True)
    sample.insert(0, "item_id", [f"{prefix}{i:03d}" for i in range(1, len(sample) + 1)])
    sample["wave"] = wave
    sample["rating_stratum"] = sample["stratum"]
    sample["stratum"] = sample["stratum"].astype(str) + "|" + sample["signal"]
    sample["signal"] = sample["signal"].replace(NO_SIGNAL, "")
    return sample

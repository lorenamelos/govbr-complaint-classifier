"""Wave sampling of the final annotation set: signals, disjoint strata, allocation, probabilities.

Synthetic texts only.
"""

import pandas as pd
import pytest

from govbr_classifier.annotation.final_sample import (
    GROUPS,
    NO_SIGNAL,
    PER_RATING,
    PER_SIGNAL,
    RATINGS,
    SIGNAL_ORDER,
    add_signals,
    allocate,
    select_wave,
    signals,
    stratum_sizes,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("deveria ter modo escuro", ["pedido_funcionalidade"]),
        ("Deveria ter ZERO estrelas", []),
        ("deveriam ter 0 estrela", []),
        ("deveria ter nenhuma estrela, deveria ter modo escuro", ["pedido_funcionalidade"]),
        ("falta de respeito", []),
        ("nao funciona", []),
        ("a carteira não abre", ["servico_nao_carrega"]),
        ("o chat não responde e o app trava", ["atendimento", "travamento"]),
        ("coloquem opção, o app trava", ["pedido_funcionalidade", "travamento"]),
    ],
)
def test_signals(text: str, expected: list[str]) -> None:
    assert signals(text) == expected


def test_a_text_with_several_signals_goes_to_the_rarest_group() -> None:
    universe = pd.DataFrame({"text": ["o chat nao responde e o app trava", "tudo certo"]})
    out = add_signals(universe)
    assert out["signal"].tolist() == ["atendimento", NO_SIGNAL]
    assert out["signals_matched"].tolist() == ["atendimento|travamento", ""]


def synthetic_universe() -> pd.DataFrame:
    texts = {
        "pedido_funcionalidade": "sugiro modo escuro {}",
        "atendimento": "o suporte some {}",
        "travamento": "o app trava {}",
        "servico_nao_carrega": "a pagina nao carrega {}",
        NO_SIGNAL: "texto comum {}",
    }
    rows = []
    for rating in RATINGS:
        for group, template in texts.items():
            size = 60 if group != NO_SIGNAL else 300 + 100 * rating
            for i in range(size):
                text = template.format(f"{rating} {i}")
                rows.append({"text_key": text, "review_id": f"r-{text}", "text": text,
                             "stratum": rating})  # fmt: skip
    return add_signals(pd.DataFrame(rows))


def test_allocation_adds_the_two_parts() -> None:
    sizes = stratum_sizes(synthetic_universe())
    random_part, targeted = allocate(sizes)
    assert (random_part.sum(axis=1) == PER_RATING).all()
    assert (targeted[list(SIGNAL_ORDER)].sum() == PER_SIGNAL).all()
    assert targeted[NO_SIGNAL].sum() == 0
    assert list(sizes.columns) == list(GROUPS)


def test_a_wave_has_one_probability_per_stratum_and_is_reproducible() -> None:
    universe = synthetic_universe()
    sample = select_wave(universe, wave=1, seed=3, prefix="w1_")
    sizes = stratum_sizes(universe)
    random_part, targeted = allocate(sizes)
    counts = random_part + targeted
    assert len(sample) == int(counts.to_numpy().sum())
    assert sample["text_key"].is_unique
    assert sample["item_id"].iloc[0].startswith("w1_")
    assert set(sample["wave"]) == {1}
    for stratum, group in sample.groupby("stratum"):
        rating, signal = stratum.split("|")
        n, size = counts.loc[int(rating), signal], sizes.loc[int(rating), signal]
        assert len(group) == n
        assert group["selection_probability"].eq(n / size).all()
        assert group["signal"].eq("" if signal == NO_SIGNAL else signal).all()
    again = select_wave(universe, wave=1, seed=3, prefix="w1_")
    pd.testing.assert_frame_equal(sample, again)

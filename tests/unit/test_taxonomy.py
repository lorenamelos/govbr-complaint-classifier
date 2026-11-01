"""The taxonomy file is the single source of truth; these tests guard its invariants."""

import pytest

from govbr_classifier.taxonomy import _parse, load_taxonomy

EXPECTED_ATTRIBUTES = {"tema", "bloqueio", "tipo", "acionabilidade"}


def test_exactly_the_four_scoped_attributes() -> None:
    # Scope lock: a new attribute needs evaluation support for the existing four first.
    assert set(load_taxonomy().attributes) == EXPECTED_ATTRIBUTES


def test_tema_has_three_escape_values_and_they_are_exclusive() -> None:
    # ADR-05: outro (subject off the list), nenhum (no complaint), nao_especificado (complaint with
    # no subject, revision of 2026-11-01). Each can only appear alone.
    tema = load_taxonomy().attributes["tema"]
    assert tema.cardinality == "multi"
    assert {"outro", "nenhum", "nao_especificado"} <= set(tema.labels)
    assert set(tema.exclusive) == {"outro", "nenhum", "nao_especificado"}


def test_taxonomy_is_version_2() -> None:
    assert load_taxonomy().version == 2


def test_cannot_know_is_a_label_not_an_abstention() -> None:
    assert "nao_da_para_saber" in load_taxonomy().attributes["bloqueio"].labels


def test_unknown_exclusive_label_fails_loudly() -> None:
    raw = {
        "version": 1,
        "attributes": {
            "x": {"cardinality": "multi", "exclusive": ["ghost"], "labels": {"a": "", "b": ""}}
        },
    }
    with pytest.raises(ValueError, match="ghost"):
        _parse(raw)

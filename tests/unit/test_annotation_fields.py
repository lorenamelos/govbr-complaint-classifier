"""The annotation section of taxonomy.yaml: aligned with the API, invisible to it."""

from typing import get_args

import yaml

from govbr_classifier.annotation.fields import load_annotation_fields
from govbr_classifier.api.schemas import OodReason
from govbr_classifier.taxonomy import TAXONOMY_PATH, _parse, load_taxonomy


def test_ood_manual_is_the_api_ood_reason_plus_the_none_value() -> None:
    # Same names as the API, so manual calls compare with the guards without a translation table.
    fields = load_annotation_fields()
    reasons = set(fields.ood_manual) - {fields.ood_none_value}
    assert reasons == set(get_args(OodReason))
    assert fields.ood_none_value == "nao"


def test_duvida_has_no_placeholder_for_blank() -> None:
    # Blank cell means no doubt; a literal "vazio" value would be a second way to say it.
    assert "vazio" not in load_annotation_fields().duvida
    assert "" not in load_annotation_fields().duvida


def test_the_api_taxonomy_ignores_the_annotation_section() -> None:
    raw = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    without = {key: value for key, value in raw.items() if key != "annotation"}
    assert "annotation" in raw
    assert _parse(raw) == _parse(without) == load_taxonomy()


def test_annotation_values_are_not_taxonomy_labels_by_accident() -> None:
    # The section adds no label to any attribute (taxonomy stays version 2).
    taxonomy = load_taxonomy()
    assert taxonomy.version == 2
    assert set(taxonomy.attributes) == {"tema", "bloqueio", "tipo", "acionabilidade"}

"""model_version format: YYYY.MM.N-description (ADR-21)."""

import pytest

from govbr_classifier.models.keyword_baseline import MODEL_VERSION
from govbr_classifier.models.version import check_model_version


def test_served_version_follows_the_format() -> None:
    assert check_model_version(MODEL_VERSION) == MODEL_VERSION


@pytest.mark.parametrize(
    "version",
    [
        "2026.10.1-tema-keyword-baseline",
        "2026.01.12-logreg-tfidf",
        "2027.12.3-x",
    ],
)
def test_valid_versions_pass(version: str) -> None:
    assert check_model_version(version) == version


@pytest.mark.parametrize(
    ("case", "version"),
    [
        ("old free-form name", "tema-keyword-baseline-v1"),
        ("single-digit month", "2026.1.1-baseline"),
        ("month 13", "2026.13.1-baseline"),
        ("month zero", "2026.00.1-baseline"),
        ("N starts at 1", "2026.10.0-baseline"),
        ("N without leading zeros", "2026.10.01-baseline"),
        ("description missing", "2026.10.1"),
        ("empty description", "2026.10.1-"),
        ("uppercase", "2026.10.1-Baseline"),
        ("underscore", "2026.10.1-keyword_baseline"),
        ("accent", "2026.10.1-classificacao-genérica"),
        ("double hyphen", "2026.10.1-keyword--baseline"),
        ("trailing hyphen", "2026.10.1-baseline-"),
        ("trailing newline", "2026.10.1-baseline\n"),
    ],
)
def test_malformed_versions_fail_loudly(case: str, version: str) -> None:
    with pytest.raises(ValueError, match=r"YYYY\.MM\.N-description"):
        check_model_version(version)

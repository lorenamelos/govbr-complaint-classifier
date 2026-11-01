"""The rubric exists in Portuguese (official) and English (translation) at the same version."""

import re

from govbr_classifier.settings import PROJECT_ROOT

RUBRIC = PROJECT_ROOT / "docs" / "rubric"


def _version(name: str, label: str) -> int:
    text = (RUBRIC / name).read_text(encoding="utf-8")
    match = re.search(rf"^{label} (\d+),", text, re.MULTILINE)
    assert match, f"{name}: no '{label} N,' line"
    return int(match.group(1))


def test_both_rubric_versions_carry_the_same_number() -> None:
    # The translation must follow every revision of the official text (v4 comes after the pilot).
    official = _version("annotation_rubric.pt.md", "Versão")
    translation = _version("annotation_rubric.en.md", "Version")
    assert official == translation

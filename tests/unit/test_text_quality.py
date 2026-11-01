"""Low text quality guard (ADR-04): no letter and no digit means nothing for the model to read."""

import pytest

from govbr_classifier.guards.text_quality import has_letters_or_digits


@pytest.mark.parametrize("text", ["ok", "a", "10", "não", "ção", "ñ", "app 👍", "?? ruim"])
def test_any_letter_or_digit_passes(text: str) -> None:
    assert has_letters_or_digits(text)


@pytest.mark.parametrize("text", ["👍", "👍🏻", "❤️", "😡😡😡", "???", "...", "!!! ???", "🇧🇷"])
def test_emoji_and_punctuation_alone_do_not(text: str) -> None:
    assert not has_letters_or_digits(text)

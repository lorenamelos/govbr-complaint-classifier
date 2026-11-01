"""Deduplication key of a review text. Synthetic texts only."""

from govbr_classifier.data.text_key import text_key


def test_case_accents_and_punctuation_are_ignored() -> None:
    assert text_key("Péssimo!!!") == text_key("PÉSSIMO") == "pessimo"


def test_spacing_is_ignored() -> None:
    assert text_key("nao   abre\n") == text_key("Não abre")


def test_texts_without_words_keep_their_own_key() -> None:
    assert text_key("👍") != text_key("😡😡")
    assert text_key("👍") == text_key("👍 ") == "👍"
    assert text_key("!!!") != text_key("???")


def test_blank_text_has_an_empty_key() -> None:
    assert text_key("   ") == ""

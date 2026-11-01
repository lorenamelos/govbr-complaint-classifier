"""The deduplication key of a review text: two reviews with the same key are the same text.

Case, accents, punctuation and spacing are ignored, so "Péssimo!!!" and "PÉSSIMO" share a key.
A text with no word character at all (emoji or punctuation only) keeps its own characters, with
spacing collapsed, as the key: otherwise every such text would collapse into one empty key, and
"👍" and "😡😡" would count as the same text.

This one function defines a "unique text" everywhere: notebook 01, the annotation pilot and the
exclusion of pilot texts from the final sample (ADR-07).
"""

import re

from govbr_classifier.models.keyword_baseline import normalize

_WORD = re.compile(r"\w+")


def text_key(text: str) -> str:
    """Return the deduplication key: normalized words, or the collapsed text when it has none."""
    words = _WORD.findall(normalize(text))
    if words:
        return " ".join(words)
    return " ".join(text.split())

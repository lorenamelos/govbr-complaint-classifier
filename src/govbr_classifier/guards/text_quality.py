"""Low text quality detector, the first out-of-distribution guard (ADR-04).

A text with no letter and no digit, such as an emoji alone or a run of punctuation, carries no
words for the model to read. It is not a contract error (the batch is valid) and not a short text
the model should judge: it comes back as `out_of_distribution` with `low_text_quality`.

Short texts with letters, such as "ok", pass this guard and reach the model, which abstains when it
finds nothing to go on (ADR-03 revision of 2026-11-01).
"""


def has_letters_or_digits(text: str) -> bool:
    """True when the text has at least one letter or digit, in any script, accented or not."""
    return any(char.isalnum() for char in text)

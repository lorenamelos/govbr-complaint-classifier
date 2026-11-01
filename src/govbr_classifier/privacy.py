"""Mask personal data inside review text before it leaves the analysis (scope lock 5).

Used by the annotation spreadsheet now and meant for the LLM labeling step later. Patterns run from
the most specific to the most general, each replacing what it matches with a marker, so a later
pattern never sees what an earlier one masked:

1. CPF-shaped numbers, with or without dots, dashes or spaces -> [CPF]. The word "cpf" is the topic
   of thousands of complaints, identifies nobody, and is never masked.
2. Phone numbers -> [TELEFONE].
3. E-mail addresses -> [EMAIL]: text, "@", then a domain with a dot or a known provider, even
   without ".com" ("fulano@gmail").
4. Social profiles -> [PERFIL]: "@" at the start of a token followed by 3 or more letters, digits,
   dots or underscores ("@fulano123").
5. Names after a self-introduction ("me chamo", "meu nome é", "sou o/a") -> [NOME].
6. Any remaining run of 8 or more digits (protocol, RG, NIS) -> [NUMERO].

Every other "@" stays: censored swearing ("porc@ria", "b@#ta") and runs of symbols in place of a
swear word ("@%#$") are part of the complaint and identify nobody.

Known limit: names are found only after a self-introduction. "A atendente Maria não ajudou" keeps
the name. That is why `capitalized_mid_sentence` exists: it flags texts for a human to read before
they are shared. This mask is not enough for the LLM step and must be revisited there.

`assert_masked` is the last barrier: it raises when a CPF pattern, a run of 8 or more digits, an
e-mail or a profile survives. Its message never contains the text.
"""

import re
from dataclasses import dataclass

CPF = re.compile(r"(?<!\d)\d{3}[\s.-]*\d{3}[\s.-]*\d{3}[\s./-]*\d{2}(?!\d)")
PHONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b")
_PROVIDERS = r"(?:gmail|hotmail|outlook|yahoo|bol|uol|icloud|live)"
EMAIL = re.compile(rf"[\w.+-]+@(?:[\w-]+(?:\.[\w-]+)+|{_PROVIDERS}\b)", re.IGNORECASE)
PROFILE = re.compile(r"(?<![\w@])@[\w.]{3,}")
_NAME_WORD = r"[^\W\d_][^\W\d_'-]*"
_CAPITALIZED = r"[A-ZÀ-Ý][^\W\d_'-]*"
_CONNECTOR = r"(?:d[aoe]s?|e)"
# After "me chamo" / "meu nome é" the first word is a name in any case; after "sou o/a" only a
# capitalized word is ("sou a favor" is not a name). Up to three more capitalized words follow.
_MORE = rf"(?:\s+(?:{_CONNECTOR}\s+)?{_CAPITALIZED}){{0,3}}"
NAME_AFTER_INTRO = re.compile(
    rf"(?i:\b(?:me\s+chamo|meu\s+nome\s+(?:é|e))\s+)({_NAME_WORD}{_MORE})"
)
NAME_AFTER_SOU = re.compile(rf"(?i:\bsou\s+[oa]\s+)({_CAPITALIZED}{_MORE})")
LONG_NUMBER = re.compile(r"\d{8,}")

MARKERS = {
    "cpf": "[CPF]",
    "phone": "[TELEFONE]",
    "email": "[EMAIL]",
    "profile": "[PERFIL]",
    "name": "[NOME]",
    "number": "[NUMERO]",
}


class PersonalDataLeakError(ValueError):
    """Raised when masked text still matches a personal-data pattern."""


@dataclass(frozen=True)
class Masked:
    """Masked text and how many replacements each pattern made."""

    text: str
    counts: dict[str, int]


def _replace_group(pattern: re.Pattern[str], marker: str, text: str) -> tuple[str, int]:
    """Replace only the captured name, keeping the introduction words."""
    count = 0

    def swap(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        start, end = match.span(1)
        return (
            match.group(0)[: start - match.start()] + marker + match.group(0)[end - match.start() :]
        )

    return pattern.sub(swap, text), count


def mask(text: str) -> Masked:
    """Mask CPF, phone, e-mail, profile, introduced names and long numbers, in that order."""
    counts = dict.fromkeys(MARKERS, 0)
    for kind, pattern in (("cpf", CPF), ("phone", PHONE), ("email", EMAIL), ("profile", PROFILE)):
        text, counts[kind] = pattern.subn(MARKERS[kind], text)
    for pattern in (NAME_AFTER_INTRO, NAME_AFTER_SOU):
        text, found = _replace_group(pattern, MARKERS["name"], text)
        counts["name"] += found
    text, counts["number"] = LONG_NUMBER.subn(MARKERS["number"], text)
    return Masked(text=text, counts=counts)


def assert_masked(text: str, item: str) -> None:
    """Raise if a CPF pattern, 8+ digits, an e-mail or a profile survived. Names only the item."""
    checks = {"cpf pattern": CPF, "8+ digits": LONG_NUMBER, "email": EMAIL, "profile": PROFILE}
    found = [name for name, pattern in checks.items() if pattern.search(text)]
    if found:
        raise PersonalDataLeakError(f"{item}: personal data survived the mask ({', '.join(found)})")


_SENTENCE_END = re.compile(r"[.!?]\s*$")
_WORD = re.compile(r"\S+")


def capitalized_mid_sentence(text: str) -> bool:
    """True when a capitalized word appears outside the start of a sentence.

    A crude name detector for human review: it also flags place names, services ("Receita") and
    proper nouns in general. Markers such as [NOME] and all-caps words do not count.
    """
    previous = ""
    for match in _WORD.finditer(text):
        word = match.group(0).strip("\"'()[]{},;:")
        at_start = not previous or bool(_SENTENCE_END.search(previous))
        if (
            not at_start
            and len(word) > 1
            and word[0].isupper()
            and any(char.islower() for char in word[1:])
        ):
            return True
        previous = match.group(0)
    return False

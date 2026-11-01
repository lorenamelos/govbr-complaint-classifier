"""Keyword baseline for the `tema` attribute.

This is the first served model (ADR-21): it fills `tema` only, so the other three attributes
abstain with `not_implemented` until a trained classifier exists.

The keyword lists below are a HYPOTHESIS written before collecting data. They were drafted from
expectation, not from measured reviews, and they are expected to change once real Google Play text
is available. Treat every term here as provisional and re-derive the lists from the labeled set
before reporting any metric.

Known problem, measured in notebook 01 and left as is until then: some terms name a subject, not a
problem. "atendimento ótimo" matches `atendimento` and `nenhum`, the problem-wins rule drops
`nenhum`, and praise of the support channel comes back as a complaint about it.

Known problem of the same kind: "nao funciona" is a `servico_nao_carrega` term, but the rubric
labels "não funciona" with no subject as `nao_especificado`. The baseline never produces
`nao_especificado`, so these reviews come back as a service that does not load.

Two rules keep the baseline from inventing confidence:

- Matching is by whole word (regex word boundaries), never by substring, so "chato" does not match
  the `atendimento` term "chat".
- `outro` is never produced. It means "a complaint about something not on this list", which a closed
  keyword list cannot detect. When nothing matches, the attribute abstains (ADR-08); it never falls
  back to `outro`.
- `nao_especificado` is never produced either. It is a label about the text (a complaint with no
  subject), not the model failing to find one; an abstention must never be reported as it.
"""

import re
import unicodedata

from govbr_classifier.models.version import check_model_version
from govbr_classifier.taxonomy import load_taxonomy

# Format YYYY.MM.N-description, checked at import (models/version.py). The keyword lists did not
# change in 2026.11.1, but the same input gets a different answer: no minimum length (contract),
# low_text_quality for text with no letter or digit (guard) and taxonomy v2. The prediction log
# separates behavior by this value, so the name says what changed.
MODEL_VERSION = check_model_version("2026.11.1-tema-keyword-baseline-contract-guard-taxonomy-v2")
# The taxonomy version this model was built against. A label change is a model-version change.
TAXONOMY_VERSION = 2

# Terms are written without accents: the text is normalized the same way before matching.
# A term may be a phrase; whitespace inside it matches any run of whitespace in the text.
TEMA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "login_autenticacao": (
        "login",
        "logar",
        "senha",
        "esqueci a senha",
        "recuperar senha",
        "autenticacao",
        "autenticar",
        "nao consigo entrar",
        "nao consigo acessar",
        "acesso negado",
        "token",
        "codigo de verificacao",
        "duas etapas",
    ),
    "verificacao_identidade": (
        "reconhecimento facial",
        "biometria",
        "selfie",
        "nivel bronze",
        "nivel prata",
        "nivel ouro",
        "validar identidade",
        "verificacao de identidade",
        "foto do rosto",
    ),
    "travamento": (
        "trava",
        "travando",
        "fecha sozinho",
        "crash",
        "fechou",
        "congela",
        "tela branca",
        "parou de funcionar",
        "erro fatal",
    ),
    "lentidao": (
        "lento",
        "lenta",
        "lentidao",
        "demora",
        "demorado",
        "devagar",
        "carregando muito tempo",
    ),
    "servico_nao_carrega": (
        "nao carrega",
        "nao abre",
        "nao funciona",
        "nao consigo acessar",
        "erro ao carregar",
        "servico indisponivel",
        "erro no servidor",
        "pagina nao encontrada",
        "error 500",
    ),
    "atendimento": (
        "atendimento",
        "suporte",
        "nao responde",
        "sem resposta",
        "central de ajuda",
        "sac",
        "ouvidoria",
        "chat",
    ),
    # Praise and other text that describes no problem at all (ADR-05).
    "nenhum": (
        "otimo",
        "excelente",
        "muito bom",
        "parabens",
        "gostei",
        "funciona bem",
        "adorei",
        "perfeito",
    ),
}


def _strip_accents(text: str) -> str:
    """Drop combining marks so "ótimo" and "otimo" compare equal."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(text: str) -> str:
    """Lowercase and remove accents. The only text transformation the baseline applies."""
    return _strip_accents(text.lower())


def _compile(term: str) -> re.Pattern[str]:
    """Build a whole-word pattern for a term, tolerating any whitespace between its words."""
    body = r"\s+".join(re.escape(word) for word in term.split())
    return re.compile(rf"\b{body}\b")


_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    label: tuple(_compile(term) for term in terms) for label, terms in TEMA_KEYWORDS.items()
}


def _check_labels_are_in_taxonomy() -> None:
    """Fail at import time if the taxonomy changed under this model or a label is not in it."""
    taxonomy = load_taxonomy()
    if taxonomy.version != TAXONOMY_VERSION:
        raise ValueError(
            f"taxonomy.yaml is version {taxonomy.version}, this model was built for "
            f"{TAXONOMY_VERSION}: a label change needs a new MODEL_VERSION"
        )
    allowed = set(taxonomy.attributes["tema"].labels)
    unknown = set(TEMA_KEYWORDS) - allowed
    if unknown:
        raise ValueError(f"keyword labels not in the tema taxonomy: {sorted(unknown)}")


_check_labels_are_in_taxonomy()


def predict_tema(text: str) -> tuple[list[str], dict[str, float]]:
    """Return the matched `tema` labels and their scores.

    Scores are binary (1.0 for a matched label) because a keyword hit carries no graded evidence;
    unmatched labels are absent from the dict rather than present with 0.0, so the response never
    implies a calibrated probability the baseline does not have.

    `nenhum` is mutually exclusive with every other label (ADR-05): when a praise term and a problem
    term both match, the problem wins and `nenhum` is dropped. "otimo, nao funciona" is a complaint.

    An empty list means nothing matched. The caller turns that into an abstention, never into
    `outro`.
    """
    normalized = normalize(text)
    matched = [
        label
        for label, patterns in _PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    ]

    problems = [label for label in matched if label != "nenhum"]
    labels = problems or matched

    return labels, dict.fromkeys(labels, 1.0)

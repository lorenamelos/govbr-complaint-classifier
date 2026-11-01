"""Behavior of the keyword baseline for `tema`.

These tests pin the rules, not the word list. The list is a hypothesis until real reviews are
collected, so a test here asserts how matching works ("whole word", "nenhum loses to a problem"),
never that a particular term is present.
"""

from govbr_classifier.models.keyword_baseline import (
    TAXONOMY_VERSION,
    TEMA_KEYWORDS,
    normalize,
    predict_tema,
)
from govbr_classifier.taxonomy import load_taxonomy


def test_matching_is_by_whole_word_not_substring() -> None:
    # "chato" contains "chat", an atendimento term. Substring matching would label this review as a
    # complaint about support channels, which it is not.
    labels, _ = predict_tema("que app chato")
    assert "atendimento" not in labels


def test_accents_do_not_change_the_match() -> None:
    labels, _ = predict_tema("não consigo fazer login, esqueci a senha")
    assert "login_autenticacao" in labels


def test_a_matched_label_scores_one_and_the_rest_are_absent() -> None:
    # Unmatched labels are absent rather than present with 0.0: the baseline has no calibrated
    # probability to report.
    labels, scores = predict_tema("o app esta muito lento")
    assert labels == ["lentidao"]
    assert scores == {"lentidao": 1.0}


def test_tema_is_multi_label() -> None:
    labels, _ = predict_tema("nao consigo acessar e o suporte nao responde")
    assert {"login_autenticacao", "servico_nao_carrega", "atendimento"} <= set(labels)


def test_praise_alone_is_nenhum() -> None:
    labels, _ = predict_tema("otimo app, parabens")
    assert labels == ["nenhum"]


def test_nenhum_is_dropped_when_a_problem_also_matches() -> None:
    # ADR-05: nenhum is mutually exclusive with every other label. A praise word next to a failure
    # is still a complaint.
    labels, scores = predict_tema("ótimo, não funciona")
    assert "nenhum" not in labels
    assert "nenhum" not in scores
    assert "servico_nao_carrega" in labels


def test_nothing_matched_returns_empty_never_outro() -> None:
    # ADR-08: the caller turns this into an abstention. Falling back to `outro` would be the silent
    # failure this project exists to prevent.
    labels, scores = predict_tema("hmm")
    assert labels == []
    assert scores == {}


def test_every_keyword_label_is_in_the_closed_list() -> None:
    allowed = set(load_taxonomy().attributes["tema"].labels)
    assert set(TEMA_KEYWORDS) <= allowed


def test_outro_has_no_keywords() -> None:
    # `outro` means "something not on this list", which a closed keyword list cannot detect.
    assert "outro" not in TEMA_KEYWORDS


def test_nao_especificado_is_never_produced() -> None:
    # A complaint with no subject is a label about the text; the baseline cannot tell it from a
    # complaint whose subject it does not know, so it abstains rather than claim it.
    assert "nao_especificado" not in TEMA_KEYWORDS
    for text in ["péssimo", "horrível", "hmm"]:
        assert predict_tema(text) == ([], {})


def test_model_is_tied_to_the_taxonomy_version() -> None:
    # A label change is a model-version change: the import check fails if the two drift apart.
    assert load_taxonomy().version == TAXONOMY_VERSION


def test_keyword_terms_are_stored_normalized() -> None:
    # The text is normalized before matching, so an accented or capitalized term could never fire.
    for terms in TEMA_KEYWORDS.values():
        for term in terms:
            assert term == normalize(term), f"term is not normalized: {term!r}"

"""Masking of personal data in review text. Every text here is synthetic."""

import pytest

from govbr_classifier.privacy import (
    PersonalDataLeakError,
    assert_masked,
    capitalized_mid_sentence,
    mask,
)


@pytest.mark.parametrize(
    "text",
    ["meu cpf 123.456.789-09 não valida", "cpf 12345678909", "o 123 456 789 09 é meu"],
)
def test_cpf_numbers_are_masked_in_any_format(text: str) -> None:
    result = mask(text)
    assert "[CPF]" in result.text
    assert result.counts["cpf"] == 1
    assert_masked(result.text, "t")


def test_the_word_cpf_is_never_masked() -> None:
    assert mask("não consigo alterar o CPF no app").text == "não consigo alterar o CPF no app"


def test_phone_and_email_are_masked() -> None:
    result = mask("liga (11) 91234-5678 ou escreve para fulano.teste@exemplo.com")
    assert result.text == "liga [TELEFONE] ou escreve para [EMAIL]"
    assert result.counts["phone"] == 1
    assert result.counts["email"] == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("oi, me chamo joana e não consigo entrar", "oi, me chamo [NOME] e não consigo entrar"),
        ("meu nome é Ana Maria da Costa, preciso de ajuda", "meu nome é [NOME], preciso de ajuda"),
        ("Meu nome e Pedro.", "Meu nome e [NOME]."),
        ("eu sou a Fernanda e o app trava", "eu sou a [NOME] e o app trava"),
    ],
)
def test_introduced_names_are_masked(text: str, expected: str) -> None:
    assert mask(text).text == expected


def test_sou_followed_by_a_lowercase_word_is_not_a_name() -> None:
    assert mask("eu sou a favor de melhorar o app").counts["name"] == 0


def test_long_numbers_left_after_specific_patterns_become_numero() -> None:
    result = mask("protocolo 20231234567890 sem resposta, em 12/03/2024")
    assert result.text == "protocolo [NUMERO] sem resposta, em 12/03/2024"
    assert result.counts["number"] == 1
    assert result.counts["cpf"] == 0


def test_specific_patterns_win_over_numero() -> None:
    assert mask("cpf 12345678909").text == "cpf [CPF]"


@pytest.mark.parametrize(
    "leak",
    ["cpf 123.456.789-09", "protocolo 123456789", "fulano@gmail", "segue @fulano123"],
)
def test_the_last_barrier_fails_on_unmasked_text(leak: str) -> None:
    # Deliberately unmasked input: the barrier must stop it, and must not echo it.
    with pytest.raises(PersonalDataLeakError) as error:
        assert_masked(leak, "p007")
    assert "p007" in str(error.value)
    assert leak not in str(error.value)


def test_capitalized_word_mid_sentence_is_flagged_for_review() -> None:
    assert capitalized_mid_sentence("a atendente Maria não ajudou")
    assert not capitalized_mid_sentence("O app trava. Depois abre.")
    assert not capitalized_mid_sentence("o app NÃO abre, me chamo [NOME]")


@pytest.mark.parametrize(
    "text",
    [
        "essa porc@ria não abre",
        "uma b@#ta",
        "ótimo @",
        "esse app está uma 163!%!$×$@",  # noqa: RUF001 (the multiplication sign is the case)
        "lixo ..... @%#$£ .... !!!",
        "aplicativo, %@%$€ nada funciona",
        "não serve para #$-#@ nenhuma",
    ],
)
def test_censored_swearing_and_loose_at_signs_stay_intact(text: str) -> None:
    result = mask(text)
    assert result.text == text
    assert_masked(result.text, "t")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("@fulano123", "[PERFIL]"),
        ("me segue no @gov.br", "me segue no [PERFIL]"),
        ("@nome_sobrenome respondeu", "[PERFIL] respondeu"),
    ],
)
def test_profiles_are_masked(text: str, expected: str) -> None:
    result = mask(text)
    assert result.text == expected
    assert result.counts["profile"] == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("manda pra fulano@gmail", "manda pra [EMAIL]"),
        ("fulano@exemplo.com.br", "[EMAIL]"),
        ("Fulano.Teste@hotmail.com, obrigado", "[EMAIL], obrigado"),
    ],
)
def test_emails_are_masked_even_without_dot_com(text: str, expected: str) -> None:
    result = mask(text)
    assert result.text == expected
    assert result.counts["email"] == 1

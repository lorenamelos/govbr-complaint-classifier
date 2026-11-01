# Annotation rubric (English translation)

Version 3, 2026-11-01.

Written before annotation starts (ADR-09). This is a reading translation. The official version is the Portuguese one (`annotation_rubric.pt.md`), which is what the spreadsheet and the LLM labeler receive; if the two differ, the Portuguese one wins.
Label lists live in `src/govbr_classifier/taxonomy.yaml`; this file says how to decide.
Sections marked **(human annotation only)** are not sent to the LLM labeler. Everything else is sent verbatim.

## General

- Label what the text says, not what you guess the person meant. Irony that is evident in the text itself counts as what it says (see "Sarcasm").
- Decide `ood_manual` first. If it is `nao`, annotate the four attributes. Otherwise leave the four attributes empty.
- Always choose the best label, even when unsure.
- Emphasis does not change labels: "péssimooo", "PÉSSIMO" and "péssimo!!!" are the same text. Capitals, repeated letters and repeated punctuation signal intensity, and intensity is not labeled.
- Emoji alongside words is ignored. Emoji alone is handled by `ood_manual`.

## ood_manual

The LLM labeler also decides this field. The names match the API's `OodReason`, so annotations can be compared with the guards without a translation table.

- `nao`: the text is in Portuguese and talks about the gov.br app or its services. The normal case.
- `language`: the text is mostly in another language. Portuguese with a few foreign words ("app top, very good") stays `nao`.
- `low_text_quality`: no readable word. Emoji only, punctuation only, or a meaningless string ("asdfgh", "kkkkkk" alone). A short text with a real word, such as "ok", "bom" or "ruim", is **not** `low_text_quality`: it is annotated normally (see "Short texts").
- `off_domain`: the text does not talk about the app or one of its services. For example, an opinion about the government with no reference to the app, a complaint about another app, an advertisement.

## tema (multi-label)

- Assign every theme the text supports. "Não consigo entrar e o app está lento" is `login_autenticacao` and `lentidao`.
- **A theme is assigned only when the text complains about it, or asks for an improvement to it.** Naming a theme in praise is not enough: "atendimento ótimo" is `nenhum`. In "atendimento ótimo, mas a CNH digital não abre", the praise is ignored and the theme is `servico_nao_carrega`.
- Three escape values, for when no listed theme applies. Ask in this order:
  1. Is there a complaint? If not: `nenhum` ("ótimo app", "obrigado, resolveu", "ok").
  2. Does the complaint have an identifiable subject? If not: `nao_especificado` ("péssimo", "horrível", "lixo", "não funciona" or "nada funciona" without saying what).
  3. The subject exists but is not on the list: `outro`. Write the subject in the note.
- `outro`, `nenhum` and `nao_especificado` are never combined with each other or with other themes.
- A request for a new feature outside the list, with no complaint ("ótimo app, poderia ter modo escuro"), is `nenhum`. A request to improve a listed theme ("melhorem o login") gets that theme.
- `servico_nao_carrega` needs a named service or screen, or a loading error ("a CNH digital não abre", "dá erro ao carregar"). "Não funciona" alone is `nao_especificado`.
- Keep `nao_especificado` and `outro` apart: `outro` feeds the new-theme alarm, and a subjectless complaint filed there would look like an unknown theme.
- `nao_especificado` is a label about the text, not about your doubt. Do not use it as a way out when you cannot decide.
- **`nao_especificado` applies to `tema` only.** `bloqueio`, `tipo` and `acionabilidade` are annotated as usual. "Não funciona" is usually `tipo = bug`; "péssimo" is usually `tipo = insatisfacao_geral`; `bloqueio` is often `nao_da_para_saber`.
- **Obligation is not a theme.** "Me obrigam a...", "é obrigatório...", "sou obrigado a..." are annotated by the mechanism the text cites: "me obrigam a fazer reconhecimento facial" is `verificacao_identidade`; "obrigam a usar o app para tudo e ele não abre" is `servico_nao_carrega`. With no mechanism cited, the obligation itself is the subject: the theme is `outro`, with "obrigatoriedade" in the note.
- "Obrigado" as thanks is not obligation. "Sou obrigado a + verb" is.

## tipo (single value)

- `bug`: something fails in the app or in a digital service. Slowness, freezing, errors, a screen that does not load and a login that does not work are failures.
- `pedido_funcionalidade`: asks for something new or different.
- `insatisfacao_geral`: unhappy with no app failure and no request. Complaints about human support (call center, 0800 line, service desk) belong here, because they are not a software failure.
- `nenhum`: no problem and no request.
- **Precedence**, when the text has more than one: `bug`, then `pedido_funcionalidade`, then `insatisfacao_geral`. "Trava toda hora, coloquem modo escuro" is `bug`. "App horrível, deveriam colocar modo escuro" is `pedido_funcionalidade`.

## bloqueio

- `sim`: the text says or clearly implies the task could not be completed.
- `nao`: the text says the task was completed despite the problem, or reports no problem at all (`tipo = nenhum`).
- `nao_da_para_saber`: the text does not tell. When in doubt between this and another value, choose this one.

## acionabilidade

`sim` if the text names at least one of:

1. the service, feature or channel (for example "CNH digital", "carteira de trabalho", "modo escuro", "0800");
2. the step where it failed (for example "ao tirar a selfie");
3. an error message;
4. the device or operating system.

Otherwise `nao`. With `tipo = nenhum`, acionabilidade is always `nao`: there is nothing to fix.

## Consistency rules

- `tipo = nenhum` requires `tema = nenhum`, `bloqueio = nao` and `acionabilidade = nao`.
- `tema = nenhum` accepts `tipo` equal to `nenhum` or `pedido_funcionalidade`.
- `tema = outro` requires the subject in the note.
- `ood_manual` other than `nao` requires the four attributes to be empty.

## Special cases

- **Short texts.** "Ok", "bom", "top" and "show" contain no complaint: `tema = nenhum`, `tipo = nenhum`, `bloqueio = nao`, `acionabilidade = nao`. "Ruim" and "péssimo" are complaints with no subject: `nao_especificado`, `insatisfacao_geral`, `nao_da_para_saber`, `nao`.
- **Truncated text.** Collection cuts text at 500 characters. Annotate only what is visible and do not complete the ending. If the missing part could change the answer, use the most cautious value (`nao_da_para_saber` for bloqueio).
- **Sarcasm.** When irony is evident in the text ("parabéns, travou de novo na hora de assinar"), annotate the real meaning: it is a freezing complaint. When it is ambiguous, annotate the literal reading.

## Worked examples

All examples are synthetic. None comes from the dataset, so no item that may land in the pilot or the test leaks.

| # | Text | ood_manual | tema | tipo | bloqueio | action. |
|---|---|---|---|---|---|---|
| 1 | "não consigo entrar, pede a senha de novo e o app trava" | nao | login_autenticacao, travamento | bug | sim | sim |
| 2 | "atendimento ótimo, me ajudaram rápido" | nao | nenhum | nenhum | nao | nao |
| 3 | "atendimento ótimo, mas a CNH digital não abre" | nao | servico_nao_carrega | bug | sim | sim |
| 4 | "péssimooooo" | nao | nao_especificado | insatisfacao_geral | nao_da_para_saber | nao |
| 5 | "NÃO FUNCIONA" | nao | nao_especificado | bug | nao_da_para_saber | nao |
| 6 | "ok" | nao | nenhum | nenhum | nao | nao |
| 7 | (two thumbs-up emojis, no text) | low_text_quality | | | | |
| 8 | "very bad app, can't login" | language | | | | |
| 9 | "esse governo é uma vergonha" | off_domain | | | | |
| 10 | "ótimo app, poderia ter modo escuro" | nao | nenhum | pedido_funcionalidade | nao | sim |
| 11 | "app horrível, deveriam colocar modo escuro" | nao | nao_especificado | pedido_funcionalidade | nao_da_para_saber | sim |
| 12 | "me obrigam a fazer reconhecimento facial e a selfie nunca valida" | nao | verificacao_identidade | bug | sim | sim |
| 13 | "é obrigatório usar o app pra tudo, absurdo" | nao | outro (note: obrigatoriedade) | insatisfacao_geral | nao_da_para_saber | nao |
| 14 | "obrigado, resolveu meu problema" | nao | nenhum | nenhum | nao | nao |
| 15 | "parabéns, travou de novo bem na hora de assinar" | nao | travamento | bug | sim | sim |
| 16 | long text, truncated: says the carteira de trabalho does not load and ends with "aí tentei de novo e" | nao | servico_nao_carrega | bug | nao_da_para_saber | sim |
| 17 | "demora uns cinco minutos pra abrir qualquer coisa" | nao | lentidao | bug | nao_da_para_saber | nao |
| 18 | "liguei no 0800 três vezes e ninguém resolve meu problema" | nao | atendimento | insatisfacao_geral | sim | sim |

## obrigatoriedade box (human annotation only)

Check it when the text says the person is forced to use the app or one of its mechanisms ("me obrigam", "é obrigatório", "sou obrigado a", "colocam a gente para fazer..."). In the examples, the box is checked for 12 and 13. The box is not a label and does not change any attribute. It collects examples; in the pilot it does not measure frequency. With `ood_manual` other than `nao`, it stays empty.

## duvida (human annotation only)

The `duvida` column records uncertainty; it never replaces a label. Pick one category, the main one, and explain it in `nota_duvida`. Leave blank when there is no doubt. The note for the `outro` theme also goes in `nota_duvida`, without marking `duvida`.

| Category | When to use |
|---|---|
| `ood` | unclear whether the text is `off_domain`, `language` or `low_text_quality` |
| `tema_limite` | between two themes, or between a theme and an escape value |
| `tipo` | between two tipo values, even with the precedence rule |
| `bloqueio` | the text suggests, but does not make clear, whether the task was completed |
| `acionabilidade` | unclear whether what was named counts as a service, step, error or device |
| `cortado` | the missing part could change the answer (mark this one in example 16) |
| `enfase` | unclear whether the emphasis changes the reading |
| `sarcasmo` | the irony is ambiguous and you annotated the literal reading |
| `obrigatoriedade` | unclear whether there is obligation, or which mechanism it cites |
| `outro_caso` | anything else; describe it |

## Agreement checks (human annotation only)

- **Pilot:** the 50 items are re-annotated at least three weeks later, without looking at the first pass, to measure the annotator's self-agreement. They never enter the test set.
- **Final set:** one week after finishing, re-annotate a random 10% without looking at the first pass.
- Report Cohen's kappa between the LLM labels and the human labels, per attribute, including `ood_manual`. This kappa is the project's ceiling.

## Open questions (human annotation only)

Record here any case the rubric did not cover, with the decision taken and the date.

- 2026-11-01: complaints with no subject ("péssimo", "não funciona" alone) get the `tema` value `nao_especificado`, not `outro` (ADR-05 revision). Only `tema` changes; the other attributes are annotated as usual.
- 2026-11-01: obligation ("me obrigam a...") is not a label. Annotate by the mechanism cited; with no mechanism, `outro` with a note. It may become a label if the annotated test set holds at least 30 cases (ADR-07); it appears in 1,674 unique texts (0.52%), so only with targeted sampling.
- 2026-11-01 (version 3): `skip` replaced by `ood_manual`, which the LLM also decides; theme only with a complaint or request; tipo precedence; human support complaints are `insatisfacao_geral`; consistency rules; special cases; duvida categories; 18 synthetic examples. The Portuguese version becomes the official one.
- 2026-11-01: "kkkkkk" alone is `low_text_quality` in the rubric, but the API guard classifies it (the text has letters). The gap is expected and measures the guard.

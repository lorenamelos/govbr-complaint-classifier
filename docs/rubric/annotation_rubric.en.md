# Annotation rubric (English translation)

Version 4, 2026-11-09.

Written before annotation starts (ADR-09) and revised after the 50-item pilot. This is a reading translation. The official version is the Portuguese one (`annotation_rubric.pt.md`), which is what the spreadsheet and the LLM labeler receive; if the two differ, the Portuguese one wins.
Label lists live in `src/govbr_classifier/taxonomy.yaml`; this file says how to decide.
Sections marked **(human annotation only)** are not sent to the LLM labeler. Everything else is sent verbatim.

## General

- Label what the text says, not what you guess the person meant. Irony that is evident in the text itself counts as what it says (see "Sarcasm").
- Decide `ood_manual` first. If it is `nao`, annotate the four attributes. Otherwise leave the four attributes empty.
- Always choose the best label, even when unsure.
- Emphasis does not change labels: "péssimooo", "PÉSSIMO" and "péssimo!!!" are the same text. Capitals, repeated letters and repeated punctuation signal intensity, and intensity is not labeled. A swear word censored with symbols ("porc@ria", "b@#ta") counts as the word it replaces.
- Emoji alongside words is ignored. Emoji alone is handled by `ood_manual`.

## ood_manual

The LLM labeler also decides this field. The names match the API's `OodReason`, so annotations can be compared with the guards without a translation table.

- `nao`: the text is in Portuguese and talks about the gov.br app or its services. The normal case.
- `language`: the text is mostly in another language. Portuguese with a few foreign words ("app top, very good") stays `nao`.
- `low_text_quality`: no readable word. Emoji only, punctuation only, symbols only, or a meaningless string ("asdfgh", "kkkkkk" alone). A short text with a real word, such as "ok", "bom" or "ruim", is **not** `low_text_quality`: it is annotated normally (see "Short texts").
- `off_domain`: the text does not talk about the app or one of its services. For example, an opinion about the government with no reference to the app, a complaint about another app, an advertisement. Criticism of the country or the government inside a complaint about the app stays `nao`.

## tema (multi-label)

### When to assign a theme

- **A theme is assigned only when the text complains about it, or asks for an improvement to it.** Naming a theme in praise is not enough: "atendimento ótimo" is `nenhum`. In "atendimento ótimo, mas a CNH digital não abre", the praise is ignored and the theme is `servico_nao_carrega`.
- **Several themes or one.** Assign more than one when the text reports distinct, added problems ("o código não chega **e** a biometria está inválida": `login_autenticacao` and `verificacao_identidade`). When one problem causes the other ("não consigo entrar **porque** o rosto não passa"), assign only the mechanism that failed: `verificacao_identidade`. Test: do both boxes apply, or am I choosing between them? If choosing, pick the best and record the doubt.

### The three escape values

Ask in this order:

1. **Is there a complaint?** If not: `nenhum` ("ótimo app", "obrigado, resolveu", "ok", "ainda nem testei"). Anything negative in the text, including a swear word, is already a complaint.
2. **Does the complaint have an identifiable subject?** Complete the sentence "the complaint is about ___". If only adjectives or failure verbs fit ("péssimo", "horrível", "lixo", "não funciona", "nada funciona"), there is no subject: `nao_especificado`.
3. **Is the subject on the list?** If a noun naming a part or aspect of the app fits, but no box applies ("navegação", "meus dados", "phone compatibility", "the agency's deadline"), the theme is `outro`, and the subject goes in the `assunto_outro` column.

- `outro`, `nenhum` and `nao_especificado` are never combined with each other or with other themes. When the text has a listed problem and a distinct subject outside the list, the listed theme wins; the outside subject may go in `assunto_outro`, for the record. When one causes the other, apply the "porque" rule: an old, unsupported phone that blocks two-step verification is `outro` (compatibility), because there is a single cause.
- Keep `nao_especificado` and `outro` apart: `outro` feeds the new-theme alarm, and a subjectless complaint filed there would look like an unknown theme.
- `nao_especificado` is a label about the text, not about your doubt. Do not use it as a way out when you cannot decide.
- **`nao_especificado` applies to `tema` only.** `bloqueio`, `tipo` and `acionabilidade` are annotated as usual.
- A request for a new feature outside the list, with no complaint ("ótimo app, poderia ter modo escuro"), is `nenhum`. A request to improve a listed theme ("melhorem o login") gets that theme.

### Boundaries between themes

- **`login_autenticacao` vs `verificacao_identidade`.** Login answers "do you have the key to this account?": password, SMS or e-mail code, password recovery, locked account, "CPF already registered". Verification answers "are you really this person?": facial recognition, selfie, face capture, biometrics, proof of life, document validation. Face, selfie and biometrics are always `verificacao_identidade`, even when the person was trying to log in.
- **"Acessar" and "entrar".** "Não consigo acessar" or "não consigo entrar" with no object is `login_autenticacao`: in gov.br the front door is the account. "Acessar X" (a service) gets X's theme. "Difícil acessar tudo", as a judgment about finding things in the app, is `outro` (navigation).
- **`servico_nao_carrega`** needs a named service or screen, or a loading error ("a CNH digital não abre", "dá erro ao carregar"). "Não funciona" alone is `nao_especificado`.
- **"Foto".** The verb decides. Face, selfie, "validate the photo": `verificacao_identidade`. Attach, send, "where do I put the photo", a missing field: `servico_nao_carrega`.
- **Slowness.** `lentidao` is the app or a screen being slow ("muito lento", "demora pra abrir"). When the delay is in a specific step ("pra recuperar a senha demora muito", "muito devagar para reconhecer"), assign the mechanism **and** `lentidao`, so `lentidao` counts every speed complaint. The agency's processing deadline ("o pedido demora 60 dias pra ser aprovado") is not app slowness: it is `outro` (agency deadline).
- **Error code with no explanation** ("erro 403"). The rest of the text decides the theme. With no context at all, `nao_especificado`. Acionabilidade is `sim`, because an error message is one of the criteria.
- **Obligation is not a theme.** "Me obrigam a...", "é obrigatório...", "sou obrigado a..." are annotated by the mechanism the text cites: "me obrigam a fazer reconhecimento facial" is `verificacao_identidade`. With no mechanism cited, the obligation itself is the subject: `outro`, with "obrigatoriedade" in `assunto_outro`. "Obrigado" as thanks is not obligation.

## tipo (single value)

- `bug`: the text **reports an event**: something should have happened in the app or in a digital service and did not. Slowness, freezing, errors, a screen that does not load, a login that does not go through, a face that does not validate and "I can't use it" are failures, even when the report is vague.
- `insatisfacao_geral`: the text **makes a judgment**, with no failure reported and no request: "péssimo", "complicado", "uma porcaria". This also covers:
  - complaints about human support (call center, 0800 line, service desk), because they are not a software failure;
  - **a barrier by rule**: the app works as designed, but a rule stops the person (a required document, age, account level, an unsupported phone).
- `pedido_funcionalidade`: asks for something new or different.
- `nenhum`: no problem and no request.
- Guiding question between `bug` and `insatisfacao_geral`: would a developer know what to fix? If something broke, it is `bug`.
- **Precedence**, when the text has more than one: `bug`, then `pedido_funcionalidade`, then `insatisfacao_geral`. "Trava toda hora, coloquem modo escuro" is `bug`. "App horrível, deveriam colocar modo escuro" is `pedido_funcionalidade`.

## bloqueio

- `sim`: the text says or clearly implies the task could not be completed. An error message that stops the person counts as `sim`.
- `nao`: the text says the task was completed despite the problem, or reports no problem at all (`tipo = nenhum`).
- `nao_da_para_saber`: the text does not tell. "Doesn't always work" and "takes too long" go here, because they do not say whether the person got through in the end. When in doubt between this and another value, choose this one.

## acionabilidade

`sim` if the text names at least one of:

1. the service, feature or channel (for example "CNH digital", "carteira de trabalho", "minha conta", "recuperar a senha", "modo escuro", "0800");
2. the step where it failed (for example "ao tirar a selfie", "captura de rosto");
3. an error message or code;
4. the device or operating system (including "old phone").

Otherwise `nao`. "Acessar" or "navegação" alone name nothing specific. With `tipo = nenhum`, acionabilidade is always `nao`: there is nothing to fix.

## Consistency rules

- `tipo = nenhum` requires `tema = nenhum`, `bloqueio = nao` and `acionabilidade = nao`.
- `tema = nenhum` accepts `tipo` equal to `nenhum` or `pedido_funcionalidade`.
- `tema = outro` requires `assunto_outro` to be filled.
- `ood_manual` other than `nao` requires the four attributes to be empty.

## Special cases

- **Short texts.** "Ok", "bom", "top" and "show" contain no complaint: `tema = nenhum`, `tipo = nenhum`, `bloqueio = nao`, `acionabilidade = nao`. "Ruim", "péssimo" and a swear word alone are complaints with no subject: `nao_especificado`, `insatisfacao_geral`, `nao_da_para_saber`, `nao`.
- **Truncated text.** Collection cuts text at 500 characters. Annotate only what is visible and do not complete the ending. If the missing part could change the answer, use the most cautious value (`nao_da_para_saber` for bloqueio).
- **Sarcasm.** When irony is evident in the text ("parabéns, travou de novo na hora de assinar"), annotate the real meaning: it is a freezing complaint. When it is ambiguous, annotate the literal reading.

## Worked examples

All examples are synthetic. None comes from the dataset, so no item that may land in the sample or the test leaks.

| # | Text | ood_manual | tema | assunto_outro | tipo | bloqueio | action. |
|---|---|---|---|---|---|---|---|
| 1 | "não consigo entrar, pede a senha de novo e o app trava" | nao | login_autenticacao, travamento | | bug | sim | sim |
| 2 | "atendimento ótimo, me ajudaram rápido" | nao | nenhum | | nenhum | nao | nao |
| 3 | "atendimento ótimo, mas a CNH digital não abre" | nao | servico_nao_carrega | | bug | sim | sim |
| 4 | "péssimooooo" | nao | nao_especificado | | insatisfacao_geral | nao_da_para_saber | nao |
| 5 | "NÃO FUNCIONA" | nao | nao_especificado | | bug | nao_da_para_saber | nao |
| 6 | "ok" | nao | nenhum | | nenhum | nao | nao |
| 7 | (two thumbs-up emojis, no text) | low_text_quality | | | | | |
| 8 | "very bad app, can't login" | language | | | | | |
| 9 | "esse governo é uma vergonha" | off_domain | | | | | |
| 10 | "ótimo app, poderia ter modo escuro" | nao | nenhum | | pedido_funcionalidade | nao | sim |
| 11 | "app horrível, deveriam colocar modo escuro" | nao | nao_especificado | | pedido_funcionalidade | nao_da_para_saber | sim |
| 12 | "me obrigam a fazer reconhecimento facial e a selfie nunca valida" | nao | verificacao_identidade | | bug | sim | sim |
| 13 | "é obrigatório usar o app pra tudo, absurdo" | nao | outro | obrigatoriedade | insatisfacao_geral | nao_da_para_saber | nao |
| 14 | "obrigado, resolveu meu problema" | nao | nenhum | | nenhum | nao | nao |
| 15 | "parabéns, travou de novo bem na hora de assinar" | nao | travamento | | bug | sim | sim |
| 16 | long text, truncated: says the carteira de trabalho does not load and ends with "aí tentei de novo e" | nao | servico_nao_carrega | | bug | nao_da_para_saber | sim |
| 17 | "demora uns cinco minutos pra abrir qualquer coisa" | nao | lentidao | | bug | nao_da_para_saber | nao |
| 18 | "liguei no 0800 três vezes e ninguém resolve meu problema" | nao | atendimento | | insatisfacao_geral | sim | sim |
| 19 | "não consigo acessar faz uma semana" | nao | login_autenticacao | | bug | sim | nao |
| 20 | "pra recuperar a senha demora demais" | nao | login_autenticacao, lentidao | | bug | nao_da_para_saber | sim |
| 21 | "o código não chega e a biometria dá inválida" | nao | login_autenticacao, verificacao_identidade | | bug | sim | sim |
| 22 | "não aparece onde anexar a foto do documento no pedido" | nao | servico_nao_carrega | | bug | sim | sim |
| 23 | "muito complicada a navegação" | nao | outro | navegação | insatisfacao_geral | nao_da_para_saber | nao |
| 24 | "não roda no meu celular porque é antigo, tenho que trocar de telefone" | nao | outro | compatibilidade com o celular | insatisfacao_geral | sim | sim |
| 25 | "pede a carteira de motorista e eu não tenho" | nao | verificacao_identidade | | insatisfacao_geral | sim | sim |
| 26 | "só aparece erro 500" | nao | nao_especificado | | bug | sim | sim |
| 27 | "o pedido de restituição demora meses pra ser analisado" | nao | outro | prazo do órgão | insatisfacao_geral | nao_da_para_saber | sim |

## obrigatoriedade box (human annotation only)

Check it when the text says the person is forced to use the app or one of its mechanisms, explicitly ("me obrigam", "é obrigatório", "sou obrigado a", "colocam a gente para fazer...") or implicitly ("meus apps só entram por ele", "tenho que trocar de telefone para ter acesso"). In the examples, the box is checked for 12, 13 and 24. The box is not a label and does not change any attribute. With `ood_manual` other than `nao`, it stays empty.

## duvida (human annotation only)

The `duvida` column records uncertainty; it never replaces a label. Pick one category, the main one, and explain it in `nota_duvida`. Leave blank when there is no doubt. What counts is the doubt left after applying the rubric, not the first-moment one. The subject of the `outro` theme goes in `assunto_outro`, never in `nota_duvida`.

| Category | When to use |
|---|---|
| `ood` | unclear whether the text is `off_domain`, `language` or `low_text_quality` |
| `tema_limite` | between two themes, or a theme and an escape value, after applying the boundaries above |
| `tipo` | between two tipo values, even with the guiding question and the precedence rule |
| `bloqueio` | the text suggests, but does not make clear, whether the task was completed |
| `acionabilidade` | unclear whether what was named counts as a service, step, error or device |
| `cortado` | the missing part could change the answer (mark this one in example 16) |
| `enfase` | unclear whether the emphasis changes the reading |
| `sarcasmo` | the irony is ambiguous and you annotated the literal reading |
| `obrigatoriedade` | unclear whether there is obligation, or which mechanism it cites |
| `outro_caso` | anything else; describe it |

## Agreement checks (human annotation only)

- **Pilot:** the 50 items are re-annotated with this version from 2026-11-29, without looking at the first pass. The annotator's self-agreement is measured only on items whose rule did not change from v3 to v4; on items that fell under new rules (p007, p013, p017, p025, p033, p039), the difference measures the effect of the change. The 50 never enter the test set.
- **Final set:** one week after finishing, re-annotate a random 10% without looking at the first pass.
- Report Cohen's kappa between the LLM labels and the human labels, per attribute, including `ood_manual`. This kappa is the project's ceiling.

## Open questions (human annotation only)

Record here any case the rubric did not cover, with the decision taken and the date.

- 2026-11-01: complaints with no subject ("péssimo", "não funciona" alone) get the `tema` value `nao_especificado`, not `outro` (ADR-05 revision).
- 2026-11-01: obligation is not a label. Annotate by the mechanism cited; with no mechanism, `outro`. It may become a label if the annotated test set holds at least 30 cases (ADR-07); it appears in 1,674 unique texts (0.52%), so only with targeted sampling.
- 2026-11-01: "kkkkkk" alone is `low_text_quality` in the rubric, but the API guard classifies it (the text has letters). The gap is expected and measures the guard.
- 2026-11-09 (version 4, after the pilot): "the complaint is about ___" test for the escape values; "porque vs e" rule; login vs verification boundary; "acessar" with no object is login; delay in a step assigns the mechanism and `lentidao`; the agency's deadline is `outro`; "foto" decided by the verb; an error code with no context is `nao_especificado` with acionabilidade `sim`; `bug` is an event report and `insatisfacao_geral` a judgment; a barrier by rule is `insatisfacao_geral`; implicit obligation checks the box; `assunto_outro` column; 27 synthetic examples.
- 2026-11-09: new themes (navigation, compatibility) and the exclusivity of `outro` are taxonomy decisions, not rubric ones. The `assunto_outro` column collects subjects in the final sample; a theme is created only if it appears often enough (at least 30 cases in the test, ADR-07).

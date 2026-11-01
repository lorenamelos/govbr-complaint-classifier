# Annotation rubric

Written before annotation starts (ADR-09). The same rubric is given verbatim to the LLM labeler.
Label lists live in `src/govbr_classifier/taxonomy.yaml`; this file says how to decide.

## General

- Label what the text says, not what you guess the person meant.
- Annotate all four attributes for every review.
- If a review is not in Portuguese or is unreadable, mark it `skip` with a reason; it is not annotated.

## tema (multi-label)

- Assign every label the text supports. "Can't log in and the app is slow" is `login_autenticacao` and `lentidao`.
- Three escape values, for when no listed theme applies. Ask in this order:
  1. Is there a complaint? If not: `nenhum` ("ótimo app", "obrigado").
  2. Does the complaint have an identifiable subject? If not: `nao_especificado` ("péssimo",
     "horrível", "lixo", "não funciona" or "nada funciona" without saying what).
  3. The subject exists but is not on the list: `outro`. Write the subject in the notes column.
- `outro`, `nenhum` and `nao_especificado` are never combined with each other or with other labels.
  If the text names any listed theme, use that theme, not an escape value.
- `servico_nao_carrega` needs a named service or screen, or a loading error ("a CNH digital não
  abre", "dá erro ao carregar"). "Não funciona" alone is `nao_especificado`.
- Keep `nao_especificado` and `outro` apart: `outro` feeds the new-theme alarm, so a subjectless
  complaint filed there would look like an unknown theme.
- `nao_especificado` is a label about the text, not doubt. If you cannot decide, say so in the notes;
  do not use it as a way out.
- **`nao_especificado` applies to `tema` only.** `bloqueio`, `tipo` and `acionabilidade` are
  annotated as usual. "Não funciona" is usually `tipo = bug`; "péssimo" is usually
  `tipo = insatisfacao_geral`; `bloqueio` is often `nao_da_para_saber`.
- **Obligation is not a theme.** "Me obrigam a...", "é obrigatório...", "sou obrigado a..."
  are annotated by the mechanism the text cites: "me obrigam a fazer reconhecimento facial" is
  `verificacao_identidade`; "obrigam a usar o app para tudo e ele não abre" is `servico_nao_carrega`.
  With no mechanism cited, apply the escape values above. Whether obligation becomes a label is
  decided later (see Open questions).

## bloqueio

- `sim`: the text says or clearly implies the task could not be completed.
- `nao`: the text says the task was completed despite the problem.
- `nao_da_para_saber`: the text does not tell. When in doubt between this and another value, choose this one.

## tipo

- `bug`: something fails. `pedido_funcionalidade`: asks for something new. `insatisfacao_geral`: unhappy with
  no specific failure or request. `nenhum`: no problem.
- If a review has both a bug and a request, choose `bug`.

## acionabilidade

`sim` if the text names at least one of:

1. the service or feature (for example "CNH digital", "carteira de trabalho");
2. the step where it failed (for example "ao tirar a selfie");
3. an error message;
4. the device or operating system.

Otherwise `nao`.

## Agreement checks

- One week after finishing, re-annotate a random 10% without looking at the first pass. Report self-agreement.
- Report Cohen's kappa between the LLM labels and the human labels, per attribute.

## Open questions

Record here any case the rubric did not cover, with the decision taken and the date.

- 2026-11-01: complaints with no subject ("péssimo", "não funciona" alone) get the new `tema` value
  `nao_especificado`, not `outro` (ADR-05 revision). Only `tema` changes; the other attributes are
  annotated as usual.
- 2026-11-01: obligation ("me obrigam a...") is not a label. Annotate by the mechanism cited. It may
  become a label if the annotated test set holds at least 30 cases (ADR-07); notebook 01 counts how
  often it appears.

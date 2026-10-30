# Annotation rubric

Written before annotation starts (ADR-09). The same rubric is given verbatim to the LLM labeler.
Label lists live in `config/taxonomy.yaml`; this file says how to decide.

## General

- Label what the text says, not what you guess the person meant.
- Annotate all four attributes for every review.
- If a review is not in Portuguese or is unreadable, mark it `skip` with a reason; it is not annotated.

## tema (multi-label)

- Assign every label the text supports. "Can't log in and the app is slow" is `login_autenticacao` and `lentidao`.
- `outro`: there is a complaint, but none of the listed themes fits. Write the theme in the notes column.
- `nenhum`: there is no complaint at all.
- `outro` and `nenhum` are never combined with other labels.

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

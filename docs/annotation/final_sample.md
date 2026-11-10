# Final annotation sample

The hand-labeled set that later splits into calibration (40%) and test (60%) (ADR-07). It is drawn
in waves: each wave is designed with what the previous one measured.

## Wave 1 (drawn 2026-11-10)

- **Universe:** 320,526 unique texts, the 320,576 of the pilot's universe minus the 50 pilot texts,
  excluded by text key (`annotation.pilot.pilot_excluded_texts`). No filter on `app_version`.
- **Strata, disjoint:** rating (as in the pilot: most frequent rating of the text, lowest on a tie)
  x signal group. A text with several signals goes to the rarest group, in this order:
  `pedido_funcionalidade`, `atendimento`, `travamento`, `servico_nao_carrega`. A text with none is
  `sem_sinal`. Every text is in exactly one stratum, so its inclusion probability is n_h / N_h.
- **Signals** (`annotation.final_sample`), a sampling device and never a label:
  - `atendimento`, `travamento`: the keyword baseline terms of that theme;
  - `servico_nao_carrega`: the baseline terms minus "nao funciona" (18,831 texts matched only
    through it, and the rubric labels it `nao_especificado`);
  - `pedido_funcionalidade`: an expression list reviewed by the owner, without the forms of
    "falta" and without "deveria(m) ter" followed by zero, nenhuma, menos or 0 estrela(s).
- **Allocation:** 300 items, one simple random draw per stratum, seed 20261110. n_h adds a random
  part (40 per rating, split across the rating's groups in proportion to size) and a targeted
  part (25 per signal group, split across ratings in proportion to size), both by largest
  remainder.

| rating | pedido N / n | atendimento N / n | travamento N / n | servico N / n | sem_sinal N / n |
|---|---|---|---|---|---|
| 1 | 936 / 14 | 3,467 / 17 | 4,010 / 20 | 12,992 / 23 | 152,083 / 35 |
| 2 | 172 / 3 | 297 / 2 | 486 / 3 | 1,315 / 4 | 19,905 / 36 |
| 3 | 185 / 4 | 178 / 1 | 359 / 3 | 663 / 2 | 19,195 / 37 |
| 4 | 153 / 2 | 140 / 1 | 175 / 2 | 230 / 2 | 16,567 / 38 |
| 5 | 202 / 3 | 1,249 / 7 | 244 / 1 | 777 / 1 | 84,546 / 39 |

- `scripts/select_wave1.py` writes `data/sample/wave1/manifest.csv` (item id, review id, text key,
  wave, stratum, rating stratum, the signal that directed the item, every signal matched,
  selection probability) and `link.csv` (plus rating, original length and API guard result).
  None of this goes to the spreadsheet: the annotator does not know which items were targeted.
- `scripts/build_annotation_sheet.py --set wave1` writes the layout v4 spreadsheet, with the same
  privacy rules as the pilot: masked text, the last barrier, and the list of item ids with a
  capitalized word mid-sentence to read before importing.

## Wave 2

Designed after wave 1 is annotated, from its counts per class and the precision of each signal on
it. Its universe also excludes every wave 1 text by key.

Candidates to leave the `pedido_funcionalidade` signal, decided only if the precision measured on
wave 1 supports it (recorded 2026-11-10, wave 1 kept as drawn):

- "deveria ter vergonha" (45 unique texts in the wave 1 universe): reads as a judgment, not a
  request;
- "deveria ter sido" (13): reads as a past expectation, not a request.

Both were found by counting the word after "deveria ter" (word counts only, no text). The star
rule already applied in wave 1 ("deveria(m) ter" followed by zero, nenhuma, menos or 0
estrela(s)) removed only 3 texts.

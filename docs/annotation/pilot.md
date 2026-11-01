# Annotation pilot

## What the pilot is, and what it is not

The pilot is 50 Google Play reviews annotated by the project owner alone, before the final
annotation set, to measure annotation speed and to find where the rubric
(`docs/rubric/annotation_rubric.pt.md`) leaves room for doubt. The same 50 items are annotated
again at least three weeks later, without looking at the first pass, to measure self-agreement.

It is **not** the test set, not the calibration set and not training data. Its labels are never
used to tune a threshold or report a metric of the model, and its texts never enter the final
sample. Its stress items were chosen by rule to provoke doubt, so its label distribution says
nothing about the population.

## Universe and selection

- **Unit: the unique text.** Two reviews are the same text when `data/text_key.text_key` gives them
  the same key (case, accents, punctuation and spacing ignored; a text with no word keeps its own
  characters as its key). 800,069 reviews give 320,576 unique texts. No filter on `app_version`.
- **Stratum: one rating per text.** The most frequent rating among the text's copies; on a tie,
  the lowest. 7,357 unique texts (2.3%) appear with more than one distinct rating. Unique texts per
  stratum: 1 star 173,503; 2 stars 22,183; 3 stars 20,588; 4 stars 17,274; 5 stars 87,028.
- **40 random items**, 8 per stratum, simple random sampling within the stratum, seed 20261101.
  Selection probability = 8 / unique texts in the stratum, recorded for reweighting.
- **10 stress items**, drawn after the random ones from what is left, by fixed rules, with no
  selection probability (they never enter a weighted estimate): 2 praise with a theme word, 2
  emphasis, 2 cut at exactly 500 characters, 1 with "obrigam", 1 with "colocam", 1 emoji or
  punctuation only, and 1 in another language taken from the reviews the owner confirmed as
  `true_positive` in the `other_language` review (the heuristic itself has 53% precision).
- The representative of a text, whose raw text is shown, is its most recently dated copy.
- `scripts/select_pilot.py` writes `data/pilot/manifest.csv` and `data/pilot/link.csv` (never
  committed) and prints counts only.

## Exclusion from the final sample

The universe of the final annotation sample is the full universe **minus the 50 pilot texts**,
excluded by text key, not by review id: every copy of a pilot text is out, including copies
collected later under review ids that did not exist when the pilot was drawn. The final sampler
must use `annotation.pilot.pilot_excluded_texts()` and `final_sample_universe()`, and its
selection probabilities are computed on this reduced universe.

## Privacy

Texts are masked before they reach the spreadsheet (`privacy.py`): CPF numbers, phones, e-mails,
social profiles, names after a self-introduction and leftover runs of 8+ digits become [CPF],
[TELEFONE], [EMAIL], [PERFIL], [NOME] and [NUMERO]. A last barrier stops the spreadsheet if a CPF
pattern, 8+ digits, an e-mail or a profile survives. The spreadsheet carries no rating, review id,
author, exact date or app version; items are p001 to p050.

**The name mask is not enough for step 4 (LLM labeling) and must be revisited there.** It only
catches names after "me chamo", "meu nome é" or "sou o/a". A name written anywhere else ("a
atendente Maria") passes. For the pilot, the generator lists the item ids with a capitalized word
mid-sentence so the owner reads them before importing the spreadsheet; that manual read does not
scale to thousands of LLM calls.

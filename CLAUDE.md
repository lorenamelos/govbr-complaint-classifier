# CLAUDE.md

Guidance for Claude Code working in this repository. Read this file before any change.

## What this project is

A multi-attribute classifier of complaints about the gov.br app, built from public Google Play reviews and
served behind a public API. It is a portfolio project, and its differentiator is honest evaluation and
silent-failure detection, not model accuracy.

The guiding principle: **when the system does not know, it says so, with a reason.** Every design choice
exists to stop an uncertainty from turning into silence. If a change would make the system quieter about
what it does not know, it is the wrong change.

The full rationale lives in `docs/adr/` (21 decisions). This file is the operational summary.

## How the owner works

- Strategy before code: business rules first, then solution structure, then implementation. When a task
  is ambiguous, propose the plan and the open questions before writing code.
- She learns through analogies and diagrams. Explanations in chat should say *why*, not only *how*.
- Python, pandas, scikit-learn. **Plotly is the only plotting library**: never matplotlib or seaborn.
- Code, comments, docstrings and commit messages in **English**. Conversation may be in Portuguese.
- No emojis anywhere: code, docs, commits, notebooks.
- Documentation is a living knowledge base: when a decision changes, update the ADR (add a dated line,
  never delete the old reasoning).

## Scope locks (do not cross without asking)

1. **Google Play only.** No App Store, Instagram, TikTok or other sources.
2. **Four attributes only**: `tema`, `bloqueio`, `tipo`, `acionabilidade` (see `src/govbr_classifier/taxonomy.yaml`).
   A new attribute is added only after evaluation supports the existing four.
3. **No accuracy averaged across attributes.** Every metric is per attribute and per class.
4. **The LLM never serves predictions.** It labels the training set offline and runs the offline cost
   benchmark. The served path is the small classifier.
5. **Raw review text never leaves the machine with authorship.** Publish only aggregates, an anonymized
   sample, and collection code. The API never stores raw input text.

## Architecture in one screen

```
request -> contract (422) -> domain guard (200 out_of_distribution) -> classifier -> per-attribute threshold
                                                                                    (200 classified, with abstentions)
every response, including 422 -> prediction log (salted hash, scores, latency, cost, model_version, source)
```

Endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/classify` | classify 1 to 50 texts |
| `GET /v1/health` | five-level report: alive, integrity, canary, freshness, drift |
| `GET /health/live` | process is up; the only check the platform polls |
| `GET /v1/drift?reference=fixed\|rolling` | input, prediction and behavior drift |
| `GET /v1/model` | machine-readable model card |

## Rules that are easy to break by accident

**Contract (ADR-01 to ADR-04)**
- Text: Portuguese, up to 2,000 characters. Batch: 1 to 50 items. Contract errors reject the whole batch with 422.
- No minimum length: only empty or whitespace-only text is a 422. Text with no letter or digit (emoji or
  punctuation only) is out of distribution with `low_text_quality`. Short text such as "ok" goes to the
  model, which abstains if it finds nothing.
- Text above the training p99 length gets `warning: length_above_training_p99`, not a rejection.
- Rating, app version and date are optional inputs. **The rating is never a model feature**; it is logged
  for monitoring only.
- Out of distribution is decided per item and returns 200 with `ood_reason` in
  `language | low_text_quality | off_domain`.

**Semantics (ADR-05, ADR-06)**
- `tema` is multi-label with two escape values: `outro` (a complaint about something off the list) and
  `nenhum` (no problem described). They are mutually exclusive with each other and with the other labels.
- `bloqueio = nao_da_para_saber` is a label about the text. Abstention is the model refusing. Never merge them.

**Evaluation (ADR-07 to ADR-09)**
- Hand-labeled data splits into **calibration (40%)** and **test (60%)**. Thresholds and detectors are
  tuned on calibration only. Metrics are reported on test only. Mixing them is leakage.
- Abstention threshold per attribute (and per label for `tema`), chosen for precision >= 0.80 on calibration.
  If no `tema` label passes, the attribute abstains; it never falls back to `outro`.
- A class with fewer than 30 test examples is reported as "insufficient evidence", not as a number.
- Report LLM-vs-human kappa per attribute: it is the ceiling of this project.

**Drift and health (ADR-10 to ADR-15)**
- The weekly job deduplicates by review ID and logs the duplicate rate; it calls the real API with
  `source: scheduled_ingest`.
- A drift window with fewer than 200 records returns `insufficient_data`, never a PSI.
- `freshness` passes only if the last ingest is under 8 days old, brought more than zero new records,
  and every new record has a logged prediction. Exit code zero is not delivery.
- The canary compares against the model's own predictions frozen at deploy, not human labels.
- `/v1/health` returns 200 with `status` in the body. Never 503 on canary failure: it would trigger a
  restart loop that hides the problem.

**Reviews without app version**
- Never filter out or drop reviews whose `app_version` is empty. "Without version" is a category of
  its own in any analysis or monitoring by version (drift per version, per-version splits, charts).
- Why: it is not missing at random. In notebook 01 (section 4b), 7.4% of reviews have no version,
  and they are a more dissatisfied group: 50.6% have 1 star against 25.7%, and the gap holds within
  the same quarter (26 of 27) and the same length band. Dropping them makes the app look better.

**Personal data in review text (scope lock 5)**
- Review text itself can carry personal data: 103 collected reviews (0.013%) contain a CPF-shaped
  number, a phone number, an e-mail or a self-introduction with a name. Dropping the author columns
  does not remove it.
- **Mask CPF numbers, phone numbers, e-mails and names in the text before sending anything to an
  LLM** (training-set labeling and the cost benchmark, step 4). No unmasked text leaves the machine,
  in any batch, ever.
- **Mask the number, never the word "cpf".** The word appears in 4,410 reviews (0.55%) as the
  subject of the complaint and identifies nobody; masking it would erase the topic the classifier
  must read. Match CPF numbers with any separators (dots, dashes, spaces) or none.
- Notebooks may count these patterns but never print texts that match them. Printed examples also
  skip texts with the word "cpf", as a margin for numbers written in forms the pattern misses.

**Day one (ADR-21)**
- The response schema in `src/govbr_classifier/api/schemas.py` is frozen. Attributes not yet implemented
  abstain with `reason: not_implemented`. Improving the model changes only `model_version`.

## Repository map

```
data/              never committed; see data/README.md for layout and privacy rules
docs/adr/          architecture decision records
docs/rubric/       annotation rubric (written before annotating)
models/            artifacts; not committed
notebooks/         exploration only; anything reusable moves to src/
scripts/           CLI entry points (collect, label, train, benchmark)
src/govbr_classifier/
  taxonomy.yaml    closed label lists; ships inside the package so the container can read it
  settings.py      runtime settings via pydantic-settings, read from the environment
  api/             FastAPI app, schemas, routes
  guards/          contract checks and out-of-distribution detectors
  models/          baseline and trained classifiers behind one interface
  monitoring/      drift statistics, health checks, prediction log
  data/            Google Play collection and dataset building
  labeling/        LLM labeling with closed-list validation
  evaluation/      per-class metrics, calibration, agreement
tests/             unit tests mirror src/; integration tests are marked
```

## Commands

```
make install     # creates .venv-govbr-complaint-classifier + all extras + git hooks + Jupyter kernel
source .venv-govbr-complaint-classifier/bin/activate   # prompt shows (govbr-complaint-classifier)
make test        # fast suite
make lint        # ruff
make typecheck   # mypy
make api         # local API at http://localhost:8000/docs
```

## Working conventions

- Small, reviewable steps. One concern per commit, conventional commit messages (`feat:`, `fix:`, `docs:`).
- Every function in `src/` has type hints. Every behavior in the rules above has a test.
- Notebooks are numbered (`01_`, `02_`) and never imported from. Outputs are stripped before commit.
- Never print or log raw review text with author names. Never commit anything under `data/`.
- Before claiming a task is done, run `make lint test` and report the result honestly.

# Data

Nothing in this folder is committed except this file and the empty folder markers.

## Source

Google Play reviews of the gov.br app, package `br.gov.meugovbr` (verified 2026-10-31: title
"gov.br", developer "Serviços e Informações do Brasil", listed on Google Play on 2020-04-27), with
`lang=pt` and `country=br`. Collected with google-play-scraper 1.2.7, newest first.

First full collection (run `20261031T144059Z`, 2026-10-31): stopped at `end_of_history` after 801
pages of 1,000 with no retries, in 57 minutes. **800,069 reviews**, against 803,198 written reviews
shown on the store page at the same time (99.6%; the store count covers every language). The oldest
review reached is dated **2020-05-01**, four days after the listing; the newest 2026-10-30. No
duplicate review IDs across the run.

## Layout

| Folder | Contents | Written by |
| --- | --- | --- |
| `raw/<run_id>/` | One collection run: `part-*.parquet` exactly as collected (author fields included), `state.json` to resume, `metadata.json` | `scripts/collect_reviews.py` |
| `interim/` | `reviews.parquet`, one row per review ID, no authorship, plus `reviews.metadata.json` | `scripts/build_interim.py` |
| `labeled/llm/` | Training set labeled by the LLM, with prompt version and model id | `scripts/label_with_llm.py` |
| `labeled/human/` | Hand annotations: `calibration` (40%) and `test` (60%) splits | manual annotation |
| `reference/` | Frozen drift reference snapshot, with collection window and app version | dataset building |
| `local/` | Local SQLite prediction log for development | the API |

### raw metadata

`metadata.json` records the parameters (app id, language, country, sort, page size, pause), the
library and Python versions, the process time zone, an app store snapshot at collection time
(version, ratings, review count), pages, rows, retries, seconds per page, the review date window
and the **stop reason**. `status` is `in_progress` until the run ends and `complete` only when the
stop reason is `end_of_history`. A run stopped by a page limit or by repeated errors is `stopped`,
and `scripts/build_interim.py` refuses it unless told the history is partial.

### interim columns

| Column | Meaning |
| --- | --- |
| `review_id` | Google Play review ID, unique in this table |
| `text` | The review text exactly as collected; no cleaning at this step |
| `score` | Star rating 1 to 5. Monitored, never a model feature (ADR-01) |
| `thumbs_up` | "Helpful" votes at collection time |
| `app_version` | App version attached to the review; may be empty (see limitations) |
| `at` | Review date, UTC (see limitations: last edit, not first publication) |
| `has_reply` | Whether the developer replied |
| `replied_at` | Reply date, UTC |
| `reply_delay_hours` | `replied_at - at` in hours; negative when the review was edited after the reply |

`reviews.metadata.json` records the source runs, whether they cover the whole history, the rows
before and after deduplication, the duplicate rate, the IDs edited during collection, and the
review date window.

## Privacy rules

- Reviews carry authorship. The raw runs keep it, on this machine only.
- `interim/` drops the author name (`userName`), the profile picture URL (`userImage`, as
  identifying as the name) and the text of the developer's reply (`replyContent`, which often
  greets the author by name). Columns are taken from an allowlist, so a field the scraper adds
  later is dropped until someone decides otherwise.
- The reply text stays in raw for a possible future anonymized use; it is never published with
  authorship.
- **The text itself can carry personal data.** In the first full collection, 4,415 reviews
  (0.55%) mention a CPF or contain a CPF-like number, and 94 introduce the author by name. Dropping
  columns does not remove them: any published sample must scrub the text, not only the columns.
  Notebooks count these patterns and skip them when printing examples.
- Never publish raw text with authorship. Publish only aggregates, an anonymized sample, and the
  collection code. Notebooks read `interim/`, never `raw/`.
- The API never stores input text, only a salted hash (ADR-17).

## Known limitations of the source

- **The review date is the date of the last edit**, not of first publication. Google Play exposes
  one timestamp per review. A review written in 2021 and edited in 2024 appears in 2024. Measured
  evidence: in the 2026-10-31 pilot, 39 replies are dated before their review, which can only
  happen when the review was edited after the reply.
- **The app version is one ambiguous field.** The library fills `appVersion` and
  `reviewCreatedVersion` from the same position of the response; whether it is the version at
  creation or at the last edit is not documented.
- **Dates depend on the time zone of the collecting machine** in the library. The collector forces
  UTC and keeps the raw epoch seconds; `interim` dates are built from the epochs.
- **Language filter.** `lang=pt` returns reviews Google classifies as Portuguese; the store's total
  review count covers every language, so the collected total is expected to be lower.
- **Text length is capped at 500 characters for recent reviews only.** 132 reviews are longer,
  up to 2,006 characters; 128 of them are from 2020 to 2022. The p99 over the whole history is 384
  characters. A model trained on this data has seen very few texts above 500 characters, and none
  above 2,006, even though the API contract accepts up to 2,000.

## Reproducibility

Every file records its collection timestamp and the app version range it covers. The calibration and test
splits are fixed with a seed and never re-drawn after annotation starts.

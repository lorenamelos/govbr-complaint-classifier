# Data

Nothing in this folder is committed except this file and the empty folder markers.

## Layout

| Folder | Contents | Written by |
| --- | --- | --- |
| `raw/` | Reviews as returned by google-play-scraper, one Parquet file per collection run | `scripts/collect_reviews.py` |
| `interim/` | Deduplicated, cleaned reviews | dataset building |
| `labeled/llm/` | Training set labeled by the LLM, with prompt version and model id | `scripts/label_with_llm.py` |
| `labeled/human/` | Hand annotations: `calibration` (40%) and `test` (60%) splits | manual annotation |
| `reference/` | Frozen drift reference snapshot, with collection window and app version | dataset building |
| `local/` | Local SQLite prediction log for development | the API |

## Privacy rules

- Reviews carry author names. Drop the author field at the `interim/` step; it is never needed downstream.
- Never publish raw text with authorship. Publish only aggregates, an anonymized sample, and the collection code.
- The API never stores input text, only a salted hash (ADR-17).

## Reproducibility

Every file records its collection timestamp and the app version range it covers. The calibration and test
splits are fixed with a seed and never re-drawn after annotation starts.

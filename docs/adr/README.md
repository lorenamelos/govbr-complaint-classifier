# Architecture decision records

The full reasoning for each decision (context, decision, why, rejected alternative) lives in the project's
architecture document. This index is the in-repo summary; when a decision changes, add a dated line under
it instead of rewriting.

| ADR | Decision |
| --- | --- |
| 01 | Input: text required; rating, app version, date optional. Rating is monitored, never a feature. Train on all ratings. |
| 02 | Three response layers: 422 rejects the batch; out of distribution is 200 per item; abstention is 200 per attribute. |
| 03 | Portuguese only, 3 to 2,000 chars, 1 to 50 items. Above training p99 length gets a warning, not a rejection. |
| 04 | Three OOD detectors with named reasons: language, low_text_quality, off_domain. |
| 05 | `tema` has `outro` (unlisted complaint) and `nenhum` (no complaint), mutually exclusive. `tipo` has `nenhum`. |
| 06 | `nao_da_para_saber` is a label about the text; abstention is the model refusing. Kept separate. |
| 07 | Hand labels split into calibration (40%) and test (60%). Classes with fewer than 30 test examples report "insufficient evidence". |
| 08 | Abstention per attribute, threshold for precision >= 0.80 on calibration. Publish coverage and the precision-coverage curve. |
| 09 | Written rubric for acionabilidade; report self-agreement (10% re-annotation) and LLM-vs-human kappa per attribute. |
| 10 | Weekly job collects, deduplicates by review ID, logs the duplicate rate, and calls the real API as `scheduled_ingest`. |
| 11 | Fixed reference (training snapshot) and rolling reference (4 vs 4 weeks), at input, prediction and behavior levels. Under 200 records returns `insufficient_data`. |
| 12 | Monthly random sample of 40 reviews from the job, hand-labeled, published with its confidence interval. |
| 13 | `/v1/health` reports alive, integrity, canary, freshness and drift, each named. |
| 14 | Canary checks reproducibility against frozen predictions; `/health/live` is separate and always 200. |
| 15 | Freshness means delivery: last ingest under 8 days, more than zero new records, a prediction logged for each. |
| 16 | FastAPI in Docker on Hugging Face Spaces; job on GitHub Actions; latency split by cold and warm, server and client. |
| 17 | Postgres log with salted text hash, scores, latency, cost, model version and source. Raw text is never stored. |
| 18 | Open API, 30 requests per minute per IP, 50 items per call. |
| 19 | LLM-in-production scenario measured offline; classifier cost published as CPU seconds at a paid-instance price. |
| 20 | Two LLMs from one provider (large and small), with per-class quality next to cost. |
| 21 | Response schema frozen on day one; unimplemented attributes abstain with `not_implemented`. |

## Scope changes

- 2026-10-29: Google Play is the only data source. App Store, Instagram and TikTok were evaluated and left out.

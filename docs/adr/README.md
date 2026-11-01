# Architecture decision records

The full reasoning for each decision (context, decision, why, rejected alternative) lives in the project's
architecture document. This index is the in-repo summary; when a decision changes, add a dated line under
it instead of rewriting.

| ADR | Decision |
| --- | --- |
| 01 | Input: text required; rating, app version, date optional. Rating is monitored, never a feature. Train on all ratings. |
| 02 | Three response layers: 422 rejects the batch; out of distribution is 200 per item; abstention is 200 per attribute. |
| 03 | Portuguese only, up to 2,000 chars, no minimum (only empty or whitespace-only is 422), 1 to 50 items. Above training p99 length gets a warning, not a rejection. |
| 04 | Three OOD detectors with named reasons: language, low_text_quality, off_domain. |
| 05 | `tema` has `outro` (unlisted subject), `nenhum` (no complaint) and `nao_especificado` (complaint with no subject), mutually exclusive. `tipo` has `nenhum`. |
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
| 16 | FastAPI in Docker as a Render web service (free plan, virginia); job on GitHub Actions; latency split by cold and warm, server and client. |
| 17 | Postgres log with salted text hash, scores, latency, cost, model version and source. Raw text is never stored. |
| 18 | Open API, 30 requests per minute per IP, 50 items per call. |
| 19 | LLM-in-production scenario measured offline; classifier cost published as CPU seconds at a paid-instance price. |
| 20 | Two LLMs from one provider (large and small), with per-class quality next to cost. |
| 21 | Response schema frozen on day one; unimplemented attributes abstain with `not_implemented`. |

## Dated notes

- 2026-10-30 (ADR-21): `model_version` follows `YYYY.MM.N-description`. `YYYY.MM` is the month the
  model was frozen, `N` counts models frozen that month from 1, the description is lowercase kebab-case.
  The first served model is `2026.10.1-tema-keyword-baseline` (was `tema-keyword-baseline-v1`). The
  format is checked at import time (`src/govbr_classifier/models/version.py`).
- 2026-10-30 (ADR-18): the rate limit is a small middleware over the `limits` library, keyed on the
  rightmost X-Forwarded-For entry, with one counter per IP for every path under `/v1/`. It runs before
  body validation, so 422s count. slowapi was dropped: its middleware cannot find route handlers in
  routers included with FastAPI 0.162 and exempts those requests silently, so nothing was limited.
- 2026-10-30 (ADR-16): the API moves from Hugging Face Spaces to a Docker web service on Render's free
  plan, region virginia, because Docker Spaces started to be charged. The image is unchanged except
  that it listens on `$PORT` (default 7860). `render.yaml` reproduces the service. Render polls
  `/health/live` only, so ADR-14 holds. The free plan stops after 15 minutes idle and takes about a
  minute to wake, which makes the cold/warm latency split matter more. The prediction-log Postgres
  (ADR-17) will live in the same region.
- 2026-10-31 (ADR-13, pending): when `/v1/health` is built, the count of rate-limit requests that
  could not be tied to a client (`unresolved`, per reason: `sources_disagree`, `no_client_entry`,
  `invalid_entry`, `no_address`) enters its alarm level. Today it exists only as a warning in the
  platform logs and as `client_ip.unresolved_totals()`. A rising count means the proxy chain in front
  of the app changed or the copied Cloudflare ranges are stale, and every such request shares one
  counter: it must be visible in the health report, not only in logs.
- 2026-10-31 (ADR-18): the rate-limit key is no longer the rightmost X-Forwarded-For entry. Behind
  Cloudflare and Render that entry is a Render internal proxy that rotates, so one client got one
  counter per proxy (silent failure 3). The key now comes from `api/client_ip.py`: a right-to-left
  walk of X-Forwarded-For that skips internal networks and Cloudflare's published ranges,
  cross-checked with `CF-Connecting-IP`; disagreement goes to a shared `unresolved` counter with a
  warning. IPv6 is counted per /64. Known limitation: a client on both IPv4 and IPv6 is two keys,
  at most twice the limit. Verified in production on 2026-10-31.
- 2026-10-31 (ADR-03): the long-text warning threshold is the p99 length of the training set,
  computed when that set exists; it is not fixed by hand. Current estimates from notebook 01: 384
  characters counting every review, 484 counting each distinct text once, so the value depends on
  whether training is deduplicated. The 2,000-character contract maximum stays.
- 2026-10-31 (ADR-07): splits are by group, never by row. A group is every review whose normalized
  text (case, accents, punctuation and spacing ignored) is identical, and all copies go to the same
  side. The most recent months are held out for test, so the model is always evaluated on text
  newer than what it learned from. Why: in a random 80/20 split, 61.4% of test reviews have an
  identical normalized twin in train (5.2% among texts of 5+ words), and near-duplicates add more.
- 2026-10-31 (ADR-07): annotation samples unique normalized texts, stratified by rating and length
  to favor complaints, and records each item's selection probability. Calibration and test metrics
  are computed per unique text and weighted by frequency (inverse selection probability times the
  number of reviews sharing the text), so thresholds are tuned for the traffic the API serves.
  Why: deduplicating moves 1-2 star reviews from 31.5% of reviews to 61.2% of unique texts, and
  precision depends on prevalence; an unweighted precision of 0.80 on the sample would not hold in
  production.
- 2026-11-01 (ADR-03): the 3-character minimum is removed. A 422 now means only empty or
  whitespace-only text. Text with no letter and no digit (emoji or punctuation only) is
  `out_of_distribution` with `low_text_quality`, decided per item by `guards/text_quality.py`, the
  first ADR-04 detector. Short text such as "ok" reaches the model, which abstains if it finds
  nothing. Why, measured in notebook 01: the old rule returned 422 for 1.72% of real reviews
  (13,770), 10,182 of them "ok", and a contract error rejects the whole batch, so one "ok" took up
  to 49 valid reviews with it. Of those 13,770, 3,226 have no letter or digit and are now
  `low_text_quality`; 10,544 are classified. The change only widens accepted input; the response
  schema is unchanged (ADR-21).
- 2026-11-01 (ADR-05): `tema` gains `nao_especificado`, a complaint with no identifiable subject
  ("péssimo", "horrível", "não funciona" alone), exclusive like `outro` and `nenhum`. Why: filed
  under `outro`, these texts would pollute the new-theme alarm that `outro` feeds, since a rise in
  `outro` should mean an unknown subject, not an angrier mood. It is a label about the text, not an
  abstention (the same line as ADR-06), and applies to `tema` only: `tipo` and `bloqueio` are
  annotated as usual ("não funciona" is usually `tipo = bug`). Taxonomy goes to version 2.
  Obligation ("me obrigam a...") is not a label: the rubric annotates it by the mechanism cited. It
  appears in 1,677 reviews (0.78% of unique 1-2 star texts); 30 test cases would need about 6,400
  hand labels from that pool, so it becomes a label only if the annotated test set reaches 30.
- 2026-11-01 (ADR-05): obligation with no mechanism cited ("é obrigatório usar o app pra tudo")
  goes to `tema = outro`, with "obrigatoriedade" in the note. Why: the obligation itself is then
  the subject, it is a candidate for a new theme, and `outro` is what feeds the new-theme alarm.
  When a mechanism is cited, the theme is that mechanism's ("me obrigam a fazer reconhecimento
  facial" is `verificacao_identidade`). Rubric version 3 (`docs/rubric/annotation_rubric.pt.md`,
  now the official text, with an English translation) records it.
- 2026-11-01 (ADR-21): `model_version` becomes
  `2026.11.1-tema-keyword-baseline-contract-guard-taxonomy-v2`. The keyword lists did not change,
  but the same input now gets a different answer: "ok" is classified instead of 422, an emoji is
  `low_text_quality` instead of classified, and `tema` has a new value. The prediction log (ADR-17)
  separates behavior by `model_version`; without a new value, drift monitoring would see the
  out-of-distribution rate jump with no recorded cause. The name lists what changed. The baseline
  now checks the taxonomy version at import, so a label change cannot ship under the old name.

## Scope changes

- 2026-10-29: Google Play is the only data source. App Store, Instagram and TikTok were evaluated and left out.

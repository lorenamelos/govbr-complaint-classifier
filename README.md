# gov.br complaint classifier

A classifier of what gov.br app reviews on Google Play complain about, served behind a public API that
says when it does not know.

> Status: first deployable version. A keyword baseline serves `tema` behind the frozen API contract;
> the trained model, out-of-distribution detection, prediction log and evaluation are built in the
> order set in [ADR-21](docs/adr/README.md). This README will carry per-class metrics, measured cost
> and latency, and what the model does not do, as each piece lands.

## What it classifies

Four attributes, each with a closed label list (`src/govbr_classifier/taxonomy.yaml`):

| Attribute | Question | Cardinality |
| --- | --- | --- |
| `tema` | What is the review about? | multi-label |
| `bloqueio` | Did the person manage to do what they wanted? | single |
| `tipo` | Bug, feature request or general dissatisfaction? | single |
| `acionabilidade` | Is there enough information to act? | single |

## Design principle

When the system does not know, it says so, with a reason: invalid input gets `422`, out-of-distribution
input gets a named reason, and low confidence gets an explicit abstention per attribute. The health check
reports five named levels instead of a single boolean. See [the decision records](docs/adr/README.md).

## Quick start

```bash
make install      # creates .venv-govbr-complaint-classifier, installs everything, sets up git hooks
cp .env.example .env
make test
make api          # http://localhost:8000/docs
```

## Public API

Live at `https://govbr-complaint-classifier.onrender.com`, a Docker web service on Render's free
plan (`render.yaml`). Interactive docs at `/docs`.

```bash
curl -X POST https://govbr-complaint-classifier.onrender.com/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"items": [
        {"id": "1", "text": "Nao consigo fazer login, o app trava na tela de senha"},
        {"id": "2", "text": "Atualizei e agora tudo certo"}
      ]}'
```

Response (`request_id` and `latency_ms` vary):

```json
{
  "request_id": "12fadd77-2411-4c97-8ee6-124da855b252",
  "model_version": "2026.10.1-tema-keyword-baseline",
  "results": [
    {
      "id": "1",
      "status": "classified",
      "ood_reason": null,
      "warnings": [],
      "attributes": {
        "tema": {
          "status": "predicted",
          "labels": ["login_autenticacao", "travamento"],
          "scores": {"login_autenticacao": 1.0, "travamento": 1.0},
          "reason": null
        },
        "bloqueio": {"status": "abstained", "label": null, "score": null, "top_candidate": null, "threshold": null, "reason": "not_implemented"},
        "tipo": {"status": "abstained", "label": null, "score": null, "top_candidate": null, "threshold": null, "reason": "not_implemented"},
        "acionabilidade": {"status": "abstained", "label": null, "score": null, "top_candidate": null, "threshold": null, "reason": "not_implemented"}
      }
    },
    {
      "id": "2",
      "status": "classified",
      "ood_reason": null,
      "warnings": [],
      "attributes": {
        "tema": {"status": "abstained", "labels": [], "scores": {}, "reason": "below_threshold"},
        "bloqueio": {"status": "abstained", "label": null, "score": null, "top_candidate": null, "threshold": null, "reason": "not_implemented"},
        "tipo": {"status": "abstained", "label": null, "score": null, "top_candidate": null, "threshold": null, "reason": "not_implemented"},
        "acionabilidade": {"status": "abstained", "label": null, "score": null, "top_candidate": null, "threshold": null, "reason": "not_implemented"}
      }
    }
  ],
  "latency_ms": {"server": 0.081}
}
```

Liveness, polled by the platform:

```bash
curl https://govbr-complaint-classifier.onrender.com/health/live
# {"status":"alive"}
```

### What is served today, and what is not

- **Model**: `2026.10.1-tema-keyword-baseline`, a keyword list written before any data was collected.
  It has **no measured metrics**. It fills `tema` only; the other three attributes always abstain with
  `not_implemented`. For `tema`, `below_threshold` here means no keyword matched: the attribute abstains
  instead of guessing `outro`. On the 800,069 collected reviews it abstains on 52.6%.
  **Known problem:** praise of the support channel is classified as a complaint. In "atendimento
  ótimo", "atendimento" matches the `atendimento` theme and "ótimo" matches `nenhum`; since a
  problem label always wins over `nenhum` (ADR-05), the review comes back as a complaint about
  support. Topic words such as "atendimento", "suporte" and "chat" name a subject, not a problem.
  Left as is until the keyword lists are re-derived from labeled data.
- **Out of distribution**: not detected yet. Every valid item comes back `classified`, including text
  that is not a gov.br review.
- **Prediction log: not active yet.** Requests are not recorded anywhere (ADR-17 is the next build
  step), so there is no drift, canary or freshness reporting, and `/v1/health`, `/v1/drift` and
  `/v1/model` do not exist yet.
- **Rate limit: active.** 30 requests per minute per client across `/v1/`, including requests
  rejected with 422. A client is its IPv4 address or its IPv6 /64. Over the limit you get `429`
  with `Retry-After`; every `/v1/` response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining`
  and `X-RateLimit-Reset`. Known limitation: a client that uses both IPv4 and IPv6 is counted
  twice, so it can get up to 60. See [silent failure 3](docs/silent_failures.md).
- **Contract**: 1 to 50 items per call, Portuguese text of 3 to 2,000 characters. Any contract error
  rejects the whole batch with `422`.
- **Cold start**: the free plan stops the service after 15 minutes without traffic. The next call wakes
  it and can take about a minute; later calls are warm. Latency is reported split by cold and warm
  (ADR-16), so a slow first call is expected, not a fault.

## Silent failures caught

When a check passes while the system is not doing what it claims, that failure is recorded in
[docs/silent_failures.md](docs/silent_failures.md): what failed, why nothing said so, how it was
caught and what stops it from coming back. Four so far: the taxonomy missing from the installed
package, a rate limiter that exempted every route, several rate-limit counters for one client in
production, and a scraper that reports a failure as the end of the history.

## Data and privacy

Reviews are public, but carry authorship. This repository publishes only collection code, aggregates and an
anonymized sample. The API stores a salted hash of each input, never the text. See [data/README.md](data/README.md).

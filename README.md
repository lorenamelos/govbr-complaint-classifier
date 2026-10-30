# gov.br complaint classifier

A classifier of what gov.br app reviews on Google Play complain about, served behind a public API that
says when it does not know.

> Status: scaffolding. The API, model and evaluation are built in the order set in
> [ADR-21](docs/adr/README.md). This README will carry per-class metrics, measured cost and latency, and
> what the model does not do, as each piece lands.

## What it classifies

Four attributes, each with a closed label list (`config/taxonomy.yaml`):

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
make install      # creates .venv, installs everything, sets up git hooks
cp .env.example .env
make test
make api          # http://localhost:8000/docs
```

## Data and privacy

Reviews are public, but carry authorship. This repository publishes only collection code, aggregates and an
anonymized sample. The API stores a salted hash of each input, never the text. See [data/README.md](data/README.md).

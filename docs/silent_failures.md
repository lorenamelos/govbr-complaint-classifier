# Silent failures caught

A silent failure is one where the system kept answering, or the checks kept passing, while
something it claimed to do was not happening. This project exists to make uncertainty visible, so
each one caught is recorded here: what failed, why nothing said so, how it was found, and what now
stops it from coming back. Entries are never deleted; a later finding is added as a dated line.

## 1. The taxonomy lived outside the package (2026-10-29)

**What failed.** `taxonomy.py` found `config/taxonomy.yaml` through a path derived from the source
tree. That path exists only in an editable install. The serving image runs `pip install .`, so the
package lives in `site-packages` and the import of the API raised `FileNotFoundError`.

**Why nothing said so.** Every check ran on an editable install: the test suite, lint, type check
and local `make api` all passed. The Docker build would also have passed, because nothing is
imported at build time. The first sign would have been a deployed service that never started.

**How it was caught.** Reviewing the deploy plan: the Dockerfile installs non-editable, and
`PROJECT_ROOT = parents[2]` points elsewhere once installed. Reproduced in a throwaway non-editable
venv before changing anything.

**What prevents it now.** The taxonomy ships inside the package (`src/govbr_classifier/`) and is
resolved next to its module. `scripts/smoke_installed.py` calls `/v1/classify` against a
non-editable install outside the repository, in CI and as `make smoke-installed`. The CI `docker`
job builds the image, runs it, and calls it.

## 2. slowapi exempted every route without saying so (2026-10-30)

**What failed.** The rate limit (ADR-18) was wired through slowapi's middleware. To decide what
to limit, the middleware looks up the route handler; when it finds none, it exempts the request.
With FastAPI 0.162, routers added with `include_router` are wrapped in an object that has no
handler at that level, so every request went through with no limit and no error.

**Why nothing said so.** Exemption is a normal, silent outcome in slowapi. Requests returned 200
as before; there was no log line, no warning, no header that would differ.

**How it was caught.** The first test written for the limit (31 calls, the last must be 429)
failed with a 200. Reading slowapi's middleware showed the exemption path.

**What prevents it now.** slowapi was dropped. The limit is a small middleware over the `limits`
library that keys on the path prefix `/v1/`, which does not depend on how FastAPI nests routes.
Tests pin: the call over the limit gets 429, 422s count toward the limit, forged left entries of
X-Forwarded-For do not escape it, and liveness is never limited. See the dated note under ADR-18.

## 3. Several rate-limit counters for one client in production (2026-10-30, open)

**What failed.** In production, 40 calls from one notebook within one minute showed three
interleaved `X-RateLimit-Remaining` countdowns (29 appeared three times), and 200s came after 429s.
One client was being counted in three places, so the effective limit was a multiple of 30.

**Why nothing said so.** Every call got a valid answer and valid rate-limit headers. The unit tests
passed because they control X-Forwarded-For. The `rate_limit.py` docstring claimed that an
unexpected proxy chain could only produce more 429s, never less limit; that claim was wrong.

**How it was caught.** Measuring from outside after deploy, and reading the sequence of
`X-RateLimit-Remaining`, not just the status codes. A first test from two devices could not have
caught it: they entered Cloudflare at different points (CNF and GRU) and would get separate
counters either way.

**Hypotheses.**

- *Several worker processes, each with its own in-memory counter.* uvicorn takes its worker count
  from `$WEB_CONCURRENCY` when `--workers` is not given, and Render sets that variable at runtime
  for services created after 2025-12-08. Reproduced locally with `WEB_CONCURRENCY=3`. **Tested and
  discarded for production:** the Render logs show one `Started server process [1]` per instance,
  and the measurement ran on a single instance with a single process. `--workers 1` is now pinned
  anyway, and CI checks it, because the in-memory counter requires it.
- *The rate-limit key rotates between proxies.* The key is the rightmost X-Forwarded-For entry.
  With Cloudflare in front of Render, that entry may be a proxy address that varies per request,
  so each proxy gets its own counter. **Under diagnosis** with `RATE_LIMIT_DIAGNOSTICS=1`, which
  logs the shape of the IP headers and never an address (`api/ip_diagnostics.py`).

**What prevents it now.** Pending the diagnosis. Already in place: `--workers 1` with a CI check,
and `scripts/check_single_counter.py`, which fails on a repeated `remaining` value or a 200 after
a 429 and is the check to repeat against production after the fix.

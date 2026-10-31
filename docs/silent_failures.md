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

## 3. Several rate-limit counters for one client in production (2026-10-30, closed 2026-10-31)

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
- *The rate-limit key rotates between proxies.* **Confirmed.** A temporary diagnostic (removed
  after the fix) logged the shape of the IP headers on each call, never an address: counts,
  header names, positions, and the class of each entry. On every call, from the left,
  X-Forwarded-For was `<client>, <Cloudflare edge>, <Render internal proxy>`; the key was the
  rightmost entry, a private address that took three distinct values in one process. That is the
  three counters. `CF-Connecting-IP` and `True-Client-IP` both matched the entry at -3. A forged
  X-Forwarded-For entry landed on the left and the client stayed at -3. A forged
  `CF-Connecting-IP` never reached the app: Cloudflare answered 403.

**Fix.** `api/client_ip.py` takes the key from two sources and requires them to agree: a walk of
X-Forwarded-For from the right that skips internal networks and Cloudflare's published ranges,
and `CF-Connecting-IP`. Disagreement, an invalid entry or a chain of proxies only goes to one
shared `unresolved` counter, with a warning that carries no address. IPv6 is counted per /64.

**Verified in production (2026-10-31).** Two runs of `scripts/check_single_counter.py` against the
service: one countdown from 29 to 0, then only 429s, `OK: one counter` both times. No
`rate_limit_unresolved` line in the Render logs for the hour after the fix.

**Known limitation, not fixed.** A client that reaches the service over both IPv4 and IPv6 is two
keys, an IPv4 address and an IPv6 /64, so it can get up to twice the limit. Seen in the
verification: after the notebook was limited, a phone on the same Wi-Fi still got a 200. The
network has IPv6 (`curl -6` to `/health/live` returned 200), so the likely explanation is the
notebook leaving over IPv4 and the phone over IPv6; this was not confirmed per request. The two
address families cannot be tied to one client from the headers, and the cap is a factor of two,
not an open-ended multiple, so this is accepted rather than fixed.

**What prevents it now.**

- `tests/unit/test_client_ip.py` reproduces the production header shape with the Render proxy
  rotating; it failed with a 200 on call 31 before the fix. Other tests pin that forged entries do
  not escape, that the entry point does not matter, that two clients behind the same proxies are
  counted apart, and that a stale Cloudflare list or a forged `CF-Connecting-IP` goes to
  `unresolved` with a warning that holds no address.
- A weekly workflow (`.github/workflows/cloudflare-ranges.yml`) fails when the copied Cloudflare
  ranges differ from the published ones, before a stale list turns into 429s in production.
- `scripts/check_single_counter.py` is the external check to repeat after any change to the
  platform or the proxy chain.
- Pending (ADR-13): the `unresolved` count enters the alarm level of `/v1/health` when it is built.

## 4. The scraper reports a failure as the end of the history (2026-10-31)

**What failed.** Nothing yet: it was caught before the first full collection. In
google-play-scraper 1.2.7, `reviews()` wraps each request in `except Exception: token = None`, and
an empty token is also how it says there are no more pages. `reviews_all()` stops on that token.
A rate limit, a network error or an unexpected page an hour into a collection would end it early,
and the result would be indistinguishable from the complete history.

**Why nothing would have said so.** The call returns normally, with fewer reviews than exist. The
oldest review date would simply be later than the truth, and every analysis built on it, from
monthly volume to the drift reference, would inherit the gap.

**How it was caught.** Reading the library before relying on it, to decide how to resume a long
collection.

**What prevents it now.** `data/collect.py` calls the one-request function directly, so errors
reach a retry loop with backoff, and every run records why it stopped: `end_of_history`,
`max_pages`, `error_after_retries` or `empty_page_with_token`. Only the first marks the run
`complete`, and `scripts/build_interim.py` refuses an incomplete run unless told the history is
partial, which is then written in the interim metadata. The library is pinned to `==1.2.7`
because the function is private. Tests pin each stop reason.

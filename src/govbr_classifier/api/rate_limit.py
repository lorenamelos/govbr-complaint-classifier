"""Per-IP rate limit for the public API (ADR-18): RATE_LIMIT requests per client IP.

Scope: every path under /v1/ shares one counter per IP. Liveness (/health/live) is outside it,
because the platform polls it (ADR-14), and so are the docs pages.

It runs as middleware, before FastAPI validates the body. A limit attached to the route would run
after validation, so a flood of malformed batches would get free 422s without ever being counted.

Why not slowapi's middleware: it looks up the route handler to decide what to limit, and when it
cannot find one it exempts the request without saying so. Routers included with FastAPI 0.162 have
no handler at that level, so every request went through unlimited. This module keys on the path
prefix instead, which does not depend on how FastAPI nests routes.

Counters live in process memory, so the limit is correct only while exactly one process serves the
API: with N processes, each keeps its own counter and a client gets up to N times the limit. The
Dockerfile pins `--workers 1` for this reason; CI checks it. Counters reset on restart, which is
acceptable for abuse protection and is not a quota.

The client IP comes from the rightmost X-Forwarded-For entry. The leftmost entries are written by
the client and can be forged, so keying on them would let anyone escape the limit by sending a
different header on each call. Keying on the rightmost entry is correct only if the proxy that
appends it sits directly in front of the app and writes the client's address. When another proxy
layer sits in between, the rightmost entry is that layer's address. If the layer is one fixed
address, every client shares one counter (more 429s). If it is a pool, each proxy in the pool gets
its own counter and the effective limit multiplies, with nothing failing visibly. The second case
is the dangerous one.

Measured on 2026-10-30, Cloudflare in front of Render: one client, one process, three interleaved
counters. The rightmost entry is not a stable client key there; the fix is pending diagnosis.
"""

import math
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from govbr_classifier.api import ip_diagnostics
from govbr_classifier.settings import get_settings

LIMITED_PREFIX = "/v1/"

_storage = MemoryStorage()
_window = FixedWindowRateLimiter(_storage)
_limit: RateLimitItem = parse(get_settings().rate_limit)


def client_ip(request: Request) -> str:
    """Return the address the limit is counted against."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def reset() -> None:
    """Clear every counter. Used by tests; the API never calls it."""
    _storage.reset()


def _headers(key: str) -> dict[str, str]:
    stats = _window.get_window_stats(_limit, key)
    return {
        "X-RateLimit-Limit": str(_limit.amount),
        "X-RateLimit-Remaining": str(stats.remaining),
        "X-RateLimit-Reset": str(math.ceil(stats.reset_time)),
    }


async def rate_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Count the call against the client IP; over the limit, answer 429 and skip the route."""
    if not request.url.path.startswith(LIMITED_PREFIX):
        return await call_next(request)

    key = client_ip(request)
    if get_settings().rate_limit_diagnostics:
        ip_diagnostics.log_request_shape(request, key)
    if not _window.hit(_limit, key):
        headers = _headers(key)
        retry_after = max(1, math.ceil(float(headers["X-RateLimit-Reset"]) - time.time()))
        return JSONResponse(
            status_code=429,
            content={"detail": f"rate limit exceeded: {_limit.amount} requests per IP"},
            headers={**headers, "Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    response.headers.update(_headers(key))
    return response

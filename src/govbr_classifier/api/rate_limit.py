"""Per-IP rate limit for the public API (ADR-18): RATE_LIMIT requests per client IP.

Scope: every path under /v1/ shares one counter per IP. Liveness (/health/live) is outside it,
because the platform polls it (ADR-14), and so are the docs pages.

It runs as middleware, before FastAPI validates the body. A limit attached to the route would run
after validation, so a flood of malformed batches would get free 422s without ever being counted.

Why not slowapi's middleware: it looks up the route handler to decide what to limit, and when it
cannot find one it exempts the request without saying so. Routers included with FastAPI 0.162 have
no handler at that level, so every request went through unlimited. This module keys on the path
prefix instead, which does not depend on how FastAPI nests routes.

Counters live in process memory. The service runs one process, so this is one shared counter; it
resets on restart, which is acceptable for abuse protection and is not a quota.

The client IP comes from the rightmost X-Forwarded-For entry, the one appended by the proxy in
front of the app. The leftmost entries are written by the client and can be forged, so keying on
them would let anyone escape the limit by sending a different header on each call. If the platform
chains more proxies than expected, the rightmost entry is a proxy address and every client shares
one bucket: the limit then fails toward more 429s, which are visible, never toward no limit.
"""

import math
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

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

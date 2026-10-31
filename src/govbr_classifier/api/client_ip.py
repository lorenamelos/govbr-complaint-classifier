"""Which address the rate limit counts a request against (ADR-18).

Measured in production on 2026-10-31 (silent failure 3, docs/silent_failures.md): requests arrive as
`X-Forwarded-For: <client>, <Cloudflare edge>, <Render internal proxy>`, the Render proxy rotates
between several private addresses, and Cloudflare sets `CF-Connecting-IP: <client>`. Keying on the
rightmost entry therefore gave one counter per Render proxy.

Two sources, each with a different blind spot:

- The walk: read X-Forwarded-For from the right, skip trusted proxies (private networks and
  Cloudflare's published ranges), and take the first address that is not one. Everything right of
  the client is written by infrastructure, so a forged entry, which lands on the left, is never
  reached. Blind spot: if Cloudflare adds a range we have not copied, the walk stops at an edge
  and each edge becomes its own counter, silently.
- CF-Connecting-IP: written by Cloudflare, which answers 403 when a client sends its own (measured).
  Blind spot: a request that reaches the app without Cloudflare can set it to anything.

Rule: when both are present they must agree. Without CF-Connecting-IP the walk decides alone;
without X-Forwarded-For, the connecting address does (local development). Anything else, either
source disagreeing or no client address in the chain, goes to one shared `unresolved` counter and
logs a warning. That fails toward more 429s, which are visible, never toward a multiplied limit.

IPv6 clients are counted per /64: one connection owns the whole prefix and can pick any address in
it on every call.

Warnings carry the reason, the number of occurrences and the class of each X-Forwarded-For entry,
never an address. At most one is written per reason per minute.
"""

import ipaddress
import logging
import time
from collections import Counter

from fastapi import Request

# uvicorn configures this logger at INFO, so warnings reach the platform logs.
logger = logging.getLogger("uvicorn.error")

UNRESOLVED = "unresolved"
WARNING_INTERVAL_SECONDS = 60.0

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# https://www.cloudflare.com/ips-v4 and /ips-v6, copied 2026-10-30. A weekly workflow
# (.github/workflows/cloudflare-ranges.yml) fails when this list falls out of date.
CLOUDFLARE_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)

# Listed explicitly instead of `is_private`, which also covers the documentation ranges.
INTERNAL_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)

_occurrences: Counter[str] = Counter()  # since the last warning, per reason
_totals: Counter[str] = Counter()  # since the process started, per reason (ADR-13, pending)
_last_warning: dict[str, float] = {}


def reset() -> None:
    """Forget unresolved counts and warning times. Used by tests."""
    _occurrences.clear()
    _totals.clear()
    _last_warning.clear()


def unresolved_totals() -> dict[str, int]:
    """Unresolved requests per reason since start, for the future /v1/health alarm (ADR-13)."""
    return dict(_totals)


def _parse(value: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def address_class(value: str) -> str:
    """Return `cloudflare`, `internal`, `other` or `invalid`; never the address itself."""
    address = _parse(value)
    if address is None:
        return "invalid"
    if any(address in network for network in CLOUDFLARE_NETWORKS):
        return "cloudflare"
    if any(address in network for network in INTERNAL_NETWORKS):
        return "internal"
    return "other"


def _bucket(address: IPAddress) -> str:
    if isinstance(address, ipaddress.IPv6Address):
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _unresolved(reason: str, entries: list[str]) -> str:
    """Count an unresolved request and warn at most once per reason per interval."""
    _occurrences[reason] += 1
    _totals[reason] += 1
    now = time.monotonic()
    last = _last_warning.get(reason)
    if last is None or now - last >= WARNING_INTERVAL_SECONDS:
        classes = ",".join(address_class(entry) for entry in entries) or "none"
        logger.warning(
            "rate_limit_unresolved reason=%s occurrences=%d xff_classes=%s",
            reason,
            _occurrences[reason],
            classes,
        )
        _occurrences[reason] = 0
        _last_warning[reason] = now
    return UNRESOLVED


def client_key(request: Request) -> str:
    """Return the rate-limit key for this request: a client address, a /64, or `unresolved`."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded is None:
        host = request.client.host if request.client else ""
        address = _parse(host)
        if address is not None:
            return _bucket(address)
        return host or _unresolved("no_address", [])

    entries = [entry.strip() for entry in forwarded.split(",") if entry.strip()]
    walked: IPAddress | None = None
    for entry in reversed(entries):
        address = _parse(entry)
        if address is None:
            return _unresolved("invalid_entry", entries)
        if address_class(entry) in ("cloudflare", "internal"):
            continue
        walked = address
        break
    if walked is None:
        return _unresolved("no_client_entry", entries)

    cloudflare = request.headers.get("cf-connecting-ip")
    if cloudflare is not None and _parse(cloudflare) != walked:
        return _unresolved("sources_disagree", entries)
    return _bucket(walked)

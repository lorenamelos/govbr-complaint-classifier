"""TEMPORARY: describe where the client address arrives, without logging any address.

Production showed one client, one process and three interleaved rate-limit counters (2026-10-30),
so the rate-limit key (the rightmost X-Forwarded-For entry) is not stable behind Cloudflare and
Render. This module logs the shape of the IP headers on each /v1/ call so the fix can be chosen
from evidence. It is off unless RATE_LIMIT_DIAGNOSTICS=1 and is removed once the fix lands.

Privacy rule: no address, and no hash of one, is ever written. Each line holds counts, header
names, positions and classes only. Addresses are compared in memory and dropped. The one piece of
state is the set of distinct rate-limit keys this process has seen, capped and never logged; it
holds the same values the rate limiter already keeps in memory as counter keys.

Classes: `cloudflare` (Cloudflare's published ranges), `private` (private or loopback),
`testnet` (192.0.2.0/24, reserved for documentation, used to mark forged headers in experiments),
`other` (any other valid address) and `invalid` (not an address).
"""

import ipaddress
import logging
import os
import re

from fastapi import Request

from govbr_classifier.api.client_ip import CLOUDFLARE_NETWORKS

# uvicorn configures this logger at INFO, so the lines reach the platform logs.
logger = logging.getLogger("uvicorn.error")

TEST_NET = ipaddress.ip_network("192.0.2.0/24")
IP_HEADERS = ("x-forwarded-for", "forwarded", "cf-connecting-ip", "true-client-ip", "x-real-ip")

_IPV4 = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")
_MAX_KEYS = 1000
_seen_keys: set[str] = set()
_previous_key: str | None = None


def reset() -> None:
    """Forget the keys seen so far. Used by tests."""
    global _previous_key
    _seen_keys.clear()
    _previous_key = None


def classify_address(value: str) -> str:
    """Return the class of one address, never the address itself."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return "invalid"
    if address in TEST_NET:
        return "testnet"
    if any(address in network for network in CLOUDFLARE_NETWORKS):
        return "cloudflare"
    if address.is_private or address.is_loopback:
        return "private"
    return "other"


def _position_in(value: str | None, entries: list[str]) -> str:
    """Where `value` appears in `entries`, counted from the right (-1 is the rightmost)."""
    if value is None:
        return "absent"
    positions = [str(i - len(entries)) for i, entry in enumerate(entries) if entry == value.strip()]
    return ",".join(positions) or "not_in_xff"


def describe(request: Request, key: str) -> str:
    """Build one log line about the IP headers of this request, holding no address."""
    global _previous_key
    headers = request.headers
    xff = [
        entry.strip() for entry in headers.get("x-forwarded-for", "").split(",") if entry.strip()
    ]

    changed = "first" if _previous_key is None else str(key != _previous_key).lower()
    _previous_key = key
    if len(_seen_keys) < _MAX_KEYS:
        _seen_keys.add(key)

    present = [name for name in IP_HEADERS if name in headers]
    testnet_in = [
        name
        for name in present
        if any(classify_address(m) == "testnet" for m in _IPV4.findall(headers[name]))
    ]
    client_host = request.client.host if request.client else ""

    fields = {
        "pid": str(os.getpid()),
        "instance": os.environ.get("RENDER_INSTANCE_ID", "none"),
        "web_concurrency": os.environ.get("WEB_CONCURRENCY", "unset"),
        "xff_entries": str(len(xff)),
        "xff_classes": ",".join(classify_address(entry) for entry in xff) or "none",
        "key_class": classify_address(key),
        "key_changed": changed,
        "distinct_keys_seen": str(len(_seen_keys)),
        "client_host_class": classify_address(client_host),
        "present": ",".join(present) or "none",
        "cf_connecting_ip_at": _position_in(headers.get("cf-connecting-ip"), xff),
        "true_client_ip_at": _position_in(headers.get("true-client-ip"), xff),
        "testnet_in": ",".join(testnet_in) or "none",
    }
    return "rate_limit_diag " + " ".join(f"{name}={value}" for name, value in fields.items())


def log_request_shape(request: Request, key: str) -> None:
    """Write the shape line for this request."""
    logger.info(describe(request, key))

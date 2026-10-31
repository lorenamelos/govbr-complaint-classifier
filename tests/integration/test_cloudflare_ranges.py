"""The Cloudflare ranges copied into client_ip.py must match the ones Cloudflare publishes.

A range Cloudflare adds that we have not copied makes the client-IP walk stop at an edge; the
cross-check with CF-Connecting-IP then sends every such request to the shared `unresolved`
counter, which becomes 429s for everyone behind that edge. This test fails first, in a weekly
workflow (.github/workflows/cloudflare-ranges.yml), so the list is updated before that happens.
"""

import ipaddress
import urllib.request

import pytest

from govbr_classifier.api.client_ip import CLOUDFLARE_NETWORKS

SOURCES = ("https://www.cloudflare.com/ips-v4", "https://www.cloudflare.com/ips-v6")
USER_AGENT = "govbr-complaint-classifier/cloudflare-range-check"


def _published() -> set[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = set()
    for url in SOURCES:
        # Cloudflare answers 403 to urllib's default User-Agent.
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
        networks |= {
            ipaddress.ip_network(line.strip()) for line in text.splitlines() if line.strip()
        }
    return networks


@pytest.mark.integration
def test_copied_cloudflare_ranges_match_the_published_list() -> None:
    published = _published()
    copied = set(CLOUDFLARE_NETWORKS)
    assert published, "Cloudflare returned an empty list; refusing to compare"
    missing = sorted(map(str, published - copied))
    extra = sorted(map(str, copied - published))
    assert not missing, f"published by Cloudflare, missing from client_ip.py: {missing}"
    assert not extra, f"in client_ip.py, no longer published by Cloudflare: {extra}"

"""Check from outside that one client sees one rate-limit counter.

Sends N calls to POST /v1/classify in a row and reads X-RateLimit-Remaining from each response.
With one counter, `remaining` falls by exactly one per call and, once a 429 appears, no 200 follows
it. Any repeated value or any 200 after a 429 means the client is being counted in more than one
place (several processes, or a key that changes between calls). Standard library only, so it runs
anywhere:

    python scripts/check_single_counter.py http://localhost:7860
    python scripts/check_single_counter.py \
        https://govbr-complaint-classifier.onrender.com --calls 40

Run it at the start of a rate-limit window with no other traffic from the same client, or the
first calls will already be partly spent. Exit code 0 means one counter; 1 means more than one.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

BODY = json.dumps({"items": [{"text": "o app trava e nao abre"}]}).encode()


def call(base_url: str) -> tuple[int, int | None]:
    """POST one valid item and return the status code with X-RateLimit-Remaining, if present."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/classify",
        data=BODY,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status, headers = response.status, response.headers
    except urllib.error.HTTPError as error:
        status, headers = error.code, error.headers
    remaining = headers.get("X-RateLimit-Remaining")
    return status, int(remaining) if remaining is not None else None


def find_problems(results: list[tuple[int, int | None]]) -> list[str]:
    """Return why these (status, remaining) pairs could not come from one counter; empty if fine."""
    problems = []
    remainings = [r for status, r in results if status == 200 and r is not None]
    repeated = sorted({r for r in remainings if remainings.count(r) > 1})
    if repeated:
        problems.append(f"remaining values repeated: {repeated}")
    first_429 = next((i for i, (status, _) in enumerate(results) if status == 429), None)
    if first_429 is not None and any(status == 200 for status, _ in results[first_429:]):
        problems.append(f"a 200 came after the first 429 (call {first_429 + 1})")
    if first_429 is None:
        problems.append("no 429 at all: the limit was never reached")
    return problems


def main() -> int:
    """Run the calls and report whether they were counted against a single counter."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url")
    parser.add_argument("--calls", type=int, default=31)
    args = parser.parse_args()

    results = [call(args.base_url) for _ in range(args.calls)]
    print(" ".join(f"{status}:{remaining}" for status, remaining in results))

    problems = find_problems(results)
    if problems:
        print("MORE THAN ONE COUNTER: " + "; ".join(problems))
        return 1
    print("OK: one counter")
    return 0


if __name__ == "__main__":
    sys.exit(main())

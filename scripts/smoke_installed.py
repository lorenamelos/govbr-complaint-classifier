"""Smoke test of the package as the container installs it: non-editable, outside the repository.

An editable install resolves files from the source tree, so it hides paths that break once the
package lives in site-packages. Run this with the interpreter of a fresh venv where the package
was installed with `pip install .`, from a directory that is not the repository root:

    python -I scripts/smoke_installed.py

Exit code is non-zero on any failure, with the reason printed.
"""

import sys

from fastapi.testclient import TestClient

import govbr_classifier
from govbr_classifier.api.main import app


def main() -> int:
    """Classify one text against the installed package and check the response shape."""
    print(f"package location: {govbr_classifier.__file__}")
    if "site-packages" not in govbr_classifier.__file__:
        print("FAIL: the package was imported from the source tree, not from an installed copy")
        return 1

    response = TestClient(app).post("/v1/classify", json={"items": [{"text": "o app trava"}]})
    if response.status_code != 200:
        print(f"FAIL: /v1/classify returned {response.status_code}: {response.text}")
        return 1

    body = response.json()
    attributes = body["results"][0]["attributes"]
    expected = {"tema", "bloqueio", "tipo", "acionabilidade"}
    if set(attributes) != expected:
        print(f"FAIL: attributes {sorted(attributes)} differ from {sorted(expected)}")
        return 1

    print(f"OK: model_version={body['model_version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

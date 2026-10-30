"""Format of `model_version`, the only response field that changes when the model improves (ADR-21).

Format: `YYYY.MM.N-description`, for example `2026.10.1-tema-keyword-baseline`.

- `YYYY.MM` is the month the model was frozen (trained or written), not the month it was deployed.
  Redeploying the same model keeps its version.
- `N` counts models frozen in that month, starting at 1, with no leading zeros.
- `description` is lowercase kebab-case ASCII: what the model is, not how good it is.

The version is checked at import time, so a malformed one stops the process instead of reaching
the prediction log, where drift and canary results are grouped by it.
"""

import re

MODEL_VERSION_PATTERN = re.compile(
    r"^(?P<year>20\d{2})\.(?P<month>0[1-9]|1[0-2])\.(?P<n>[1-9]\d*)"
    r"-(?P<description>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)


def check_model_version(version: str) -> str:
    """Return the version unchanged, or raise ValueError if it breaks the format."""
    if not MODEL_VERSION_PATTERN.fullmatch(version):
        raise ValueError(
            f"model_version {version!r} does not match YYYY.MM.N-description "
            "(for example 2026.10.1-tema-keyword-baseline)"
        )
    return version

"""Load and validate the closed label lists in taxonomy.yaml, shipped inside this package.

The taxonomy is the single source of truth for labels. The API, the LLM labeling prompt and the
evaluation all read it from here, so a label cannot exist in one place and not in another.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

# Resolved next to this module, not from the repository root, so an installed (non-editable)
# package such as the serving container finds it too.
TAXONOMY_PATH = Path(__file__).resolve().with_name("taxonomy.yaml")


@dataclass(frozen=True)
class Attribute:
    """One classification attribute with its closed list of labels."""

    name: str
    cardinality: Literal["single", "multi"]
    labels: tuple[str, ...]
    exclusive: tuple[str, ...] = ()


@dataclass(frozen=True)
class Taxonomy:
    """All attributes, keyed by name, plus the file version."""

    version: int
    attributes: dict[str, Attribute]


def _parse(raw: dict) -> Taxonomy:
    """Build a Taxonomy from parsed YAML, failing loudly on any inconsistency."""
    attributes: dict[str, Attribute] = {}
    for name, spec in raw["attributes"].items():
        labels = tuple(spec["labels"].keys())
        exclusive = tuple(spec.get("exclusive", []))
        unknown = set(exclusive) - set(labels)
        if unknown:
            raise ValueError(f"{name}: exclusive labels not in label list: {sorted(unknown)}")
        if spec["cardinality"] not in ("single", "multi"):
            raise ValueError(f"{name}: cardinality must be 'single' or 'multi'")
        attributes[name] = Attribute(name, spec["cardinality"], labels, exclusive)
    return Taxonomy(version=int(raw["version"]), attributes=attributes)


@lru_cache
def load_taxonomy(path: Path = TAXONOMY_PATH) -> Taxonomy:
    """Read and validate the taxonomy file once per process."""
    with path.open(encoding="utf-8") as f:
        return _parse(yaml.safe_load(f))

"""Annotation-only fields, read from the `annotation` section of taxonomy.yaml.

The label lists of the four attributes come from `taxonomy.load_taxonomy()`; the auxiliary fields of
the annotation spreadsheet (ood_manual, duvida) come from here. Both read the same file, so no value
is typed by hand anywhere else.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from govbr_classifier.taxonomy import TAXONOMY_PATH


@dataclass(frozen=True)
class AnnotationFields:
    """Allowed values of the annotation-only columns."""

    ood_manual: tuple[str, ...]
    ood_none_value: str
    duvida: tuple[str, ...]


@lru_cache
def load_annotation_fields(path: Path = TAXONOMY_PATH) -> AnnotationFields:
    """Read the `annotation` section, failing loudly if it is missing or inconsistent."""
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    section = raw.get("annotation")
    if not section:
        raise ValueError(f"{path.name}: no `annotation` section")
    ood = tuple(section["ood_manual"]["values"])
    none_value = section["ood_manual"]["none_value"]
    if none_value not in ood:
        raise ValueError(f"{path.name}: ood_manual none_value {none_value!r} is not a value")
    return AnnotationFields(
        ood_manual=ood, ood_none_value=none_value, duvida=tuple(section["duvida"]["values"])
    )

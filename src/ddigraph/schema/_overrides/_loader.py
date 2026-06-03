"""Read ``schema_overrides.toml`` and produce typed override views.

The override file lives next to this module and is the human-edited
bridge between the XSD-derived metadata under
``ddigraph.schema._generated`` and the runtime
``NodeDefinition`` / ``RelationshipDefinition`` tuples exported from
``ddigraph.schema.definitions``.

Today only the DDI-CDI section is consumed by runtime code; lifecycle
and codebook are added in follow-up commits.
"""

from __future__ import annotations

import re
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from ddigraph.schema._generated.cdi import CDI_GENERATED_ASSOCIATIONS
from ddigraph.schema._generated.lifecycle import FRAGMENT_GENERATED_REFERENCES
from ddigraph.schema.definitions._dataclasses import NodeDefinition

_OVERRIDES_FILE = Path(__file__).resolve().parent / "schema_overrides.toml"
_CAMEL_SPLIT = re.compile(r"(?<!^)([A-Z])")


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    """Load and cache the raw TOML payload."""
    with _OVERRIDES_FILE.open("rb") as fh:
        return tomllib.load(fh)


def _default_rel_type(verb: str) -> str:
    """Convert a CDI verb to its default UPPER_SNAKE_CASE relationship type.

    Examples:
        >>> _default_rel_type("has")
        'HAS'
        >>> _default_rel_type("isStructuredBy")
        'IS_STRUCTURED_BY'
    """
    return _CAMEL_SPLIT.sub(r"_\1", verb).upper()


def _build_node(entry: dict[str, Any], defaults: dict[str, Any]) -> NodeDefinition:
    """Materialise one ``NodeDefinition`` from a TOML entry + flavor defaults.

    Any field absent from the entry inherits from ``defaults`` (the
    flavor's ``[<flavor>.defaults]`` block). Lists in TOML become
    Python lists; ``NodeDefinition`` expects tuples, so we coerce.
    """
    label = entry["label"]
    id_field = entry.get("id_field", defaults["id_field"])
    properties = tuple(entry.get("properties", defaults["properties"]))
    indexes = tuple(entry.get("indexes", defaults["indexes"]))
    is_fragment = bool(entry.get("is_fragment", False))
    composite_id_fields = tuple(entry.get("composite_id_fields", ()))
    return NodeDefinition(
        label=label,
        id_field=id_field,
        properties=properties,
        indexes=indexes,
        is_fragment=is_fragment,
        composite_id_fields=composite_id_fields,
    )


def cdi_nodes() -> tuple[NodeDefinition, ...]:
    """Return the curated DDI-CDI ``NodeDefinition`` tuple.

    Reads ``[ddi_cdi.defaults]`` and ``[[ddi_cdi.node]]`` entries from
    ``schema_overrides.toml``. Order preserved from the TOML file (it
    matches the ``CDI_NODES`` tuple ordering callers may rely on).

    Raises:
        KeyError: If the override file is missing the ``ddi_cdi``
            section or any required field.
    """
    section = _raw()["ddi_cdi"]
    defaults = section["defaults"]
    entries = section.get("node", [])
    return tuple(_build_node(entry, defaults) for entry in entries)


def cdi_relationships() -> dict[str, tuple[str, str, str]]:
    """Return the full DDI-CDI relationship-tag dispatch table.

    Derived from ``CDI_GENERATED_ASSOCIATIONS`` (every XSD-declared
    ``<Source>_<verb>_<Target>`` element) with the rel_type computed
    via ``_default_rel_type(verb)``. Where that default would be
    ambiguous (e.g. ``has`` collides across many associations), the
    ``[ddi_cdi.relationship_overrides]`` table supplies a curated name.

    Returns:
        Dict from association tag to ``(rel_type, source_label,
        target_label)``. Source and target labels are prefixed with
        ``CDI`` to match the runtime node labels.
    """
    overrides: dict[str, str] = _raw()["ddi_cdi"].get("relationship_overrides", {})
    table: dict[str, tuple[str, str, str]] = {}
    for assoc in CDI_GENERATED_ASSOCIATIONS:
        rel_type = overrides.get(assoc.tag, _default_rel_type(assoc.verb))
        source_label = f"CDI{assoc.source}"
        target_label = f"CDI{assoc.target}"
        table[assoc.tag] = (rel_type, source_label, target_label)
    return table


def _default_fragment_rel_type(ref_tag: str) -> str:
    """Default rel_type for a DDI-L ``*Reference`` element name.

    Strips the trailing ``"Reference"`` and uppercases the remainder, mirroring
    the historical fallback in ``DDISchema.get_fragment_relationship_type``.
    Empty stems map to ``"REFERENCES"`` so a bare ``<Reference/>`` still
    produces a meaningful name.
    """
    rel = ref_tag.removesuffix("Reference")
    return rel.upper() if rel else "REFERENCES"


def fragment_relationships() -> dict[str, str]:
    """Return the full DDI-L ``*Reference`` -> rel_type table.

    Every XSD-declared ``*Reference`` element produces a runtime
    rel_type. Curated names in ``[ddi_l.relationship_overrides]`` win;
    everything else falls back to ``_default_fragment_rel_type``. The
    returned dict is the single source of truth for
    ``DDISchema.FRAGMENT_RELATIONSHIP_TYPES``.

    Returns:
        Map from ``*Reference`` tag name to relationship-type string.
    """
    overrides: dict[str, str] = _raw()["ddi_l"].get("relationship_overrides", {})
    table: dict[str, str] = {}
    for ref in FRAGMENT_GENERATED_REFERENCES:
        table[ref.tag] = overrides.get(ref.tag, _default_fragment_rel_type(ref.tag))
    # ``ExternalURLReference`` is a synthetic runtime-only edge that has no
    # XSD element; keep it in the table so legacy callers that look it up
    # continue to work. The override always wins.
    for tag, rel_type in overrides.items():
        if tag not in table:
            table[tag] = rel_type
    return table


__all__ = ["cdi_nodes", "cdi_relationships", "fragment_relationships"]

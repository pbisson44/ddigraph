"""Round-trip tests for ``ddigraph.schema._overrides``.

The override file is the single source of truth for the curated CDI
node table and the curated CDI relationship-type rel_type names.
These tests pin three invariants:

1. The loader produces a ``NodeDefinition`` tuple that is *byte-equal*
   to ``tests/fixtures/cdi_nodes_snapshot.json``, captured right before
   the Step B wire-in.
2. The runtime ``CDI_NODES`` exported from
   ``ddigraph.schema.definitions`` matches the loader output exactly.
3. Every entry from the pre-Step-C
   ``tests/fixtures/cdi_relationships_snapshot.json`` (the 26
   historically-curated rel_type names) survives the wire-in
   identically -- i.e. the override file in
   ``[ddi_cdi.relationship_overrides]`` reproduces every legacy name.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ddigraph.schema._overrides._loader import cdi_nodes, cdi_relationships
from ddigraph.schema.definitions import CDI_NODES

_NODES_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cdi_nodes_snapshot.json"
_RELS_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cdi_relationships_snapshot.json"


def _load_nodes_fixture() -> list[dict[str, object]]:
    """Return the canonical CDI snapshot as a list of dicts."""
    with _NODES_FIXTURE.open() as fh:
        loaded: list[dict[str, object]] = json.load(fh)
    return loaded


def _load_rels_fixture() -> dict[str, list[str]]:
    """Return the canonical CDI relationship snapshot."""
    with _RELS_FIXTURE.open() as fh:
        loaded: dict[str, list[str]] = json.load(fh)
    return loaded


def _serialise(nodes: tuple[object, ...]) -> str:
    """Stable JSON serialisation of a NodeDefinition tuple."""
    return json.dumps([asdict(n) for n in nodes], sort_keys=True, indent=2)  # type: ignore[call-overload]


def test_loader_round_trips_against_fixture() -> None:
    """Loader output equals the committed JSON snapshot, field for field."""
    loaded = cdi_nodes()
    expected_serialised = json.dumps(_load_nodes_fixture(), sort_keys=True, indent=2)
    actual_serialised = _serialise(loaded)
    assert actual_serialised == expected_serialised, (
        "schema_overrides.toml drifted from cdi_nodes_snapshot.json. "
        "If the change is intentional, regenerate the fixture; otherwise "
        "fix the TOML."
    )


def test_definitions_cdi_nodes_uses_the_loader() -> None:
    """``ddigraph.schema.definitions.CDI_NODES`` is exactly the loader output."""
    assert CDI_NODES == cdi_nodes()


def test_legacy_cdi_relationships_are_preserved() -> None:
    """Every pre-Step-C rel_type name survives the wire-in unchanged.

    The 26 historically curated entries in ``_CDI_RELATIONSHIP_MAP``
    are captured in ``tests/fixtures/cdi_relationships_snapshot.json``.
    Their rel_type / source_label / target_label triples must match
    the new derived table byte-for-byte; otherwise a Cypher query
    written against the previous schema would break.
    """
    fixture = _load_rels_fixture()
    derived = cdi_relationships()
    mismatches: list[str] = []
    for tag, expected_list in fixture.items():
        expected = tuple(expected_list)
        actual = derived.get(tag)
        if actual != expected:
            mismatches.append(f"  {tag}: expected={expected}, actual={actual}")
    assert not mismatches, "legacy CDI rel_type names drifted:\n" + "\n".join(mismatches)


def test_cdi_relationships_covers_every_generated_association() -> None:
    """The derived table emits a relationship for every XSD association."""
    from ddigraph.schema._generated.cdi import CDI_GENERATED_ASSOCIATIONS

    derived = cdi_relationships()
    assert set(derived) == {a.tag for a in CDI_GENERATED_ASSOCIATIONS}

"""Snapshot tests for the ``definitions`` package refactor.

Step B of the simplification plan converted the 3,218-line
``ddigraph.schema.definitions`` module into a package backed by
``_dataclasses``, ``codebook``, ``lifecycle`` and ``cdi`` sub-modules.
These tests pin the public surface so future overrides-driven changes
(Step B follow-up + Step C) cannot accidentally reshape it.
"""

from __future__ import annotations

from dataclasses import asdict

from ddigraph.schema.definitions import (
    CDI_NODES,
    CODEBOOK_NODES,
    FRAGMENT_NODES,
    FRAGMENT_RELATIONSHIP_TYPES,
    DDISchema,
    NodeDefinition,
    RelationshipDefinition,
)


def test_public_surface_is_preserved() -> None:
    """Every name the old monolith exposed is still importable.

    A regression here means downstream code (loaders, adapters, demos)
    that imports from ``ddigraph.schema.definitions`` will break.
    """
    assert NodeDefinition is not None
    assert RelationshipDefinition is not None
    assert DDISchema is not None

    # The four data tables are accessible both as DDISchema class vars
    # and as module-level convenience names.
    assert CODEBOOK_NODES is DDISchema.CODEBOOK_NODES
    assert FRAGMENT_NODES is DDISchema.FRAGMENT_NODES
    assert FRAGMENT_RELATIONSHIP_TYPES is DDISchema.FRAGMENT_RELATIONSHIP_TYPES
    assert CDI_NODES is DDISchema.CDI_NODES


def test_node_counts_are_stable() -> None:
    """Snapshot the counts so a stray edit to a flavor file is noticed.

    These numbers come straight from the literals that lived in the
    pre-refactor ``definitions.py``. A change here is a deliberate
    schema change and the constant should be updated alongside.
    """
    assert len(CODEBOOK_NODES) == 47, len(CODEBOOK_NODES)
    assert len(FRAGMENT_NODES) == 191, len(FRAGMENT_NODES)
    # Step D wired this dict through fragment_relationships(), making it
    # a superset of every XSD-declared *Reference element (282) plus the
    # synthetic ExternalURLReference runtime edge.
    assert len(FRAGMENT_RELATIONSHIP_TYPES) == 283, len(FRAGMENT_RELATIONSHIP_TYPES)
    assert len(CDI_NODES) == 32, len(CDI_NODES)


def test_get_all_nodes_aggregates_every_flavor() -> None:
    """``DDISchema.get_all_nodes`` returns codebook + fragment + cdi by default."""
    nodes = DDISchema.get_all_nodes()
    expected = len(CODEBOOK_NODES) + len(FRAGMENT_NODES) + len(CDI_NODES)
    assert len(nodes) == expected

    codebook_only = DDISchema.get_all_nodes(include_fragments=False, include_cdi=False)
    assert len(codebook_only) == len(CODEBOOK_NODES)


def test_dataclasses_remain_frozen_and_typed() -> None:
    """``NodeDefinition`` instances stay frozen so they can be hashed / cached."""
    node = CODEBOOK_NODES[0]
    assert isinstance(node, NodeDefinition)

    payload = asdict(node)
    assert {"label", "id_field", "properties", "indexes"} <= set(payload)


def test_constraint_queries_round_trip_through_helpers() -> None:
    """``generate_all_schema_queries`` covers every flavor's nodes."""
    queries = DDISchema.generate_all_schema_queries()
    assert queries, "expected at least one constraint/index query"
    assert any("Dataset" in q for q in queries), "Codebook flavor missing from query set"
    assert any("Instrument" in q for q in queries), "Lifecycle flavor missing from query set"
    assert any("CDI" in q for q in queries), "CDI flavor missing from query set"


def test_fragment_relationship_type_lookup_handles_known_and_unknown() -> None:
    """Known reference tags resolve to mapped types; unknown tags fall back."""
    # Curated mapping: every known *Reference name has a hand-chosen
    # rel type; the dict is the source of truth.
    assert DDISchema.get_fragment_relationship_type("ConceptReference") == "USES_CONCEPT"
    # Unknown reference tags strip the "Reference" suffix and uppercase.
    assert DDISchema.get_fragment_relationship_type("MadeUpReference") == "MADEUP"
    # The empty-suffix fallback returns a defensible default rather than "".
    assert DDISchema.get_fragment_relationship_type("Reference") == "REFERENCES"

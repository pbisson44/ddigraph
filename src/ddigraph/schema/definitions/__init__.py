"""Unified DDI graph schema definitions.

This package is the public home of ``DDISchema``, ``NodeDefinition``,
and ``RelationshipDefinition``. The literal node / relationship data
lives in ``codebook``, ``lifecycle`` and ``cdi`` sub-modules; a
follow-up commit will route those through ``_generated`` + override
files.

External imports from ``ddigraph.schema.definitions`` continue to
work unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from ddigraph.schema.definitions._dataclasses import (
    NodeDefinition,
    RelationshipDefinition,
)
from ddigraph.schema.definitions.cdi import CDI_NODES as _CDI_NODES
from ddigraph.schema.definitions.codebook import CODEBOOK_NODES as _CODEBOOK_NODES
from ddigraph.schema.definitions.lifecycle import (
    FRAGMENT_NODES as _FRAGMENT_NODES,
    FRAGMENT_RELATIONSHIP_TYPES as _FRAGMENT_RELATIONSHIP_TYPES,
)


@dataclass
class DDISchema:
    """Single source of truth for DDI graph schema."""

    CODEBOOK_NODES: ClassVar[tuple[NodeDefinition, ...]] = _CODEBOOK_NODES
    FRAGMENT_NODES: ClassVar[tuple[NodeDefinition, ...]] = _FRAGMENT_NODES
    FRAGMENT_RELATIONSHIP_TYPES: ClassVar[dict[str, str]] = _FRAGMENT_RELATIONSHIP_TYPES
    CDI_NODES: ClassVar[tuple[NodeDefinition, ...]] = _CDI_NODES

    @classmethod
    def get_all_nodes(
        cls,
        include_fragments: bool = True,
        include_cdi: bool = True,
    ) -> tuple[NodeDefinition, ...]:
        """Get all node definitions.

        Args:
            include_fragments: If True, include DDI-L fragment node types.
            include_cdi: If True, include DDI-CDI 1.0 node types.

        Returns:
            Tuple of all node definitions.
        """
        nodes = cls.CODEBOOK_NODES
        if include_fragments:
            nodes = nodes + cls.FRAGMENT_NODES
        if include_cdi:
            nodes = nodes + cls.CDI_NODES
        return nodes

    @classmethod
    def get_fragment_relationship_type(cls, ref_tag: str) -> str:
        """Convert a reference tag name to a relationship type.

        Args:
            ref_tag: XML tag name of the reference element.

        Returns:
            Neo4j relationship type string.
        """
        if ref_tag in cls.FRAGMENT_RELATIONSHIP_TYPES:
            return cls.FRAGMENT_RELATIONSHIP_TYPES[ref_tag]

        # Generic fallback: strip "Reference" suffix and uppercase
        rel = ref_tag.replace("Reference", "")
        return rel.upper() if rel else "REFERENCES"

    @classmethod
    def generate_constraint_queries(
        cls,
        include_fragments: bool = True,
        include_cdi: bool = True,
    ) -> list[str]:
        """Generate Cypher queries to create uniqueness constraints.

        Args:
            include_fragments: If True, include DDI-L fragment constraints.
            include_cdi: If True, include DDI-CDI 1.0 constraints.

        Returns:
            List of CREATE CONSTRAINT Cypher statements.
        """
        queries = []
        for node in cls.get_all_nodes(include_fragments, include_cdi):
            if node.composite_id_fields:
                composite = ", ".join(f"n.{field}" for field in node.composite_id_fields)
                queries.append(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node.label}) "
                    f"REQUIRE ({composite}) IS UNIQUE"
                )
            else:
                queries.append(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node.label}) "
                    f"REQUIRE n.{node.id_field} IS UNIQUE"
                )
        return queries

    @classmethod
    def generate_index_queries(
        cls,
        include_fragments: bool = True,
        include_cdi: bool = True,
    ) -> list[str]:
        """Generate Cypher queries to create secondary indexes.

        Args:
            include_fragments: If True, include DDI-L fragment indexes.
            include_cdi: If True, include DDI-CDI 1.0 indexes.

        Returns:
            List of CREATE INDEX Cypher statements.
        """
        queries = []
        for node in cls.get_all_nodes(include_fragments, include_cdi):
            for index_field in node.indexes:
                queries.append(
                    f"CREATE INDEX IF NOT EXISTS FOR (n:{node.label}) ON (n.{index_field})"
                )
        return queries

    @classmethod
    def generate_all_schema_queries(
        cls,
        include_fragments: bool = True,
        include_cdi: bool = True,
    ) -> list[str]:
        """Generate all schema bootstrap queries.

        Args:
            include_fragments: If True, include DDI-L fragment schema.
            include_cdi: If True, include DDI-CDI 1.0 schema.

        Returns:
            List of all constraint and index Cypher statements.
        """
        return cls.generate_constraint_queries(
            include_fragments, include_cdi
        ) + cls.generate_index_queries(include_fragments, include_cdi)


# Convenience exports (preserve the public surface of the former monolith).
CODEBOOK_NODES = DDISchema.CODEBOOK_NODES
FRAGMENT_NODES = DDISchema.FRAGMENT_NODES
FRAGMENT_RELATIONSHIP_TYPES = DDISchema.FRAGMENT_RELATIONSHIP_TYPES
CDI_NODES = DDISchema.CDI_NODES


__all__ = [
    "CDI_NODES",
    "CODEBOOK_NODES",
    "FRAGMENT_NODES",
    "FRAGMENT_RELATIONSHIP_TYPES",
    "DDISchema",
    "NodeDefinition",
    "RelationshipDefinition",
]

"""Dataclasses backing ``DDISchema``.

Public re-export from ``ddigraph.schema.definitions``; kept in a
private module so the literal data files (codebook, lifecycle, cdi)
can import these types without circular references.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeDefinition:
    """Definition of a graph node type.

    Attributes:
        label: Neo4j node label (e.g., "Variable", "Question").
        id_field: Primary identifier field name for MERGE operations.
        properties: Tuple of property field names to persist.
        indexes: Additional fields to create secondary indexes on.
        is_fragment: True if this is a DDI-L FragmentInstance node type.
        composite_id_fields: When non-empty, overrides ``id_field`` and creates
            a composite uniqueness constraint across the listed properties.
    """

    label: str
    id_field: str
    properties: tuple[str, ...]
    indexes: tuple[str, ...] = ()
    is_fragment: bool = False
    composite_id_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipDefinition:
    """Definition of a graph relationship type.

    Attributes:
        rel_type: Neo4j relationship type (e.g., "IN_DATASET", "USES_CONCEPT").
        start_label: Label of the start node.
        start_field: Identity field on the start node.
        end_label: Label of the end node.
        end_field: Identity field on the end node.
        start_attr: Attribute name on the graph object containing start records.
        end_attr: Attribute name on the graph object containing end records.
        lookup_field: Field on start record to look up end node (if different from end_field).
    """

    rel_type: str
    start_label: str
    start_field: str
    end_label: str
    end_field: str
    start_attr: str
    end_attr: str
    lookup_field: str | None = None


__all__ = ["NodeDefinition", "RelationshipDefinition"]

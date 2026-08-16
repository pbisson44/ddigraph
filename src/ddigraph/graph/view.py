"""A backend-neutral node/relationship view over every DDI flavor.

The three DDI parsers each produce their own intermediate representation:
DDI-Codebook yields :class:`~ddigraph.ingest.loader.DDIBatch`, DDI-Lifecycle
yields :class:`~ddigraph.ingest.fragment_loader.FragmentBatch`, and DDI-CDI
yields :class:`~ddigraph.ingest.cdi_loader.CDIBatch`. Only the codebook tier
had a backend-neutral projection (``DDIIngestGraph.nodes()`` /
``.relationships()``), so anything wanting to consume "the graph" regardless
of input format had to special-case all three.

:func:`iter_graph` closes that gap. It detects the flavor, drives the right
parser, and yields :class:`GraphChunk` values built from the existing
:class:`~ddigraph.schema.ddi_graph.Node` and
:class:`~ddigraph.schema.ddi_graph.Relationship` dataclasses. Exporters,
previewers and validators can then target one shape.

Chunks stream: the parsers are ``iterparse``-based and memory-bounded, and
this layer adds no buffering beyond a single chunk. Two consequences are
worth knowing:

* Node identity is *upsert* semantics, not "seen once". The codebook
  projection re-emits the ``Dataset`` node in every chunk, exactly as
  ``DDIIngestGraph.nodes()`` always has, and a consumer is expected to merge
  on :attr:`~ddigraph.schema.ddi_graph.Node.identity`.
* The lifecycle parser is two-phase: it yields node-only chunks first and
  relationship-only chunks afterwards. A consumer that needs both sides of
  an edge must therefore accumulate nodes as they stream past rather than
  assume a chunk is self-contained.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ddigraph.ingest.cdi_loader import _CDI_TAG_MAP, parse_cdi_batches
from ddigraph.ingest.fragment_loader import DDIFragmentParser, detect_ddi_format
from ddigraph.ingest.loader import parse_ddi_batches
from ddigraph.logging import get_logger
from ddigraph.paths import default_dataset_id, validate_readable_xml_path
from ddigraph.schema.ddi_graph import DDIIngestGraph, Node, Relationship

if TYPE_CHECKING:
    from ddigraph.ingest.cdi_loader import CDIBatch, CDIRecord
    from ddigraph.ingest.fragment_loader import FragmentBatch

logger = get_logger(__name__)

# Collection attribute on ``CDIBatch`` -> graph label. The labels match
# ``DDISchema.CDI_NODES`` exactly; ``test_graph_view`` asserts that this map
# stays exhaustive so a new curated CDI node type cannot be added without
# also becoming visible here.
_CDI_COLLECTION_LABELS: dict[str, str] = {
    "concepts": "CDIConcept",
    "concept_systems": "CDIConceptSystem",
    "conceptual_variables": "CDIConceptualVariable",
    "represented_variables": "CDIRepresentedVariable",
    "instance_variables": "CDIInstanceVariable",
    "unit_types": "CDIUnitType",
    "universes": "CDIUniverse",
    "populations": "CDIPopulation",
    "agents": "CDIAgent",
    "categories": "CDICategory",
    "category_sets": "CDICategorySet",
    "codes": "CDICode",
    "code_lists": "CDICodeList",
    "statistical_classifications": "CDIStatisticalClassification",
    "classification_items": "CDIClassificationItem",
    "data_structures": "CDIDataStructure",
    "data_structure_components": "CDIDataStructureComponent",
    "datasets": "CDIDataSet",
    "data_stores": "CDIDataStore",
    "logical_records": "CDILogicalRecord",
    "physical_datasets": "CDIPhysicalDataSet",
    "activities": "CDIActivity",
    "processing_agents": "CDIProcessingAgent",
    "value_domains": "CDIValueDomain",
    "correspondence_tables": "CDICorrespondenceTable",
    "variable_relationships": "CDIVariableRelationship",
    "concept_maps": "CDIConceptMap",
    "concept_system_correspondences": "CDIConceptSystemCorrespondence",
    "physical_record_segments": "CDIPhysicalRecordSegment",
    "classification_families": "CDIClassificationFamily",
    "classification_indexes": "CDIClassificationIndex",
    "classification_series": "CDIClassificationSeries",
}

# Entities parsed through the CDI generic path carry no curated
# ``NodeDefinition``. They keep their XSD tag on ``entity_type``, mirroring
# how the codebook tier exposes ``DDIGenericIdentifiable`` with
# ``element_tag``.
_CDI_GENERIC_LABEL = "CDIGenericEntity"

# Identity field per flavor, matching the ``NodeDefinition.id_field`` the
# Neo4j adapter merges on.
_CDI_ID_FIELD = "cdi_id"
_FRAGMENT_ID_FIELD = "fragment_id"


@dataclass(slots=True)
class GraphChunk:
    """A streamed slice of a DDI graph, independent of any backend.

    Attributes:
        nodes: Nodes parsed in this slice. May be empty when the underlying
            parser is emitting a relationship-only phase.
        relationships: Relationships parsed in this slice. May be empty when
            the parser is emitting a node-only phase.
    """

    nodes: list[Node] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Return True when the chunk carries any node or relationship."""
        return bool(self.nodes or self.relationships)


def iter_graph(
    path: str | Path,
    *,
    flavor: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    chunk_size: int = 200,
    recover: bool = True,
) -> Iterator[GraphChunk]:
    """Stream a DDI file as backend-neutral graph chunks.

    Args:
        path: Path to a DDI Codebook, DDI-L FragmentInstance, or DDI-CDI file.
        flavor: Force a flavor instead of sniffing the file. One of
            ``"codebook"``, ``"lifecycle"``, ``"cdi"``.
        dataset_id: Dataset identifier for the codebook flavor. Defaults to
            the file stem, matching :func:`ddigraph.load`. Ignored by the
            lifecycle and CDI flavors, which carry their own identity.
        dataset_name: Human-readable dataset name for the codebook flavor.
        chunk_size: Records to accumulate before emitting a chunk.
        recover: Ask the XML parser to recover from malformed markup rather
            than raising.

    Yields:
        GraphChunk: Non-empty slices of the parsed graph.

    Raises:
        ValueError: If the path is not a readable file, or if the flavor
            cannot be determined (or is not one of the three known values).
    """
    xml_path = validate_readable_xml_path(path)
    resolved = flavor or detect_ddi_format(xml_path)

    logger.debug(
        "Streaming graph view",
        extra={"path": str(xml_path), "flavor": resolved, "chunk_size": chunk_size},
    )

    if resolved == "codebook":
        yield from _codebook_chunks(
            xml_path,
            dataset_id=dataset_id or default_dataset_id(xml_path),
            dataset_name=dataset_name,
            chunk_size=chunk_size,
            recover=recover,
        )
    elif resolved == "lifecycle":
        yield from _lifecycle_chunks(xml_path, chunk_size=chunk_size, recover=recover)
    elif resolved == "cdi":
        yield from _cdi_chunks(xml_path, chunk_size=chunk_size, recover=recover)
    else:
        raise ValueError(
            f"Cannot build a graph view for {xml_path}: unrecognised DDI flavor "
            f"{resolved!r}. Expected one of 'codebook', 'lifecycle', 'cdi'."
        )


def _codebook_chunks(
    path: Path,
    *,
    dataset_id: str,
    dataset_name: str | None,
    chunk_size: int,
    recover: bool,
) -> Iterator[GraphChunk]:
    """Project DDI-Codebook batches through the existing ingest graph."""
    for batch in parse_ddi_batches(path, dataset_id, dataset_name, chunk_size, recover=recover):
        graph = DDIIngestGraph.from_ddi_batch(batch)
        chunk = GraphChunk(list(graph.nodes()), list(graph.relationships()))
        if chunk:
            yield chunk


def _lifecycle_chunks(path: Path, *, chunk_size: int, recover: bool) -> Iterator[GraphChunk]:
    """Project DDI-L fragment batches, resolving edge endpoints to labels.

    ``FragmentBatch.relationships`` holds ``(from_key, rel_type, to_key)``
    string triples with no labels attached, so endpoints are recovered from a
    key -> element-type map built while the node-only phase streams past. The
    parser's two-phase ordering guarantees the map is complete before the
    first edge arrives, and ``_resolve_reference`` drops edges whose target
    was never seen, so both endpoints are always known by then.
    """
    labels: dict[str, str] = {}
    parser = DDIFragmentParser(path, chunk_size=chunk_size, recover=recover)

    for batch in parser.parse_batches():
        chunk = GraphChunk(
            _fragment_nodes(batch, labels),
            _fragment_relationships(batch, labels),
        )
        if chunk:
            yield chunk


def _fragment_nodes(batch: FragmentBatch, labels: dict[str, str]) -> list[Node]:
    """Build nodes from a fragment batch, recording each key's label."""
    nodes: list[Node] = []
    for element_type, fragments in batch.fragments_by_type.items():
        for fragment in fragments:
            key = fragment.node_key
            labels[key] = element_type
            nodes.append(
                Node(
                    element_type,
                    {_FRAGMENT_ID_FIELD: key},
                    dict(fragment.to_dict()),
                )
            )
    return nodes


def _fragment_relationships(batch: FragmentBatch, labels: dict[str, str]) -> list[Relationship]:
    """Build relationships from a fragment batch using the label map."""
    relationships: list[Relationship] = []
    for from_key, rel_type, to_key in batch.relationships:
        relationships.append(
            Relationship(
                rel_type,
                _fragment_stub(from_key, labels),
                _fragment_stub(to_key, labels),
            )
        )
    return relationships


def _fragment_stub(key: str, labels: dict[str, str]) -> Node:
    """Return an identity-only endpoint node for a fragment key."""
    return Node(labels.get(key, "DDIFragment"), {_FRAGMENT_ID_FIELD: key}, {})


def _cdi_chunks(path: Path, *, chunk_size: int, recover: bool) -> Iterator[GraphChunk]:
    """Project DDI-CDI batches.

    CDI relationship records already carry both endpoint labels, so unlike the
    lifecycle path this needs no key -> label bookkeeping.
    """
    for batch in parse_cdi_batches(path, chunk_size, recover=recover):
        chunk = GraphChunk(_cdi_nodes(batch), _cdi_relationships(batch))
        if chunk:
            yield chunk


def _cdi_nodes(batch: CDIBatch) -> list[Node]:
    """Build nodes from every curated and generic CDI collection."""
    nodes: list[Node] = []
    for attr, label in _CDI_COLLECTION_LABELS.items():
        for record in getattr(batch, attr):
            nodes.append(_cdi_node(label, record))
    for record in batch.generic_entities:
        nodes.append(_cdi_node(_CDI_GENERIC_LABEL, record))
    return nodes


def _cdi_node(label: str, record: CDIRecord) -> Node:
    """Build one CDI node, dropping unset optional fields.

    ``CDIRecord`` is a ``slots=True`` dataclass, so it has no ``__dict__``
    to read; the field list is the only way in. Most of its thirteen
    optional extras are unset for any given entity type, and carrying them
    as explicit nulls would bloat every downstream serialization.
    """
    properties = {
        f.name: value
        for f in dataclasses.fields(record)
        if (value := getattr(record, f.name)) is not None
    }
    return Node(label, {_CDI_ID_FIELD: record.cdi_id}, properties)


def _normalise_cdi_label(raw: str) -> str:
    """Map a raw CDI association endpoint label onto an emittable node label.

    ``_CDI_RELATIONSHIP_MAP`` derives endpoint labels straight from the
    association tag, so ``Activity_has_Step`` yields ``CDIStep``. But the
    parser collapses many concrete tags into shared collections -- ``Step``
    lands in ``activities`` and surfaces as ``CDIActivity``, and any tag with
    no bespoke entry becomes a generic entity -- so 102 of the 134 endpoint
    labels name something ``_cdi_nodes`` can never emit.

    Left alone, a consumer matching endpoints on ``(label, identity)`` would
    invent a dangling node beside the real one. That matters immediately for
    RDF export, where the label is part of the minted subject IRI.

    Args:
        raw: The endpoint label recorded on the relationship, e.g. ``"CDIStep"``.

    Returns:
        The label ``_cdi_nodes`` would give the same entity.
    """
    tag = raw[3:] if raw.startswith("CDI") else raw
    entry = _CDI_TAG_MAP.get(tag)
    if entry is None:
        return _CDI_GENERIC_LABEL
    return _CDI_COLLECTION_LABELS.get(entry[1], _CDI_GENERIC_LABEL)


def _cdi_relationships(batch: CDIBatch) -> list[Relationship]:
    """Build relationships from parsed CDI association records."""
    return [
        Relationship(
            rel.rel_type,
            Node(_normalise_cdi_label(rel.source_label), {_CDI_ID_FIELD: rel.source_id}, {}),
            Node(_normalise_cdi_label(rel.target_label), {_CDI_ID_FIELD: rel.target_id}, {}),
        )
        for rel in batch.relationships
    ]


__all__ = ["GraphChunk", "iter_graph"]

"""Read RDF back into the backend-neutral graph view.

Everything in this package used to run one way: DDI XML in, something else
out. This module closes the loop, so a graph exported here -- or produced by
a colleague, or by a tool like maplib -- can be read back and loaded.

Reversal works because the writer deliberately keeps an identifying trace of
the original graph alongside the interoperable form:

* Every node carries a project-namespace ``rdf:type`` beside its standard
  class, because the standard alignment is many-to-one. ``disco:Question``
  cannot tell a ``Question`` from a ``QuestionItem``;
  ``ddigraph:QuestionItem`` can.
* The three published predicates reached by more than one relationship type
  get a project-namespace companion triple, for the same reason.

Properties are distinguished from relationships by the object itself: a
literal is a property, an IRI is an edge. That needs no convention and no
lookup table, and it holds for predicates this vocabulary has never seen.

The reader is tolerant on purpose. A subject with no project type is skipped
rather than guessed at, so pointing it at arbitrary RDF yields nothing
instead of nonsense.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ddigraph.graph.view import GraphChunk
from ddigraph.logging import get_logger
from ddigraph.rdf.vocabulary import (
    RDF,
    is_ambiguous_predicate,
    label_for_class_iri,
    property_field_for,
    relationship_type_for,
)
from ddigraph.schema.ddi_graph import NODE_RECORD_FIELDS, Node, Relationship
from ddigraph.schema.definitions import DDISchema

if TYPE_CHECKING:
    from rdflib import Graph

logger = get_logger(__name__)

#: Serialisation name per file extension, for callers that do not say.
EXTENSION_FORMATS: dict[str, str] = {
    ".ttl": "turtle",
    ".turtle": "turtle",
    ".nt": "nt",
    ".n3": "n3",
    ".jsonld": "json-ld",
    ".json": "json-ld",
    ".rdf": "xml",
    ".xml": "xml",
    ".owl": "xml",
}

# Identity is reconstructed from the properties the writer emitted, so the
# reader needs to know which of them was the identity. Candidates are
# recovered per label rather than assumed, because the flavors disagree.
_LIFECYCLE_IDENTITY = "fragment_id"
_CDI_IDENTITY = "cdi_id"


def read_graph(
    source: str | Path,
    *,
    format: str | None = None,
    chunk_size: int = 200,
) -> Iterator[GraphChunk]:
    """Stream an RDF file as backend-neutral graph chunks.

    Args:
        source: Path to a Turtle, N-Triples, JSON-LD or RDF/XML file.
        format: Override the serialisation instead of inferring it from the
            file extension.
        chunk_size: Nodes or relationships to accumulate per chunk.

    Yields:
        GraphChunk: Non-empty slices, nodes first and then relationships,
        matching the phase ordering the DDI-L parser already uses.

    Raises:
        ValueError: If the path is not a readable file.
        ImportError: If ``rdflib`` is not installed.
    """
    path = Path(source)
    if not path.is_file():
        raise ValueError(f"RDF path must reference a readable file: {path}")

    graph = _parse(path, format)
    labels = _labels(graph)

    parsed = list(_nodes(graph, labels))
    nodes = [node for _subject, node in parsed]
    # Endpoints must carry the same identity the node does, or a consumer
    # matching on ``(label, identity)`` -- which is what the Neo4j writer's
    # MATCH does -- finds nothing and silently drops every edge.
    identities = {subject: node.identity for subject, node in parsed}
    relationships = list(_relationships(graph, labels, identities))

    logger.info(
        "Read RDF graph",
        extra={
            "path": str(path),
            "triples": len(graph),
            "nodes": len(nodes),
            "relationships": len(relationships),
        },
    )

    yield from _chunked(nodes, relationships, chunk_size)


def _parse(path: Path, format: str | None) -> Graph:
    """Parse a file into an ``rdflib.Graph``."""
    try:
        from rdflib import Graph as RDFGraph
    except ImportError as exc:  # pragma: no cover - exercised by the CLI path
        raise ImportError(
            "Reading RDF needs rdflib, which is an optional extra. "
            'Install it with: pip install "ddigraph[rdf]"'
        ) from exc

    graph = RDFGraph()
    resolved = format or EXTENSION_FORMATS.get(path.suffix.lower())
    if resolved is None:
        # Unknown extension: let rdflib sniff rather than assume Turtle and
        # fail with a syntax error pointing at the wrong parser.
        graph.parse(str(path))
    else:
        graph.parse(str(path), format=resolved)
    return graph


def _labels(graph: Graph) -> dict[Any, str]:
    """Map every subject to its project-namespace label.

    Subjects without one are absent, which is how non-ddigraph RDF is
    ignored rather than misread.
    """
    from rdflib import URIRef

    rdf_type = URIRef(RDF + "type")
    labels: dict[Any, str] = {}
    for subject, obj in graph.subject_objects(rdf_type):
        label = label_for_class_iri(str(obj))
        if label is not None:
            labels[subject] = label
    return labels


def _composite_fields() -> dict[str, tuple[str, ...]]:
    """Label -> the fields a composite identity is keyed on."""
    return {
        node.label: node.composite_id_fields
        for node in DDISchema.get_all_nodes()
        if node.composite_id_fields
    }


_COMPOSITE_FIELDS: dict[str, tuple[str, ...]] = _composite_fields()


def _identity_key(label: str, properties: dict[str, object]) -> dict[str, object]:
    """Recover a node's identity dict from its parsed properties.

    The RDF does not record which flavor produced it and the flavors key
    differently, so identity is resolved by what is actually present.
    Guessing wrong is not cosmetic: the identity dict decides the subject
    IRI on re-export, so a wrong answer silently moves every node to a new
    IRI and the round trip stops being one.

    DDI-L fragments and DDI-CDI entities are checked first because their
    keys are unambiguous. Codebook identity is looked up in
    ``NODE_RECORD_FIELDS`` rather than derived from the label, because it is
    not always ``<thing>_id``: a ``Concept`` is keyed on ``name``.
    """
    composite = _COMPOSITE_FIELDS.get(label)
    if composite and all(field in properties for field in composite):
        return {field: properties[field] for field in composite}

    for candidate in (_LIFECYCLE_IDENTITY, _CDI_IDENTITY):
        if candidate in properties:
            return {candidate: properties[candidate]}

    record = NODE_RECORD_FIELDS.get(label)
    if record and record[0] in properties:
        return {record[0]: properties[record[0]]}

    if "id" in properties:
        return {"id": properties["id"]}

    logger.debug("No identity recovered", extra={"label": label})
    return {}


def _nodes(graph: Graph, labels: dict[Any, str]) -> Iterator[tuple[Any, Node]]:
    """Rebuild nodes from literal-valued triples."""
    from rdflib import Literal

    grouped: dict[Any, dict[str, object]] = {}
    for subject, predicate, obj in graph:
        if subject not in labels or not isinstance(obj, Literal):
            continue
        field = property_field_for(str(predicate))
        if field is None:
            continue
        properties = grouped.setdefault(subject, {})
        value = obj.toPython()
        if field in properties:
            # A repeated predicate is a list-valued attribute on the way
            # back, e.g. ``external_references``.
            existing = properties[field]
            if isinstance(existing, list):
                existing.append(value)
            else:
                properties[field] = [existing, value]
        else:
            properties[field] = value

    for subject, label in labels.items():
        properties = grouped.get(subject, {})
        yield subject, Node(label, _identity_key(label, properties), properties)


def _relationships(
    graph: Graph,
    labels: dict[Any, str],
    identities: dict[Any, dict[str, object]],
) -> Iterator[Relationship]:
    """Rebuild relationships from IRI-valued triples.

    Predicates that carry a project-namespace companion are skipped here:
    the companion states the same edge with its original type and direction,
    so honouring both would double every one of them.
    """
    from rdflib import URIRef

    rdf_type = URIRef(RDF + "type")
    for subject, predicate, obj in graph:
        if predicate == rdf_type or subject not in labels or not isinstance(obj, URIRef):
            continue
        if obj not in labels or is_ambiguous_predicate(str(predicate)):
            continue
        rel_type = relationship_type_for(str(predicate))
        if rel_type is None:
            continue
        yield Relationship(
            rel_type,
            Node(labels[subject], dict(identities.get(subject, {})), {}),
            Node(labels[obj], dict(identities.get(obj, {})), {}),
        )


def _chunked(
    nodes: list[Node],
    relationships: list[Relationship],
    chunk_size: int,
) -> Iterator[GraphChunk]:
    """Emit nodes then relationships in bounded chunks."""
    for start in range(0, len(nodes), chunk_size):
        yield GraphChunk(nodes[start : start + chunk_size], [])
    for start in range(0, len(relationships), chunk_size):
        yield GraphChunk([], relationships[start : start + chunk_size])


__all__ = ["EXTENSION_FORMATS", "read_graph"]

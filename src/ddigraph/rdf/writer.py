"""Turn a stream of :class:`~ddigraph.graph.view.GraphChunk` into RDF.

The writer is deliberately thin: :mod:`ddigraph.rdf.vocabulary` decides
*which* IRI every label, relationship and attribute maps to, and this module
decides only how to lay the triples out. Keeping the two apart is what lets
the vocabulary be reviewed, tested and documented without ``rdflib``
installed.

``rdflib`` is imported inside functions, never at module scope --
``tests/test_extras_lazy_imports.py`` fails the build otherwise, because a
top-level import would silently turn an optional extra back into a hard
runtime dependency of ``pip install ddigraph``.

Two behaviours are worth knowing about:

* **Every node carries two ``rdf:type`` triples** where a standard alignment
  exists -- see :func:`ddigraph.rdf.vocabulary.class_iris`.
* **Container-to-member edges are emitted inverted** so code lists come out
  as valid SKOS. See
  :func:`ddigraph.rdf.vocabulary.is_inverted_predicate`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from ddigraph.logging import get_logger
from ddigraph.rdf.vocabulary import (
    PREFIXES,
    RDF,
    XSD,
    class_iris,
    is_ambiguous_predicate,
    is_inverted_predicate,
    is_skos_typed,
    predicate_iri,
    project_predicate_iri,
    property_iri,
    subject_iri,
)

if TYPE_CHECKING:
    from rdflib import Graph

    from ddigraph.graph.view import GraphChunk
    from ddigraph.schema.ddi_graph import Node, Relationship

logger = get_logger(__name__)

# Attributes that describe the record's own bookkeeping rather than the
# thing being described. ``language`` becomes a literal language tag on the
# other properties instead of a predicate of its own.
_SKIPPED_PROPERTIES = frozenset({"language"})

# Properties that carry natural-language text and so take the record's
# language tag when it has one.
_LANGUAGE_TAGGED = frozenset(
    {"label", "name", "title", "description", "question_text", "rationale", "purpose"}
)


def build_graph(
    chunks: Iterable[GraphChunk],
    *,
    base: str | None = None,
) -> Graph:
    """Build an in-memory RDF graph from streamed graph chunks.

    Args:
        chunks: Chunks as produced by :func:`ddigraph.graph.view.iter_graph`.
        base: IRI stem for subjects whose identity is not already a URN.

    Returns:
        An ``rdflib.Graph`` with every vocabulary prefix bound.

    Raises:
        ImportError: If ``rdflib`` is not installed.
    """
    graph = _new_graph()
    nodes = relationships = 0

    for chunk in chunks:
        for node in chunk.nodes:
            _add_node(graph, node, base)
            nodes += 1
        for relationship in chunk.relationships:
            _add_relationship(graph, relationship, base)
            relationships += 1

    logger.info(
        "Built RDF graph",
        extra={"nodes": nodes, "relationships": relationships, "triples": len(graph)},
    )
    return graph


def _new_graph() -> Graph:
    """Create an empty graph with the vocabulary prefixes bound."""
    try:
        from rdflib import Graph as RDFGraph
    except ImportError as exc:  # pragma: no cover - exercised by the CLI path
        raise ImportError(
            "RDF export needs rdflib, which is an optional extra. "
            'Install it with: pip install "ddigraph[rdf]"'
        ) from exc

    graph = RDFGraph()
    for prefix, namespace in PREFIXES.items():
        graph.bind(prefix, namespace)
    return graph


def _node_iri(node: Node, base: str | None) -> str:
    """Return the subject IRI for a node.

    Derived from label and identity only. A relationship endpoint is a stub
    carrying exactly those two things and no properties, so anything else
    would put an edge's endpoint on a different IRI from the node itself.

    Every identity value participates, not just the first. Composite
    identities exist -- ``DDIGenericIdentifiable`` is keyed on
    ``(dataset_id, element_tag, identifiable_id)`` -- and taking the first
    value alone collapsed all fourteen of them in a codebook fixture onto
    one subject, silently merging fourteen nodes' properties into one.
    Keys are sorted so the result does not depend on dict ordering.
    """
    parts = [str(value) for _key, value in sorted(node.identity.items())]
    return subject_iri(node.label, parts or [""], base=base)


def _add_node(graph: Graph, node: Node, base: str | None) -> None:
    """Add one node's type and property triples."""
    from rdflib import URIRef

    subject = URIRef(_node_iri(node, base))

    for class_iri in class_iris(node.label):
        graph.add((subject, URIRef(RDF + "type"), URIRef(class_iri)))

    skos_typed = is_skos_typed(node.label)
    language = node.properties.get("language")
    lang = str(language) if isinstance(language, str) and language else None

    for field, value in node.properties.items():
        if value is None or field in _SKIPPED_PROPERTIES:
            continue
        predicate = URIRef(property_iri(field, skos_typed=skos_typed))
        for item in value if isinstance(value, (list, tuple, set)) else (value,):
            if item is None:
                continue
            graph.add((subject, predicate, _literal(item, field, lang)))


def _literal(value: Any, field: str, lang: str | None) -> Any:
    """Return a typed or language-tagged literal for a property value.

    ``bool`` is checked before ``int`` deliberately: ``bool`` is a subclass
    of ``int`` in Python, so the natural ordering would type every boolean
    as ``xsd:integer``.
    """
    from rdflib import Literal, URIRef

    if isinstance(value, bool):
        return Literal(value, datatype=URIRef(XSD + "boolean"))
    if isinstance(value, int):
        return Literal(value, datatype=URIRef(XSD + "integer"))
    if isinstance(value, float):
        return Literal(value, datatype=URIRef(XSD + "double"))
    if lang and field in _LANGUAGE_TAGGED:
        return Literal(str(value), lang=lang)
    return Literal(str(value))


def _add_relationship(graph: Graph, relationship: Relationship, base: str | None) -> None:
    """Add one relationship triple, inverting it when SKOS requires.

    Three published predicates are reached by more than one relationship
    type -- ``disco:question``, ``skos:inScheme`` and ``dcterms:isPartOf``,
    covering nine of 369 types -- and ``skos:inScheme`` additionally loses
    the graph's edge direction. For those, a project-namespace companion is
    emitted in the graph direction so :mod:`ddigraph.rdf.reader` can recover
    the original type, exactly as every node carries a project ``rdf:type``
    beside its standard one. The remaining published predicates are
    one-to-one, so no companion is written and the output stays lean.
    """
    from rdflib import URIRef

    start = URIRef(_node_iri(relationship.start, base))
    end = URIRef(_node_iri(relationship.end, base))
    resolved = predicate_iri(relationship.type)
    predicate = URIRef(resolved)

    if is_inverted_predicate(relationship.type):
        graph.add((end, predicate, start))
    else:
        graph.add((start, predicate, end))

    if is_ambiguous_predicate(resolved):
        graph.add((start, URIRef(project_predicate_iri(relationship.type)), end))


__all__ = ["build_graph"]

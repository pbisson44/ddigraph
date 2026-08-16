"""Derive SHACL shapes from the same schema that drives ingestion.

``DDISchema`` is already the single source of truth for Neo4j constraints
and indexes -- :meth:`~ddigraph.schema.definitions.DDISchema.generate_constraint_queries`
walks ``get_all_nodes()`` and emits Cypher. SHACL is the same walk with a
different emitter, which is why the shapes cannot drift from the data: both
come from one table.

The shapes give RDF consumers something the package never offered before: a
way to check that a graph they received is the shape ddigraph claims to
produce. Exported output is validated against them in the test suite, so the
vocabulary and the writer are held to the same contract as everyone else.

Two constraints are deliberately conservative, because a shape that fires on
correct data is worse than no shape at all:

* **Cardinality** is asserted only for the identity property. Other
  attributes may legitimately repeat -- ``external_references`` is a list --
  and nothing in the schema records which.
* **``sh:class``** is asserted only where a given subject class and predicate
  lead to exactly one object class across the whole schema. Several
  relationship types share a predicate (``ASKS_QUESTION`` and
  ``USES_QUESTION_ITEM`` both become ``disco:question``), so an
  unconditional class constraint would contradict itself.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from ddigraph.graph.view import _normalise_cdi_label
from ddigraph.ingest.cdi_loader import _CDI_RELATIONSHIP_MAP
from ddigraph.logging import get_logger
from ddigraph.rdf.vocabulary import (
    PREFIXES,
    RDF,
    RDFS,
    SH,
    is_ambiguous_predicate,
    is_inverted_predicate,
    is_skos_typed,
    predicate_iri,
    project_class_iri,
    project_predicate_iri,
    property_iri,
)
from ddigraph.schema.ddi_graph import DDI_RELATIONSHIPS, NODE_RECORD_FIELDS
from ddigraph.schema.definitions import DDISchema, NodeDefinition

if TYPE_CHECKING:
    from rdflib import Graph, URIRef

logger = get_logger(__name__)

#: Namespace the generated node shapes live in.
SHAPES_NS = "https://pbisson44.github.io/ddigraph/shapes/1.0/"


#: The DDI flavors shapes can be scoped to.
FLAVORS: tuple[str, ...] = ("codebook", "lifecycle", "cdi")


def _nodes_for(flavor: str | None) -> tuple[NodeDefinition, ...]:
    """Return the node definitions in scope for a flavor."""
    if flavor == "codebook":
        return DDISchema.CODEBOOK_NODES
    if flavor == "lifecycle":
        return DDISchema.FRAGMENT_NODES
    if flavor == "cdi":
        return DDISchema.CDI_NODES
    return DDISchema.get_all_nodes()


def _scoped_nodes(flavor: str | None) -> list[tuple[str, NodeDefinition]]:
    """Pair every in-scope node definition with the flavor that defines it.

    The flavor has to travel with the node: identity lives under a different
    record attribute per flavor, and the table that knows the codebook
    answer does not describe the other two.
    """
    if flavor is not None:
        return [(flavor, node) for node in _nodes_for(flavor)]
    return [(f, node) for f in FLAVORS for node in _nodes_for(f)]


def _shared_labels() -> set[str]:
    """Return labels that mean different things in different flavors.

    Twenty-one labels appear in both the codebook and lifecycle tables --
    ``Category``, ``CodeList``, ``Variable`` and friends -- and they do not
    agree on the identity field: a codebook ``Category`` is keyed on ``id``,
    a DDI-L one on ``fragment_id``. Both shapes target the same class, so an
    unscoped shapes graph asserts each flavor's identity requirement against
    the other flavor's data and reports 71 violations on correct output.
    """
    counts: dict[str, set[str]] = defaultdict(set)
    for flavor in FLAVORS:
        for node in _nodes_for(flavor):
            counts[node.label].add(flavor)
    return {label for label, flavors in counts.items() if len(flavors) > 1}


def _record_fields(flavor: str, node: NodeDefinition) -> tuple[str, tuple[str, ...]]:
    """Return the identity attribute and property attributes for a node.

    ``NodeDefinition`` describes the *Neo4j* side: ``id_field`` is the node
    property the Cypher merges on (44 of 45 codebook mappings call it
    ``id``) and ``properties`` names graph properties. The writer emits the
    *record* side, the attributes ``DDIIngestGraph.nodes()`` reads
    (``MERGE (s:Study {id: row.study_id})``). Shapes built from the Neo4j
    names would constrain ``ddigraph:id``, which no exported ``Study``
    contains, and say nothing about ``ddigraph:studyId``, which every one
    does.

    Only the codebook tier diverges: DDI-L keys every fragment on
    ``fragment_id`` and DDI-CDI on ``cdi_id``, and there the
    ``NodeDefinition`` already names record attributes.
    """
    if flavor != "codebook":
        return node.id_field, node.properties
    return NODE_RECORD_FIELDS.get(node.label, (node.id_field, node.properties))


def _edges(flavor: str | None) -> list[tuple[str, str, str]]:
    """Return every ``(start_label, rel_type, end_label)`` in scope.

    DDI-L contributes none at all: ``FRAGMENT_RELATIONSHIP_TYPES`` maps a
    reference tag to a relationship type and records no endpoint labels, so
    there is nothing to constrain. Codebook edges must not leak into a
    lifecycle scope, because the two disagree -- a codebook category sits in
    a ``CodeScheme``, a DDI-L one in a ``CodeList``.
    """
    edges: list[tuple[str, str, str]] = []
    if flavor in (None, "codebook"):
        edges += [(rel.start_label, rel.type, rel.end_label) for rel in DDI_RELATIONSHIPS]
    if flavor in (None, "cdi"):
        edges += [
            (_normalise_cdi_label(source), rel_type, _normalise_cdi_label(target))
            for rel_type, source, target in _CDI_RELATIONSHIP_MAP.values()
        ]
    return edges


def _object_classes(flavor: str | None) -> dict[tuple[str, str], set[str]]:
    """Map ``(subject_label, predicate)`` to every object class it may take.

    Inverted predicates are recorded against the object's shape, since that
    is the subject the triple actually has once emitted.
    """
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    for start_label, rel_type, end_label in _edges(flavor):
        predicate = predicate_iri(rel_type)
        if is_inverted_predicate(rel_type):
            grouped[(end_label, predicate)].add(project_class_iri(start_label))
        else:
            grouped[(start_label, predicate)].add(project_class_iri(end_label))

        # Ambiguous published predicates get a project-namespace companion
        # in the writer, always in graph direction. Shapes have to describe
        # it too, or the output carries predicates nothing constrains.
        if is_ambiguous_predicate(predicate):
            companion = project_predicate_iri(rel_type)
            grouped[(start_label, companion)].add(project_class_iri(end_label))
    return grouped


def shapes_graph(*, flavor: str | None = None) -> Graph:
    """Build a SHACL shapes graph for the DDI vocabulary.

    Args:
        flavor: Restrict the shapes to one DDI flavor -- ``"codebook"``,
            ``"lifecycle"`` or ``"cdi"``. Strongly preferred when validating
            real data, because a data graph comes from a file of exactly one
            flavor. Passing ``None`` emits shapes for all three and, for the
            labels the flavors define differently, drops the constraints
            they disagree on.

    Returns:
        An ``rdflib.Graph`` of ``sh:NodeShape`` definitions.

    Raises:
        ValueError: If ``flavor`` is not one of :data:`FLAVORS` or ``None``.
        ImportError: If ``rdflib`` is not installed.
    """
    if flavor is not None and flavor not in FLAVORS:
        raise ValueError(f"Unknown flavor {flavor!r}. Expected one of: {', '.join(FLAVORS)}")
    try:
        from rdflib import Graph as RDFGraph, Literal, URIRef
    except ImportError as exc:  # pragma: no cover - exercised by the CLI path
        raise ImportError(
            "SHACL shape generation needs rdflib, which is an optional extra. "
            'Install it with: pip install "ddigraph[shacl]"'
        ) from exc

    graph = RDFGraph()
    for prefix, namespace in PREFIXES.items():
        graph.bind(prefix, namespace)
    graph.bind("sh", SH)
    graph.bind("shapes", SHAPES_NS)

    classes = _object_classes(flavor)
    nodes = _scoped_nodes(flavor)
    ambiguous = _shared_labels() if flavor is None else set()

    for node_flavor, node in nodes:
        shape = URIRef(f"{SHAPES_NS}{node.label}Shape")
        graph.add((shape, URIRef(RDF + "type"), URIRef(SH + "NodeShape")))
        graph.add((shape, URIRef(SH + "targetClass"), URIRef(project_class_iri(node.label))))
        graph.add((shape, URIRef(RDFS + "label"), Literal(f"{node.label} shape")))

        skos_typed = is_skos_typed(node.label)
        seen: set[str] = set()

        # Identity: exactly one, always present -- the only cardinality the
        # schema actually guarantees. Skipped for a label the flavors key
        # differently, where asserting either answer would be wrong for the
        # other. Composite identities are skipped too: the parts repeat
        # across sibling nodes, so no single one is unique.
        identity_field, record_properties = _record_fields(node_flavor, node)

        if node.label not in ambiguous and not node.composite_id_fields:
            identity_path = property_iri(identity_field, skos_typed=skos_typed)
            _add_property(
                graph,
                shape,
                identity_path,
                min_count=1,
                max_count=1,
                node_kind="Literal",
            )
            seen.add(identity_path)

        for field in record_properties:
            path = property_iri(field, skos_typed=skos_typed)
            if path in seen:
                continue
            seen.add(path)
            _add_property(graph, shape, path, node_kind="Literal")

        for (label, predicate), object_classes in classes.items():
            if label != node.label or predicate in seen:
                continue
            seen.add(predicate)
            # ``sh:class`` needs one unambiguous answer. Several relationship
            # types share a predicate (ASKS_QUESTION and USES_QUESTION_ITEM
            # both become disco:question), and in an unscoped graph a shared
            # label draws edges from a flavor whose endpoints differ -- a
            # codebook category sits in a CodeScheme, a DDI-L one in a
            # CodeList. Either way, fall back to asserting only that the
            # object is an IRI.
            unambiguous = len(object_classes) == 1 and node.label not in ambiguous
            _add_property(
                graph,
                shape,
                predicate,
                node_kind="IRI",
                object_class=next(iter(object_classes)) if unambiguous else None,
            )

    logger.info(
        "Generated SHACL shapes",
        extra={"shapes": len(nodes), "triples": len(graph)},
    )
    return graph


def _add_property(
    graph: Graph,
    shape: URIRef,
    path: str,
    *,
    min_count: int | None = None,
    max_count: int | None = None,
    node_kind: str | None = None,
    object_class: str | None = None,
) -> None:
    """Attach one ``sh:property`` constraint to a node shape."""
    from rdflib import BNode, Literal, URIRef

    constraint = BNode()
    graph.add((shape, URIRef(SH + "property"), constraint))
    graph.add((constraint, URIRef(SH + "path"), URIRef(path)))
    if min_count is not None:
        graph.add((constraint, URIRef(SH + "minCount"), Literal(min_count)))
    if max_count is not None:
        graph.add((constraint, URIRef(SH + "maxCount"), Literal(max_count)))
    if node_kind is not None:
        graph.add((constraint, URIRef(SH + "nodeKind"), URIRef(SH + node_kind)))
    if object_class is not None:
        graph.add((constraint, URIRef(SH + "class"), URIRef(object_class)))


__all__ = ["SHAPES_NS", "shapes_graph"]

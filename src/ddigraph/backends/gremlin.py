"""Write the graph to any Apache TinkerPop (Gremlin) server.

>>> from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
>>> from gremlin_python.process.anonymous_traversal import traversal
>>> from ddigraph.backends.gremlin import write_gremlin
>>> connection = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")  # doctest: +SKIP
>>> g = traversal().with_(connection)  # doctest: +SKIP
>>> write_gremlin(g, "survey.xml")  # doctest: +SKIP

Writes are **upserts**: a vertex is found by its label and ``node_key``
property, and created only if absent; an edge only if the same type does not
already join the same two vertices. Loading a file twice changes nothing.

Writes are batched -- one request per ``batch_size`` vertices or edges --
because a round trip per element dominates load time on a remote server.

Two choices keep it portable across TinkerGraph, JanusGraph, Neptune and
Cosmos DB:

* **Reserved names.** ``id`` and ``label`` mean the element id and label to
  some providers (Cosmos DB rejects them as property keys), and DDI records
  use both -- a codebook category is keyed on ``id``, and most nodes have a
  human-readable ``label``. They are written as ``ddi_id`` and ``ddi_label``.
* **Lists** are joined with ``|``, as in the CSV export. Provider support
  for multi-properties varies too much to rely on.

Look a vertex up the way the writer does:
``g.V().has("Variable", "node_key", "v1")``. On a large graph, index
``node_key`` first -- how depends on the provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ddigraph.backends import GraphSource, flatten, graph_chunks
from ddigraph.graph.view import node_key
from ddigraph.logging import get_logger

if TYPE_CHECKING:
    from gremlin_python.process.graph_traversal import GraphTraversal, GraphTraversalSource

    from ddigraph.schema.ddi_graph import Node, Relationship

logger = get_logger(__name__)

#: The vertex property the writer looks vertices up by.
KEY_PROPERTY = "node_key"

#: Property names some providers reserve, and what they are written as.
RESERVED: dict[str, str] = {"id": "ddi_id", "label": "ddi_label"}


@dataclass(slots=True)
class GremlinResult:
    """Summary of one :func:`write_gremlin` call.

    Attributes:
        nodes: Vertices upserted.
        relationships: Edges upserted.
        skipped: Edges not written because an endpoint vertex was missing.
    """

    nodes: int = 0
    relationships: int = 0
    skipped: int = 0


def _property_name(key: str) -> str:
    return RESERVED.get(key, key)


def _vertex(node: Node, cardinality: Any) -> GraphTraversal:
    """An anonymous traversal that upserts one vertex and emits it."""
    from gremlin_python.process.graph_traversal import __

    key = node_key(node)
    traversal = (
        __.V()
        .has(node.label, KEY_PROPERTY, key)
        .fold()
        .coalesce(__.unfold(), __.add_v(node.label).property(KEY_PROPERTY, key))
    )
    for name, value in {**node.identity, **node.properties}.items():
        if value is None:
            continue
        args = (_property_name(name), flatten(value))
        traversal = (
            traversal.property(cardinality, *args)
            if cardinality is not None
            else traversal.property(*args)
        )
    return traversal


def _edge(rel: Relationship) -> GraphTraversal:
    """An anonymous traversal that upserts one edge, or emits nothing.

    Nothing comes out when an endpoint is missing, which is how
    :func:`write_gremlin` counts the edges it could not write.
    """
    from gremlin_python.process.graph_traversal import __

    traversal = (
        __.V()
        .has(rel.start.label, KEY_PROPERTY, node_key(rel.start))
        .as_("start")
        .V()
        .has(rel.end.label, KEY_PROPERTY, node_key(rel.end))
        .coalesce(
            __.in_e(rel.type).where(__.out_v().as_("start")),
            __.add_e(rel.type).from_("start"),
        )
    )
    for name, value in (rel.properties or {}).items():
        if value is not None:
            traversal = traversal.property(_property_name(name), flatten(value))
    return traversal


def _submit(g: GraphTraversalSource, branches: list[GraphTraversal]) -> int:
    """Run upserts as one request and return how many emitted a result.

    Each branch is wrapped in ``union`` from a single injected traverser, so
    a branch that finds nothing -- an edge with a missing endpoint -- cannot
    stop the branches after it, as it would in a plain chain.
    """
    return len(g.inject(0).union(*(branch.constant(1) for branch in branches)).to_list())


def write_gremlin(
    g: GraphTraversalSource,
    source: GraphSource,
    *,
    batch_size: int = 50,
    cardinality: str | None = "single",
    flavor: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    chunk_size: int = 200,
) -> GremlinResult:
    """Upsert a DDI or RDF source into a Gremlin server.

    Args:
        g: A traversal source bound to a remote connection.
        source: A DDI XML path, an RDF path, or an iterable of chunks.
        batch_size: Vertices or edges per request.
        cardinality: ``"single"`` replaces a property's value on reload; pass
            ``None`` for a provider that only supports the default (list)
            cardinality, at the cost of repeated values when reloading.
        flavor: Force a DDI flavor. DDI XML only.
        dataset_id: Dataset identifier for the codebook flavor.
        dataset_name: Human-readable dataset name for the codebook flavor.
        chunk_size: Records per streamed chunk.

    Returns:
        GremlinResult: How many vertices and edges were written or skipped.

    Raises:
        ImportError: If ``gremlinpython`` is not installed.
        ValueError: If ``batch_size`` is not positive.
    """
    try:
        from gremlin_python.process.traversal import Cardinality
    except ImportError as exc:
        raise ImportError(
            "The Gremlin backend needs gremlinpython, which is optional. "
            'Install it with: pip install "ddigraph[gremlin]"'
        ) from exc
    if batch_size < 1:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    card = getattr(Cardinality, cardinality) if cardinality is not None else None
    result = GremlinResult()

    def batches(items: list[Any]) -> list[list[Any]]:
        return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    # Vertices are written as they stream; edges wait until every vertex is
    # in. A codebook is parsed in batches, and an edge in one batch may point
    # at a vertex that only arrives in a later one -- written early, it would
    # find no endpoint and be skipped.
    edges: list[Relationship] = []
    pending: list[Node] = []
    for chunk in graph_chunks(
        source,
        flavor=flavor,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        chunk_size=chunk_size,
    ):
        edges.extend(chunk.relationships)
        pending.extend(chunk.nodes)
        while len(pending) >= batch_size:
            batch, pending = pending[:batch_size], pending[batch_size:]
            result.nodes += _submit(g, [_vertex(node, card) for node in batch])
    if pending:
        result.nodes += _submit(g, [_vertex(node, card) for node in pending])

    for edge_batch in batches(edges):
        written = _submit(g, [_edge(rel) for rel in edge_batch])
        result.relationships += written
        result.skipped += len(edge_batch) - written

    if result.skipped:
        logger.warning(
            "Skipped edges whose endpoint vertex was missing",
            extra={"skipped": result.skipped},
        )
    logger.info(
        "Wrote to Gremlin",
        extra={"nodes": result.nodes, "relationships": result.relationships},
    )
    return result


__all__ = ["KEY_PROPERTY", "RESERVED", "GremlinResult", "write_gremlin"]

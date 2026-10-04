"""Load the graph into NetworkX for in-memory analysis.

>>> from ddigraph.backends.networkx import to_networkx
>>> G = to_networkx("survey.xml")  # doctest: +SKIP

The result is an ``nx.MultiDiGraph``: directed, because DDI relationships
are, and *multi*, because two nodes can be linked by more than one
relationship type. Each edge's key is its relationship type, so loading the
same file twice does not double the edges.

Node ids are ``"<label>:<key>"`` with the key from
:func:`~ddigraph.graph.view.node_key`. The label is part of the id because
a key is only unique within its label: a codebook may use ``c1`` for both a
category and a concept.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ddigraph.backends import GraphSource, flatten, graph_chunks
from ddigraph.graph.view import node_key
from ddigraph.logging import get_logger

if TYPE_CHECKING:
    import networkx as nx

    from ddigraph.schema.ddi_graph import Node

logger = get_logger(__name__)


def node_id(node: Node) -> str:
    """Return the NetworkX node id for a graph node.

    Args:
        node: The node.

    Returns:
        ``"<label>:<key>"``.
    """
    return f"{node.label}:{node_key(node)}"


def to_networkx(
    source: GraphSource,
    *,
    graph: nx.MultiDiGraph | None = None,
    flatten_lists: bool = False,
    flavor: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    chunk_size: int = 200,
) -> nx.MultiDiGraph:
    """Build (or extend) a NetworkX graph from a DDI or RDF source.

    Every node carries ``node_type`` (its label), ``node_key``, its identity
    fields and its properties, with ``None`` values left out. ``node_type``
    is not called ``label`` because most DDI records have a ``label``
    property of their own -- the human-readable one -- and it would collide.
    Every edge carries ``relationship`` (its type) and its properties.

    Args:
        source: A DDI XML path, an RDF path, or an iterable of chunks.
        graph: Add to this graph instead of a new one. Loading several files
            into one graph merges the nodes they share.
        flatten_lists: Join list values with ``|``. Needed before
            ``nx.write_graphml`` or ``nx.write_gexf``, which reject lists.
        flavor: Force a DDI flavor. DDI XML only.
        dataset_id: Dataset identifier for the codebook flavor.
        dataset_name: Human-readable dataset name for the codebook flavor.
        chunk_size: Records per streamed chunk.

    Returns:
        The graph.

    Raises:
        ImportError: If ``networkx`` is not installed.
    """
    try:
        import networkx as nx
    except ImportError as exc:
        raise ImportError(
            "The NetworkX backend needs networkx, which is optional. "
            'Install it with: pip install "ddigraph[networkx]"'
        ) from exc

    target: nx.MultiDiGraph = nx.MultiDiGraph() if graph is None else graph

    def clean(values: dict[str, object]) -> dict[str, Any]:
        return {
            key: flatten(value) if flatten_lists else value
            for key, value in values.items()
            if value is not None
        }

    nodes = edges = 0
    for chunk in graph_chunks(
        source,
        flavor=flavor,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        chunk_size=chunk_size,
    ):
        for node in chunk.nodes:
            attributes = clean({**node.identity, **node.properties})
            attributes["node_type"] = node.label
            attributes["node_key"] = node_key(node)
            target.add_node(node_id(node), **attributes)
            nodes += 1
        for rel in chunk.relationships:
            attributes = clean(dict(rel.properties or {}))
            attributes["relationship"] = rel.type
            target.add_edge(node_id(rel.start), node_id(rel.end), key=rel.type, **attributes)
            edges += 1

    logger.info("Built NetworkX graph", extra={"nodes": nodes, "relationships": edges})
    return target


__all__ = ["node_id", "to_networkx"]

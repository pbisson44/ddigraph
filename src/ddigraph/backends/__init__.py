"""Write the graph to backends other than Neo4j.

Each module turns the backend-neutral :class:`~ddigraph.graph.view.GraphChunk`
stream into one target:

* :mod:`ddigraph.backends.networkx` -- an in-memory ``nx.MultiDiGraph``.
* :mod:`ddigraph.backends.pandas` -- node and relationship DataFrames.
* :mod:`ddigraph.backends.gremlin` -- upserts into any TinkerPop server.

Before 0.5.1 these existed only as ``demo/load_*.py`` scripts outside the
package. They now share one input contract, :func:`graph_chunks`: a DDI XML
file, an RDF file, or chunks you already have.

Every backend library is an optional extra and is imported inside the
function that needs it, so ``import ddigraph.backends.networkx`` works on a
base install and fails only when called.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ddigraph.graph.view import GraphChunk

#: What every backend accepts: a path, or chunks already streamed.
GraphSource = str | Path | Iterable["GraphChunk"]


def graph_chunks(
    source: GraphSource,
    *,
    flavor: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    chunk_size: int = 200,
) -> Iterator[GraphChunk]:
    """Stream chunks from a DDI XML file, an RDF file, or existing chunks.

    RDF is recognised by extension, exactly as ``ddigraph load`` does, so a
    Turtle export round-trips into any backend.

    Args:
        source: A DDI XML path, an RDF path, or an iterable of chunks.
        flavor: Force a DDI flavor. DDI XML only.
        dataset_id: Dataset identifier for the codebook flavor.
        dataset_name: Human-readable dataset name for the codebook flavor.
        chunk_size: Records per chunk.

    Yields:
        GraphChunk: Nodes first, then relationships.
    """
    if not isinstance(source, (str, Path)):
        yield from source
        return

    from ddigraph.validation import is_rdf_path

    if is_rdf_path(source):
        from ddigraph.rdf.reader import read_graph

        yield from read_graph(source, chunk_size=chunk_size)
        return

    from ddigraph.graph.view import iter_graph

    yield from iter_graph(
        source,
        flavor=flavor,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        chunk_size=chunk_size,
    )


def flatten(value: object) -> object:
    """Render a list as one ``|``-joined string; pass anything else through.

    The convention the CSV export already uses. Backends that cannot store a
    list -- GraphML files, most Gremlin providers -- need it.
    """
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value)
    return value


__all__ = ["GraphSource", "flatten", "graph_chunks"]

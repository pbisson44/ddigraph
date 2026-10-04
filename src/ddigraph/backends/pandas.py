"""Load the graph into pandas DataFrames.

>>> from ddigraph.backends.pandas import to_dataframes
>>> frames = to_dataframes("survey.xml")  # doctest: +SKIP
>>> frames.of("Variable")  # doctest: +SKIP

A graph does not fit one rectangle, so there are two: one row per node and
one per relationship. They are the same records ``ddigraph export --format
csv`` writes, so the columns match that export, and the two frames join on
``(node_label, node_id)`` = ``(start_label, start_id)`` or
``(end_label, end_id)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ddigraph.backends import GraphSource, graph_chunks
from ddigraph.exporter import _node_record, _relationship_record
from ddigraph.logging import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)

#: Relationship columns, in order.
RELATIONSHIP_COLUMNS: tuple[str, ...] = ("start_label", "start_id", "type", "end_label", "end_id")


@dataclass(slots=True)
class GraphFrames:
    """The graph as two DataFrames.

    Attributes:
        nodes: One row per node. ``node_label`` and ``node_id`` come first,
            then the sorted union of every node type's fields -- so a given
            row leaves most columns empty.
        relationships: One row per relationship.
    """

    nodes: pd.DataFrame
    relationships: pd.DataFrame

    def of(self, label: str) -> pd.DataFrame:
        """Return the nodes of one type, with only the columns it uses.

        Args:
            label: A node label such as ``"Variable"``.

        Returns:
            The matching rows, minus every column that is empty for all of them.
        """
        rows = self.nodes[self.nodes["node_label"] == label]
        return rows.dropna(axis="columns", how="all").reset_index(drop=True)


def to_dataframes(
    source: GraphSource,
    *,
    flavor: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    chunk_size: int = 200,
) -> GraphFrames:
    """Build node and relationship DataFrames from a DDI or RDF source.

    Args:
        source: A DDI XML path, an RDF path, or an iterable of chunks.
        flavor: Force a DDI flavor. DDI XML only.
        dataset_id: Dataset identifier for the codebook flavor.
        dataset_name: Human-readable dataset name for the codebook flavor.
        chunk_size: Records per streamed chunk.

    Returns:
        GraphFrames: The two frames.

    Raises:
        ImportError: If ``pandas`` is not installed.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "The pandas backend needs pandas, which is optional. "
            'Install it with: pip install "ddigraph[pandas]"'
        ) from exc

    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    for chunk in graph_chunks(
        source,
        flavor=flavor,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        chunk_size=chunk_size,
    ):
        nodes.extend(_node_record(node) for node in chunk.nodes)
        relationships.extend(_relationship_record(rel) for rel in chunk.relationships)

    fields = sorted({key for record in nodes for key in record} - {"node_label", "node_id"})
    node_frame = pd.DataFrame(nodes, columns=["node_label", "node_id", *fields])
    relationship_frame = pd.DataFrame(relationships, columns=list(RELATIONSHIP_COLUMNS))

    logger.info(
        "Built pandas DataFrames",
        extra={"nodes": len(node_frame), "relationships": len(relationship_frame)},
    )
    return GraphFrames(nodes=node_frame, relationships=relationship_frame)


__all__ = ["RELATIONSHIP_COLUMNS", "GraphFrames", "to_dataframes"]

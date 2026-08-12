"""Graph write adapter protocol for DDI ingestion.

Defines the interface a graph write adapter implements so the ingestion
pipeline can persist a batch of records and purge a dataset against
its target. The only shipped implementation is
``Neo4jGraphAdapter``; other backends (RDF, Gremlin, NetworkX, pandas)
are not adapter-driven -- they consume the parser tier (``DDILoader``,
``DDIFragmentLoader``, ``DDIFragmentParser``) and write through their
own backend-specific code, as shown in the ``demo/load_*.py`` scripts.
A consumer who wants to plug a new backend into the ingestion pipeline
implements this protocol; otherwise they use the parser tier directly.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ddigraph.schema.ddi_graph import DDIIngestGraph


@runtime_checkable
class GraphWriteAdapter(Protocol):
    """Protocol for graph write adapters.

    Implementations of this protocol handle the actual persistence of DDI data
    to a graph backend. The default implementation is Neo4jGraphAdapter.

    Example:
        >>> class MyAdapter:
        ...     async def write_batch(self, graph, **kwargs):
        ...         for node in graph.nodes():
        ...             my_backend.create_node(node.label, node.properties)
        ...
        ...     async def purge_dataset(self, dataset_id, **kwargs):
        ...         my_backend.delete_dataset(dataset_id)
    """

    def write_batch(
        self,
        graph: DDIIngestGraph,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> Awaitable[None] | None:
        """Write a batch of DDI data to the graph.

        Args:
            graph: The DDIIngestGraph containing nodes and relationships to write.
            session_config: Optional backend-specific session configuration.
            transaction_config: Optional backend-specific transaction configuration.

        Returns:
            None for sync implementations, Awaitable[None] for async.
        """
        ...

    def purge_dataset(
        self,
        dataset_id: str,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> Awaitable[None] | None:
        """Remove all nodes and relationships for a dataset.

        Args:
            dataset_id: The identifier of the dataset to purge.
            session_config: Optional backend-specific session configuration.
            transaction_config: Optional backend-specific transaction configuration.

        Returns:
            None for sync implementations, Awaitable[None] for async.
        """
        ...


__all__ = ["GraphWriteAdapter"]

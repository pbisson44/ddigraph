"""Write a :class:`~ddigraph.graph.view.GraphChunk` stream to Neo4j.

``Neo4jGraphAdapter`` writes a ``DDIIngestGraph``, which only the codebook
parser produces, so a graph coming from anywhere else -- DDI-CDI, or an RDF
file read back by :mod:`ddigraph.rdf.reader` -- had no way into a database.
This writer takes the backend-neutral shape instead, which makes
``ddigraph load survey.ttl`` work and gives DDI-CDI its first write path.

Where the adapter runs 46 hand-written Cypher statements keyed to specific
entity lists, this one groups a chunk by ``(label, identity keys)`` and by
``(start label, type, end label)`` and issues one ``UNWIND`` per group, so it
does not need to know the schema at all.

**Labels and relationship types are interpolated into Cypher, not
parameterised** -- Neo4j does not accept them as parameters. Every one is
therefore checked against :data:`_SAFE_NAME` first. That matters more here
than anywhere else in the package: with an RDF input the labels come from a
file someone else wrote, so without the check a crafted
``ddigraph:Foo) DETACH DELETE n //`` class IRI would run as Cypher.
"""

from __future__ import annotations

import inspect
import re
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from ddigraph.logging import get_logger
from ddigraph.utils.chunking import chunked

if TYPE_CHECKING:
    from neo4j import AsyncDriver, Driver

    from ddigraph.graph.view import GraphChunk
    from ddigraph.schema.ddi_graph import Node, Relationship

logger = get_logger(__name__)

# Neo4j identifiers may be back-tick quoted, but accepting only this shape is
# simpler to reason about than escaping, and every label the package itself
# produces already matches it.
_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UnsafeGraphNameError(ValueError):
    """Raised when a label or relationship type cannot be used in Cypher."""


def _check(name: str, kind: str) -> str:
    """Validate a label or relationship type before interpolating it.

    Args:
        name: The candidate label or relationship type.
        kind: What is being checked, for the error message.

    Returns:
        The name, unchanged.

    Raises:
        UnsafeGraphNameError: If the name is not a plain identifier.
    """
    if not _SAFE_NAME.match(name):
        raise UnsafeGraphNameError(
            f"Refusing to build Cypher with an unsafe {kind}: {name!r}. "
            "Labels and relationship types are interpolated into the query "
            "because Neo4j cannot parameterise them, so only plain "
            "identifiers are accepted."
        )
    return name


def _node_groups(nodes: Iterable[Node]) -> dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]]:
    """Group nodes by label and identity-key shape.

    Nodes sharing a label may still differ in identity shape -- a composite
    key has three -- so the MERGE pattern is keyed on both.
    """
    grouped: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        keys = tuple(sorted(node.identity))
        row = {
            "identity": {key: node.identity[key] for key in keys},
            "properties": {k: v for k, v in node.properties.items() if v is not None},
        }
        grouped[(node.label, keys)].append(row)
    return grouped


def _relationship_groups(
    relationships: Iterable[Relationship],
) -> dict[tuple[str, tuple[str, ...], str, str, tuple[str, ...]], list[dict[str, Any]]]:
    """Group relationships by endpoint labels, identity shapes, and type."""
    grouped: dict[tuple[str, tuple[str, ...], str, str, tuple[str, ...]], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    for rel in relationships:
        start_keys = tuple(sorted(rel.start.identity))
        end_keys = tuple(sorted(rel.end.identity))
        key = (rel.start.label, start_keys, rel.type, rel.end.label, end_keys)
        grouped[key].append(
            {
                "start": {k: rel.start.identity[k] for k in start_keys},
                "end": {k: rel.end.identity[k] for k in end_keys},
            }
        )
    return grouped


def _match_pattern(variable: str, label: str, keys: tuple[str, ...], row_field: str) -> str:
    """Build a ``(v:Label {k: row.field.k, ...})`` pattern."""
    properties = ", ".join(f"{key}: row.{row_field}.{key}" for key in keys)
    return f"({variable}:{_check(label, 'label')} {{{properties}}})"


def node_query(label: str, keys: tuple[str, ...]) -> str:
    """Return the MERGE statement for one node group.

    Args:
        label: The node label.
        keys: The identity property names.

    Returns:
        A Cypher statement expecting an ``$rows`` parameter.
    """
    return (
        f"UNWIND $rows AS row\n"
        f"MERGE {_match_pattern('n', label, keys, 'identity')}\n"
        f"SET n += row.properties"
    )


def relationship_query(
    start_label: str,
    start_keys: tuple[str, ...],
    rel_type: str,
    end_label: str,
    end_keys: tuple[str, ...],
) -> str:
    """Return the MERGE statement for one relationship group.

    Endpoints are matched, not merged: a relationship whose endpoints were
    never written is skipped rather than conjuring an empty node. The reader
    only emits edges between subjects it also described, and the parsers only
    emit edges to fragments they saw, so a miss means something upstream is
    wrong and inventing a node would hide it.

    Args:
        start_label: Label of the start node.
        start_keys: Identity property names on the start node.
        rel_type: The relationship type.
        end_label: Label of the end node.
        end_keys: Identity property names on the end node.

    Returns:
        A Cypher statement expecting an ``$rows`` parameter.
    """
    return (
        f"UNWIND $rows AS row\n"
        f"MATCH {_match_pattern('a', start_label, start_keys, 'start')}\n"
        f"MATCH {_match_pattern('b', end_label, end_keys, 'end')}\n"
        f"MERGE (a)-[:{_check(rel_type, 'relationship type')}]->(b)"
    )


def statements(chunk: GraphChunk) -> list[tuple[str, dict[str, Any]]]:
    """Compile one chunk into ``(cypher, parameters)`` pairs.

    Nodes come first so relationship ``MATCH`` clauses can find them.

    Args:
        chunk: The chunk to compile.

    Returns:
        Statements in execution order.

    Raises:
        UnsafeGraphNameError: If any label or relationship type is not a
            plain identifier.
    """
    compiled: list[tuple[str, dict[str, Any]]] = []
    for (label, keys), rows in _node_groups(chunk.nodes).items():
        compiled.append((node_query(label, keys), {"rows": rows}))
    for (start, start_keys, rel_type, end, end_keys), rows in _relationship_groups(
        chunk.relationships
    ).items():
        compiled.append(
            (relationship_query(start, start_keys, rel_type, end, end_keys), {"rows": rows})
        )
    return compiled


class GraphChunkWriter:
    """Persist a ``GraphChunk`` stream to Neo4j.

    Supports both sync and async drivers, matching ``Neo4jGraphAdapter``:
    the interface is always async and the session type is detected at
    runtime.
    """

    def __init__(
        self,
        driver: Driver | AsyncDriver,
        *,
        database: str | None = None,
        chunk_size: int = 200,
    ) -> None:
        """Initialise the writer.

        Args:
            driver: Neo4j driver used to open sessions.
            database: Database to target.
            chunk_size: Rows per ``UNWIND`` batch.
        """
        self.driver = driver
        self.database = database
        self.chunk_size = chunk_size

    async def write(self, chunks: Iterable[GraphChunk]) -> dict[str, int]:
        """Write every chunk, returning what was persisted.

        Args:
            chunks: Chunks from :func:`ddigraph.graph.view.iter_graph` or
                :func:`ddigraph.rdf.reader.read_graph`.

        Returns:
            Counts of nodes and relationships written.

        Raises:
            UnsafeGraphNameError: If a label or relationship type is unsafe.
        """
        totals = {"nodes": 0, "relationships": 0}

        for chunk in chunks:
            for query, params in statements(chunk):
                rows = cast(list[Any], params["rows"])
                for batch in chunked(rows, self.chunk_size):
                    await self._run(query, {"rows": list(batch)})
            totals["nodes"] += len(chunk.nodes)
            totals["relationships"] += len(chunk.relationships)

        logger.info("Wrote graph chunks", extra=totals)
        return totals

    async def _run(self, query: str, params: dict[str, Any]) -> None:
        """Execute one statement in a write transaction."""

        def _write(tx: Any) -> None:
            tx.run(query, parameters=params).consume()

        async def _write_async(tx: Any) -> None:
            result = tx.run(query, parameters=params)
            if inspect.isawaitable(result):
                result = await result
            consume = result.consume()
            if inspect.isawaitable(consume):
                await consume

        session = self.driver.session(database=self.database)
        if inspect.iscoroutinefunction(session.execute_write):
            async with cast(Any, session) as async_session:
                outcome = async_session.execute_write(_write_async)
                if inspect.isawaitable(outcome):
                    await outcome
        else:
            with cast(Any, session) as sync_session:
                sync_session.execute_write(_write)


__all__ = [
    "GraphChunkWriter",
    "UnsafeGraphNameError",
    "node_query",
    "relationship_query",
    "statements",
]

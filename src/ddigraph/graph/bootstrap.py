"""Neo4j schema bootstrap helpers for DDI ingestion.

This module provides functions to create the necessary constraints and indexes in Neo4j
for DDI data ingestion. It derives all queries from the centralized schema definitions
in :mod:`ddigraph.schema.definitions`.
"""

from __future__ import annotations

import inspect
from typing import Any

from neo4j import AsyncDriver
from neo4j.exceptions import Forbidden

from ddigraph.logging import get_logger
from ddigraph.schema.definitions import DDISchema

logger = get_logger(__name__)


def bootstrap_queries(
    *, include_fragments: bool = False, include_cdi: bool = False
) -> tuple[str, ...]:
    """Compose the ordered schema creation statements.

    Args:
        include_fragments: If True, include DDI-L FragmentInstance constraints
            in addition to DDI Codebook constraints.
        include_cdi: If True, include DDI-CDI 1.0 constraints. Defaults to
            False because no shipped writer creates DDI-CDI nodes; enabling it
            pre-provisions the schema for externally written CDI data.

    Returns:
        tuple[str, ...]: Constraint creation queries followed by index queries
        for the DDI domain graph schema.
    """
    return tuple(
        DDISchema.generate_all_schema_queries(
            include_fragments=include_fragments, include_cdi=include_cdi
        )
    )


def fragment_bootstrap_queries() -> tuple[str, ...]:
    """Compose schema creation statements for DDI-L FragmentInstance only.

    Returns:
        tuple[str, ...]: Constraint and index queries for DDI-L fragment types.
    """
    queries = []
    for node in DDISchema.FRAGMENT_NODES:
        queries.append(
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node.label}) "
            f"REQUIRE n.{node.id_field} IS UNIQUE"
        )
    for node in DDISchema.FRAGMENT_NODES:
        for index_field in node.indexes:
            queries.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{node.label}) ON (n.{index_field})")
    return tuple(queries)


async def ensure_schema(
    driver: AsyncDriver,
    database: str | None = None,
    *,
    include_fragments: bool = False,
    include_cdi: bool = False,
) -> None:
    """Ensure indexes and constraints exist for the DDI domain.

    Args:
        driver: The Neo4j async driver instance used to open sessions.
        database: Optional database name to target when applying the schema.
        include_fragments: If True, include DDI-L FragmentInstance constraints.
        include_cdi: If True, include DDI-CDI 1.0 constraints.

    Raises:
        PermissionError: If the Neo4j user lacks schema privileges.
    """

    async def _run(query: str) -> None:
        logger.info("Executing bootstrap query", extra={"query": query})
        async with driver.session(database=database) as session:

            async def execute(tx: Any) -> None:
                result = tx.run(query)
                if inspect.isawaitable(result):
                    await result

            await session.execute_write(execute)

    queries = bootstrap_queries(include_fragments=include_fragments, include_cdi=include_cdi)
    for query in queries:
        try:
            await _run(query)
        except Forbidden as exc:
            raise PermissionError(
                "Schema bootstrap failed because the Neo4j user lacks permission "
                "to create constraints or indexes. Use a user with the schema "
                "privileges (e.g., `schema_admin` or `admin`), supply the correct "
                "database via DDIGRAPH_NEO4J_DATABASE (or the bare NEO4J_DATABASE "
                "name, which DDIGRAPH_NEO4J_DATABASE overrides), or "
                "pre-provision the schema manually before running ddigraph."
            ) from exc


async def ensure_fragment_schema(
    driver: AsyncDriver,
    database: str | None = None,
) -> None:
    """Ensure indexes and constraints exist for DDI-L FragmentInstance format.

    This is a convenience function that only creates the fragment-specific
    schema, useful when working exclusively with DDI-L files.

    Args:
        driver: The Neo4j async driver instance used to open sessions.
        database: Optional database name to target when applying the schema.

    Raises:
        PermissionError: If the Neo4j user lacks schema privileges.
    """

    async def _run(query: str) -> None:
        logger.info("Executing fragment bootstrap query", extra={"query": query})
        async with driver.session(database=database) as session:

            async def execute(tx: Any) -> None:
                result = tx.run(query)
                if inspect.isawaitable(result):
                    await result

            await session.execute_write(execute)

    for query in fragment_bootstrap_queries():
        try:
            await _run(query)
        except Forbidden as exc:
            raise PermissionError(
                "Schema bootstrap failed because the Neo4j user lacks permission "
                "to create constraints or indexes. Use a user with the schema "
                "privileges (e.g., `schema_admin` or `admin`), supply the correct "
                "database via DDIGRAPH_NEO4J_DATABASE (or the bare NEO4J_DATABASE "
                "name, which DDIGRAPH_NEO4J_DATABASE overrides), or "
                "pre-provision the schema manually before running ddigraph."
            ) from exc


# Backwards compatibility: generate queries from schema definitions
CONSTRAINT_QUERIES = DDISchema.generate_constraint_queries(
    include_fragments=False, include_cdi=False
)

INDEX_QUERIES = [
    f"CREATE INDEX IF NOT EXISTS FOR (n:{node.label}) ON (n.{index_field})"
    for node in DDISchema.CODEBOOK_NODES
    for index_field in node.indexes
]


__all__ = [
    "CONSTRAINT_QUERIES",
    "INDEX_QUERIES",
    "bootstrap_queries",
    "ensure_fragment_schema",
    "ensure_schema",
    "fragment_bootstrap_queries",
]

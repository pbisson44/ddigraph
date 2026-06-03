"""Graph bootstrap and schema management."""

from ddigraph.graph.bootstrap import (
    CONSTRAINT_QUERIES,
    INDEX_QUERIES,
    bootstrap_queries,
    ensure_fragment_schema,
    ensure_schema,
    fragment_bootstrap_queries,
)

__all__ = [
    "CONSTRAINT_QUERIES",
    "INDEX_QUERIES",
    "bootstrap_queries",
    "ensure_fragment_schema",
    "ensure_schema",
    "fragment_bootstrap_queries",
]

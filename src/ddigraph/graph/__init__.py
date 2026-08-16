"""Graph bootstrap, schema management, and the backend-neutral graph view."""

from ddigraph.graph.bootstrap import (
    CONSTRAINT_QUERIES,
    INDEX_QUERIES,
    bootstrap_queries,
    ensure_fragment_schema,
    ensure_schema,
    fragment_bootstrap_queries,
)
from ddigraph.graph.view import GraphChunk, iter_graph

__all__ = [
    "CONSTRAINT_QUERIES",
    "INDEX_QUERIES",
    "GraphChunk",
    "bootstrap_queries",
    "ensure_fragment_schema",
    "ensure_schema",
    "fragment_bootstrap_queries",
    "iter_graph",
]

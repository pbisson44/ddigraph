"""Tests for the GraphChunk -> Neo4j writer.

``Neo4jGraphAdapter`` writes a ``DDIIngestGraph``, which only the codebook
parser produces, so DDI-CDI and RDF input had no way into a database. These
tests exercise the generic writer against a recording fake driver, the same
approach ``tests/test_neo4j_adapter.py`` uses -- no Neo4j server is involved
anywhere in this suite.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from ddigraph.graph.view import GraphChunk, iter_graph
from ddigraph.graph.writer import (
    GraphChunkWriter,
    UnsafeGraphNameError,
    node_query,
    relationship_query,
    statements,
)
from ddigraph.schema.ddi_graph import Node, Relationship

FIXTURES = Path(__file__).parent / "fixtures"


class FakeSession:
    """Records every statement executed through it."""

    def __init__(self, log: list[tuple[str, dict[str, Any]]]) -> None:
        self.log = log

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute_write(self, fn: Any, **_kw: object) -> None:
        fn(self)

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeSession:
        self.log.append((query, parameters or {}))
        return self

    def consume(self) -> None:
        return None


class FakeDriver:
    """Sync driver whose sessions record statements."""

    def __init__(self) -> None:
        self.log: list[tuple[str, dict[str, Any]]] = []

    def session(self, **_kw: object) -> FakeSession:
        return FakeSession(self.log)


def _write(chunks: Any) -> FakeDriver:
    driver = FakeDriver()
    asyncio.run(GraphChunkWriter(driver).write(chunks))  # type: ignore[arg-type]
    return driver


# ---------------------------------------------------------------------------
# Cypher generation
# ---------------------------------------------------------------------------


def test_node_query_merges_on_identity_and_sets_properties() -> None:
    """Identity goes in the MERGE pattern; everything else is a SET."""
    query = node_query("Variable", ("variable_id",))

    assert "MERGE (n:Variable {variable_id: row.identity.variable_id})" in query
    assert "SET n += row.properties" in query


def test_composite_identity_merges_on_every_key() -> None:
    """``DDIGenericIdentifiable`` is keyed on three fields together.

    Merging on one of them would collapse every sibling node onto a single
    graph node, which is the same failure the RDF writer had.
    """
    query = node_query("DDIGenericIdentifiable", ("dataset_id", "element_tag", "identifiable_id"))

    for key in ("dataset_id", "element_tag", "identifiable_id"):
        assert f"{key}: row.identity.{key}" in query


def test_relationship_query_matches_endpoints_rather_than_merging() -> None:
    """A missing endpoint should surface, not be conjured into existence."""
    query = relationship_query(
        "CodeList", ("fragment_id",), "HAS_CATEGORY", "Category", ("fragment_id",)
    )

    assert query.count("MATCH") == 2
    assert "MERGE (a)-[:HAS_CATEGORY]->(b)" in query


def test_node_query_is_exactly_this_cypher() -> None:
    """Pin the whole statement, not fragments of it.

    Asserting only that a substring appears lets a mutation change the
    variable, the row field or the clause order and go unnoticed. Mutation
    testing surfaced exactly that: swapping the match variable to ``None``
    survived every assertion in this file.
    """
    assert node_query("Variable", ("variable_id",)) == (
        "UNWIND $rows AS row\n"
        "MERGE (n:Variable {variable_id: row.identity.variable_id})\n"
        "SET n += row.properties"
    )


def test_relationship_query_is_exactly_this_cypher() -> None:
    """Same, for the two-endpoint statement."""
    assert relationship_query(
        "CodeList", ("fragment_id",), "HAS_CATEGORY", "Category", ("fragment_id",)
    ) == (
        "UNWIND $rows AS row\n"
        "MATCH (a:CodeList {fragment_id: row.start.fragment_id})\n"
        "MATCH (b:Category {fragment_id: row.end.fragment_id})\n"
        "MERGE (a)-[:HAS_CATEGORY]->(b)"
    )


def test_node_rows_carry_identity_and_properties() -> None:
    """The parameters matter as much as the query text.

    Nothing checked the row payload, so replacing the whole dict with
    ``None`` survived: the Cypher was right and the data was gone.
    """
    chunk = GraphChunk(
        [Node("Variable", {"variable_id": "v1"}, {"label": "Age", "urn": None})],
        [],
    )

    (_query, params) = statements(chunk)[0]

    assert params == {"rows": [{"identity": {"variable_id": "v1"}, "properties": {"label": "Age"}}]}


def test_relationship_rows_carry_both_endpoint_identities() -> None:
    """A dropped endpoint would make MATCH silently find nothing."""
    chunk = GraphChunk(
        [],
        [
            Relationship(
                "IN_DATASET",
                Node("Variable", {"variable_id": "v1"}, {}),
                Node("Dataset", {"id": "d1"}, {}),
            )
        ],
    )

    (_query, params) = statements(chunk)[0]

    assert params == {"rows": [{"start": {"variable_id": "v1"}, "end": {"id": "d1"}}]}


def test_none_valued_properties_are_dropped() -> None:
    """``SET n += row.properties`` would otherwise null out real values."""
    chunk = GraphChunk([Node("Variable", {"variable_id": "v1"}, {"urn": None})], [])

    (_query, params) = statements(chunk)[0]

    assert params["rows"][0]["properties"] == {}


def test_nodes_are_written_before_relationships() -> None:
    """Relationship MATCH clauses depend on the nodes already existing."""
    chunk = GraphChunk(
        [Node("Variable", {"variable_id": "v1"}, {})],
        [
            Relationship(
                "IN_DATASET",
                Node("Variable", {"variable_id": "v1"}, {}),
                Node("Dataset", {"id": "d1"}, {}),
            )
        ],
    )

    compiled = [query for query, _params in statements(chunk)]

    assert compiled[0].startswith("UNWIND $rows AS row\nMERGE")
    assert "MATCH" in compiled[-1]


# ---------------------------------------------------------------------------
# Cypher injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [
        "Foo) DETACH DELETE n //",
        "Foo`",
        "Foo Bar",
        "123Foo",
        "",
    ],
)
def test_unsafe_labels_are_refused(label: str) -> None:
    """Labels are interpolated into Cypher because Neo4j cannot bind them.

    With RDF input the labels come from a file someone else wrote, so an
    unchecked class IRI would execute as Cypher.
    """
    with pytest.raises(UnsafeGraphNameError, match="unsafe label"):
        node_query(label, ("id",))


def test_unsafe_relationship_types_are_refused() -> None:
    """Same exposure through the relationship type."""
    with pytest.raises(UnsafeGraphNameError, match="unsafe relationship type"):
        relationship_query("A", ("id",), "T]->() DETACH DELETE n //", "B", ("id",))


def test_every_label_the_package_produces_is_safe() -> None:
    """The guard must not reject legitimate schema labels."""
    from ddigraph.schema.definitions import DDISchema

    for node in DDISchema.get_all_nodes():
        node_query(node.label, ("id",))


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    ["codebook_sample.xml", "fragment_instance.xml", "cdi_sample.xml"],
)
def test_every_flavor_reaches_the_database(fixture: str) -> None:
    """DDI-CDI included, which had no write path at all before."""
    driver = _write(iter_graph(FIXTURES / fixture))

    assert driver.log
    assert any("MERGE (n:" in query for query, _p in driver.log)


def test_cdi_relationships_are_written() -> None:
    """CDI edges reach Cypher, not just CDI nodes."""
    driver = _write(iter_graph(FIXTURES / "cdi_sample.xml"))

    merges = [q for q, _p in driver.log if "MERGE (a)-[:" in q]

    assert any("HAS_CONCEPT" in q for q in merges)


def test_rows_are_batched_by_chunk_size() -> None:
    """Large groups are split so a single UNWIND stays bounded."""
    nodes = [Node("Variable", {"variable_id": f"v{i}"}, {}) for i in range(25)]
    driver = FakeDriver()

    asyncio.run(
        GraphChunkWriter(driver, chunk_size=10).write([GraphChunk(nodes, [])])  # type: ignore[arg-type]
    )

    sizes = [len(params["rows"]) for _q, params in driver.log]

    assert sizes == [10, 10, 5]


def test_write_reports_what_it_wrote() -> None:
    """Counts come back for the CLI summary."""
    driver = FakeDriver()

    totals = asyncio.run(
        GraphChunkWriter(driver).write(iter_graph(FIXTURES / "cdi_sample.xml"))  # type: ignore[arg-type]
    )

    assert totals == {"nodes": 8, "relationships": 3}


# ---------------------------------------------------------------------------
# The promise: RDF in, database out
# ---------------------------------------------------------------------------


def test_rdf_file_loads_end_to_end(tmp_path: Path) -> None:
    """``ddigraph load survey.ttl`` -- the loop the release set out to close.

    The endpoint identities matter here: the reader must give an edge the
    same identity the node carries, or every MATCH finds nothing and the
    edges vanish without an error.
    """
    pytest.importorskip("rdflib")
    from ddigraph.exporter import export
    from ddigraph.rdf.reader import read_graph

    out = tmp_path / "graph.ttl"
    export(FIXTURES / "fragment_instance.xml", out, format="turtle")

    driver = _write(read_graph(out))
    edges = [(q, p) for q, p in driver.log if "MERGE (a)-[:" in q]

    assert edges
    for query, params in edges:
        for row in params["rows"]:
            assert row["start"], f"empty start identity in {query}"
            assert row["end"], f"empty end identity in {query}"


def test_loaded_rdf_matches_the_xml_it_came_from(tmp_path: Path) -> None:
    """Loading the RDF must write the same graph as loading the XML."""
    pytest.importorskip("rdflib")
    from ddigraph.exporter import export
    from ddigraph.rdf.reader import read_graph

    source = FIXTURES / "fragment_instance.xml"
    out = tmp_path / "graph.ttl"
    export(source, out, format="turtle")

    from_xml = asyncio.run(GraphChunkWriter(FakeDriver()).write(iter_graph(source)))  # type: ignore[arg-type]
    from_rdf = asyncio.run(GraphChunkWriter(FakeDriver()).write(read_graph(out)))  # type: ignore[arg-type]

    assert from_xml == from_rdf

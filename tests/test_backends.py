"""Tests for the shipped backend adapters (``ddigraph.backends``).

Until 0.5.1 NetworkX, pandas and Gremlin were reachable only through
``demo/load_*.py`` scripts outside the package. These tests hold the
adapters to the graph view they consume: every node and relationship
arrives, nothing collapses, and composite identities stay distinct.

The Gremlin tests need no server. A recording connection captures the
bytecode each request would send, which is what the adapter actually
controls; what a given provider does with it is the provider's business.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ddigraph import export
from ddigraph.backends import flatten, graph_chunks
from ddigraph.graph.view import GraphChunk, iter_graph, node_key
from ddigraph.schema.ddi_graph import Node

FIXTURES = Path(__file__).parent / "fixtures"
CODEBOOK = FIXTURES / "codebook_sample.xml"
LIFECYCLE = FIXTURES / "fragment_instance.xml"
CDI = FIXTURES / "cdi_sample.xml"
ALL = [CODEBOOK, LIFECYCLE, CDI]


def _drain(path: Path) -> GraphChunk:
    merged = GraphChunk()
    for chunk in iter_graph(path):
        merged.nodes.extend(chunk.nodes)
        merged.relationships.extend(chunk.relationships)
    return merged


def _distinct_nodes(graph: GraphChunk) -> set[tuple[str, str]]:
    return {(node.label, node_key(node)) for node in graph.nodes}


# ---------------------------------------------------------------------------
# Shared input
# ---------------------------------------------------------------------------


def test_graph_chunks_passes_existing_chunks_through() -> None:
    chunks = list(iter_graph(LIFECYCLE))

    assert list(graph_chunks(chunks)) == chunks


def test_graph_chunks_reads_rdf_by_extension(tmp_path: Path) -> None:
    pytest.importorskip("rdflib")
    turtle = tmp_path / "survey.ttl"
    export(LIFECYCLE, turtle, format="turtle")

    from_rdf = {(n.label, node_key(n)) for c in graph_chunks(turtle) for n in c.nodes}

    assert from_rdf == _distinct_nodes(_drain(LIFECYCLE))


def test_flatten_joins_lists_only() -> None:
    assert flatten(["a", "b"]) == "a|b"
    assert flatten("a") == "a"
    assert flatten(3) == 3


def test_node_key_ignores_identity_order() -> None:
    """Equal identities must key equally, however the dict was built.

    An edge's endpoint stub and its node can build the same composite
    identity in different orders; keyed by insertion order, they would no
    longer match.
    """
    forward = Node(label="X", identity={"a": 1, "b": 2}, properties={})
    backward = Node(label="X", identity={"b": 2, "a": 1}, properties={})

    assert node_key(forward) == node_key(backward) == "1|2"


def test_backend_modules_import_without_their_libraries() -> None:
    """The extras are lazy: importing a backend must not need its library."""
    import importlib
    import sys

    for name in ("networkx", "pandas", "gremlin"):
        module = importlib.import_module(f"ddigraph.backends.{name}")
        assert module.__name__ in sys.modules


# ---------------------------------------------------------------------------
# NetworkX
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", ALL, ids=lambda p: p.stem)
def test_networkx_keeps_every_node_and_edge(fixture: Path) -> None:
    pytest.importorskip("networkx")
    from ddigraph.backends.networkx import to_networkx

    expected = _drain(fixture)
    graph = to_networkx(fixture)

    assert graph.number_of_nodes() == len(_distinct_nodes(expected))
    distinct_edges = {
        (r.start.label, node_key(r.start), r.type, r.end.label, node_key(r.end))
        for r in expected.relationships
    }
    assert graph.number_of_edges() == len(distinct_edges)


def test_networkx_keeps_composite_identities_apart() -> None:
    """All fourteen ``DDIGenericIdentifiable`` nodes share a dataset_id."""
    pytest.importorskip("networkx")
    from ddigraph.backends.networkx import to_networkx

    graph = to_networkx(CODEBOOK)
    generic = [n for n, d in graph.nodes(data=True) if d["node_type"] == "DDIGenericIdentifiable"]

    assert len(generic) == 14


def test_networkx_node_type_does_not_collide_with_the_label_property() -> None:
    pytest.importorskip("networkx")
    from ddigraph.backends.networkx import node_id, to_networkx

    graph = to_networkx(LIFECYCLE)
    instrument = next(n for n in _drain(LIFECYCLE).nodes if n.label == "Instrument")
    data = graph.nodes[node_id(instrument)]

    assert data["node_type"] == "Instrument"
    assert data["label"] == instrument.properties["label"]
    assert None not in data.values()


def test_networkx_reloading_does_not_duplicate() -> None:
    pytest.importorskip("networkx")
    from ddigraph.backends.networkx import to_networkx

    once = to_networkx(LIFECYCLE)
    twice = to_networkx(LIFECYCLE, graph=to_networkx(LIFECYCLE))

    assert twice.number_of_nodes() == once.number_of_nodes()
    assert twice.number_of_edges() == once.number_of_edges()


def test_networkx_flattened_graph_writes_graphml(tmp_path: Path) -> None:
    """GraphML rejects lists; ``flatten_lists`` is what makes it writable."""
    nx = pytest.importorskip("networkx")
    from ddigraph.backends.networkx import to_networkx

    graph = to_networkx(CODEBOOK, flatten_lists=True)
    out = tmp_path / "graph.graphml"
    nx.write_graphml(graph, out)

    assert nx.read_graphml(out).number_of_nodes() == graph.number_of_nodes()


def test_networkx_edges_are_keyed_by_type() -> None:
    pytest.importorskip("networkx")
    from ddigraph.backends.networkx import to_networkx

    graph = to_networkx(LIFECYCLE)

    for _start, _end, key, data in graph.edges(keys=True, data=True):
        assert key == data["relationship"]


# ---------------------------------------------------------------------------
# pandas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", ALL, ids=lambda p: p.stem)
def test_pandas_frames_match_the_graph(fixture: Path) -> None:
    pytest.importorskip("pandas")
    from ddigraph.backends.pandas import RELATIONSHIP_COLUMNS, to_dataframes

    expected = _drain(fixture)
    frames = to_dataframes(fixture)

    assert len(frames.nodes) == len(expected.nodes)
    assert len(frames.relationships) == len(expected.relationships)
    assert list(frames.nodes.columns[:2]) == ["node_label", "node_id"]
    assert tuple(frames.relationships.columns) == RELATIONSHIP_COLUMNS


@pytest.mark.parametrize("fixture", ALL, ids=lambda p: p.stem)
def test_pandas_relationships_join_to_nodes(fixture: Path) -> None:
    pytest.importorskip("pandas")
    from ddigraph.backends.pandas import to_dataframes

    frames = to_dataframes(fixture)
    joined = frames.relationships.merge(
        frames.nodes[["node_label", "node_id"]],
        left_on=["start_label", "start_id"],
        right_on=["node_label", "node_id"],
        how="left",
        indicator=True,
    )

    assert (joined["_merge"] == "both").all()


def test_pandas_of_keeps_only_the_columns_a_type_uses() -> None:
    pytest.importorskip("pandas")
    from ddigraph.backends.pandas import to_dataframes

    frames = to_dataframes(CODEBOOK)
    variables = frames.of("Variable")

    assert len(variables) == (frames.nodes["node_label"] == "Variable").sum()
    assert len(variables.columns) < len(frames.nodes.columns)
    assert not variables.isna().all().any()


# ---------------------------------------------------------------------------
# Gremlin
# ---------------------------------------------------------------------------


class _Recording:
    """A remote connection that records bytecode instead of sending it.

    ``answer`` decides how many results a request returns, which is how an
    upsert that found no endpoint looks from the client side.
    """

    def __init__(self, answer: Callable[[Any], int] | None = None) -> None:
        self.requests: list[Any] = []
        self.answer = answer or _branches

    def submit(self, bytecode: Any) -> Any:
        from gremlin_python.driver.remote_connection import RemoteTraversal
        from gremlin_python.process.traversal import Traverser

        self.requests.append(bytecode)
        return RemoteTraversal(iter([Traverser(1, 1)] * self.answer(bytecode)))


def _branches(bytecode: Any) -> int:
    """How many upserts one request carries: the arguments of its ``union``."""
    union = next(step for step in bytecode.step_instructions if step[0] == "union")
    return len(union) - 1


def _source(connection: _Recording) -> Any:
    from gremlin_python.driver.remote_connection import RemoteStrategy
    from gremlin_python.process.graph_traversal import GraphTraversalSource
    from gremlin_python.process.traversal import TraversalStrategies
    from gremlin_python.structure.graph import Graph

    strategies = TraversalStrategies()
    strategies.add_strategies([RemoteStrategy(connection)])
    return GraphTraversalSource(Graph(), strategies)


def _steps(bytecode: Any) -> list[Any]:
    """Every step in a request, branches included, flattened."""
    from gremlin_python.process.traversal import Bytecode

    found: list[Any] = []
    for step in bytecode.step_instructions:
        found.append(step)
        for arg in step[1:]:
            if isinstance(arg, Bytecode):
                found.extend(_steps(arg))
    return found


def test_gremlin_writes_every_node_and_edge_in_batches() -> None:
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import write_gremlin

    expected = _drain(CODEBOOK)
    connection = _Recording()
    result = write_gremlin(_source(connection), CODEBOOK, batch_size=10)

    assert result.nodes == len(expected.nodes)
    assert result.relationships == len(expected.relationships)
    assert result.skipped == 0
    expected_requests = -(-len(expected.nodes) // 10) + -(-len(expected.relationships) // 10)
    assert len(connection.requests) == expected_requests


def test_gremlin_writes_vertices_before_any_edge() -> None:
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import write_gremlin

    connection = _Recording()
    write_gremlin(_source(connection), CODEBOOK, batch_size=10)

    kinds = [
        "addE" if any(s[0] == "addE" for s in _steps(r)) else "addV" for r in connection.requests
    ]
    assert kinds == sorted(kinds, key=lambda kind: kind == "addE")


def test_gremlin_upserts_on_label_and_node_key() -> None:
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import KEY_PROPERTY, write_gremlin

    connection = _Recording()
    write_gremlin(_source(connection), LIFECYCLE, batch_size=1000)

    steps = _steps(connection.requests[0])
    instrument = next(n for n in _drain(LIFECYCLE).nodes if n.label == "Instrument")
    assert ["has", "Instrument", KEY_PROPERTY, node_key(instrument)] in steps
    assert any(step[0] == "coalesce" for step in steps), "a plain addV would duplicate on reload"


def test_gremlin_renames_reserved_property_names() -> None:
    """``label`` and ``id`` are element accessors to some providers."""
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import write_gremlin

    connection = _Recording()
    write_gremlin(_source(connection), LIFECYCLE, batch_size=1000)

    keys = {
        step[2] if len(step) == 4 else step[1]
        for step in _steps(connection.requests[0])
        if step[0] == "property"
    }
    assert "ddi_label" in keys
    assert "label" not in keys and "id" not in keys


@pytest.mark.parametrize(("cardinality", "arity"), [("single", 4), (None, 3)])
def test_gremlin_cardinality_is_configurable(cardinality: str | None, arity: int) -> None:
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import KEY_PROPERTY, write_gremlin

    connection = _Recording()
    write_gremlin(_source(connection), LIFECYCLE, batch_size=1000, cardinality=cardinality)

    properties = [
        step
        for step in _steps(connection.requests[0])
        if step[0] == "property" and KEY_PROPERTY not in step
    ]
    assert properties
    assert {len(step) for step in properties} == {arity}


def test_gremlin_counts_edges_it_could_not_write() -> None:
    """An edge whose endpoint is missing emits nothing; it must not vanish silently."""
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import write_gremlin

    def lose_one_edge(bytecode: Any) -> int:
        branches = _branches(bytecode)
        is_edges = any(step[0] == "addE" for step in _steps(bytecode))
        return branches - 1 if is_edges else branches

    expected = _drain(LIFECYCLE)
    result = write_gremlin(_source(_Recording(lose_one_edge)), LIFECYCLE, batch_size=1000)

    assert result.skipped == 1
    assert result.relationships == len(expected.relationships) - 1


def test_gremlin_flattens_lists() -> None:
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import write_gremlin

    node = Node(label="Variable", identity={"id": "v1"}, properties={"tags": ["a", "b"]})
    connection = _Recording()
    write_gremlin(_source(connection), [GraphChunk(nodes=[node])])

    assert ["property", _single(), "tags", "a|b"] in _steps(connection.requests[0])


def _single() -> Any:
    from gremlin_python.process.traversal import Cardinality

    return Cardinality.single


def test_gremlin_rejects_a_non_positive_batch_size() -> None:
    pytest.importorskip("gremlin_python")
    from ddigraph.backends.gremlin import write_gremlin

    with pytest.raises(ValueError, match="batch_size"):
        write_gremlin(_source(_Recording()), [], batch_size=0)

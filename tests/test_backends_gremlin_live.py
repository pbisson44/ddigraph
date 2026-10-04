"""Run the Gremlin adapter against a real server, when one is available.

``tests/test_backends.py`` checks the bytecode the adapter sends. This checks
what a server does with it -- above all that the upserts are idempotent and
that each edge lands between the right two vertices. Set ``GREMLIN_URL`` to
run it, for instance against the official image::

    docker run --rm -p 8182:8182 tinkerpop/gremlin-server:3.8.2
    GREMLIN_URL=ws://localhost:8182/gremlin pytest tests/test_backends_gremlin_live.py

It clears the server's graph, so never point it at one that holds data.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

URL = os.environ.get("GREMLIN_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set GREMLIN_URL to run against a live server")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def g() -> Iterator[Any]:
    pytest.importorskip("gremlin_python")
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from gremlin_python.process.anonymous_traversal import traversal

    connection = DriverRemoteConnection(URL, "g")
    source = traversal().with_(connection)
    source.V().drop().iterate()
    try:
        yield source
    finally:
        source.V().drop().iterate()
        connection.close()


@pytest.mark.parametrize("fixture", ["codebook_sample", "fragment_instance", "cdi_sample"])
def test_a_fixture_loads_completely_and_idempotently(g: Any, fixture: str) -> None:
    from ddigraph.backends.gremlin import write_gremlin
    from ddigraph.graph.view import iter_graph, node_key

    path = FIXTURES / f"{fixture}.xml"
    nodes = {(n.label, node_key(n)) for c in iter_graph(path) for n in c.nodes}
    edges = {
        (r.start.label, node_key(r.start), r.type, r.end.label, node_key(r.end))
        for c in iter_graph(path)
        for r in c.relationships
    }

    first = write_gremlin(g, path, batch_size=7)
    assert first.skipped == 0
    assert g.V().count().next() == len(nodes)
    assert g.E().count().next() == len(edges)

    write_gremlin(g, path, batch_size=7)
    assert g.V().count().next() == len(nodes), "reloading must not duplicate vertices"
    assert g.E().count().next() == len(edges), "reloading must not duplicate edges"


def test_edges_join_the_right_vertices(g: Any) -> None:
    from gremlin_python.process.graph_traversal import __

    from ddigraph.backends.gremlin import KEY_PROPERTY, write_gremlin
    from ddigraph.graph.view import iter_graph, node_key

    path = FIXTURES / "fragment_instance.xml"
    write_gremlin(g, path)

    for chunk in iter_graph(path):
        for rel in chunk.relationships:
            found = (
                g.V()
                .has(rel.start.label, KEY_PROPERTY, node_key(rel.start))
                .out_e(rel.type)
                .in_v()
                .has(rel.end.label, KEY_PROPERTY, node_key(rel.end))
                .count()
                .next()
            )
            assert found == 1, rel
    assert g.V().has("ddi_label").count().next() > 0
    assert g.V().where(__.properties("label")).count().next() == 0

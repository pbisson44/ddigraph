"""Tests for ``ddigraph preview``.

Preview answers "what is actually in this file?" without a database, which
until now meant opening Neo4j Browser and writing Cypher. It aggregates to
node-type and relationship-shape counts rather than drawing every node,
because the demo corpus reaches tens of thousands of them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ddigraph.graph.view import GraphChunk, iter_graph
from ddigraph.previewer import (
    FORMATS,
    preview,
    summarise,
    to_html,
    to_mermaid,
    to_text,
)
from ddigraph.schema.ddi_graph import Node, Relationship

FIXTURES = Path(__file__).parent / "fixtures"
LIFECYCLE = FIXTURES / "fragment_instance.xml"
CODEBOOK = FIXTURES / "codebook_sample.xml"
CDI = FIXTURES / "cdi_sample.xml"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI], ids=lambda p: p.stem)
def test_totals_match_the_graph(fixture: Path) -> None:
    """The summary must agree with what the view actually yielded."""
    chunks = list(iter_graph(fixture))
    summary = summarise(chunks)

    assert summary.nodes == sum(len(c.nodes) for c in chunks)
    assert summary.relationships == sum(len(c.relationships) for c in chunks)
    assert sum(summary.nodes_by_label.values()) == summary.nodes
    assert sum(summary.edges_by_shape.values()) == summary.relationships


def test_edges_are_grouped_by_shape_not_instance() -> None:
    """Aggregating is the whole point: 65 MB must not become 65 MB of boxes."""
    summary = summarise(
        [
            GraphChunk(
                [],
                [
                    Relationship(
                        "USES_CODELIST",
                        Node("QuestionItem", {"fragment_id": f"q{i}"}, {}),
                        Node("CodeList", {"fragment_id": "cl1"}, {}),
                    )
                    for i in range(500)
                ],
            )
        ]
    )

    assert summary.relationships == 500
    assert summary.edges_by_shape == {("QuestionItem", "USES_CODELIST", "CodeList"): 500}


def test_samples_are_off_by_default() -> None:
    """Keeping examples is what would make memory grow with the file."""
    assert summarise(iter_graph(CODEBOOK)).samples == {}


def test_samples_are_capped_per_label() -> None:
    """``--limit`` bounds the examples kept, per type."""
    summary = summarise(iter_graph(CODEBOOK), limit=2)

    assert summary.samples
    assert all(len(nodes) <= 2 for nodes in summary.samples.values())


def test_samples_are_rendered_with_their_identities() -> None:
    """Counts say how many. ``--limit`` is how you check they are the right ones."""
    rendered = to_text(summarise(iter_graph(CODEBOOK), limit=2))

    assert "Sample Variable" in rendered
    assert "variable_id=v1" in rendered


def test_a_label_with_no_kept_samples_prints_no_heading() -> None:
    """An empty list would otherwise leave a ``Sample X`` heading over nothing."""
    summary = summarise([GraphChunk([Node("Study", {"study_id": "s1"}, {})], [])], limit=1)
    summary.samples["Ghost"] = []

    assert "Sample Ghost" not in to_text(summary)


def test_ordering_is_deterministic() -> None:
    """Same input, same bytes -- otherwise the output is not diffable."""
    first = to_text(summarise(iter_graph(CODEBOOK)))
    second = to_text(summarise(iter_graph(CODEBOOK)))

    assert first == second


def test_labels_are_ordered_by_count_then_name() -> None:
    """Most common first; ties broken by name so ordering is stable."""
    summary = summarise(
        [
            GraphChunk(
                [
                    Node("B", {"id": "1"}, {}),
                    Node("A", {"id": "2"}, {}),
                    Node("A", {"id": "3"}, {}),
                ],
                [],
            )
        ]
    )

    assert to_text(summary).index("A") < to_text(summary).index("B")


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def test_text_names_every_type_and_relationship() -> None:
    """The terminal output is the default, so it has to carry the content."""
    rendered = to_text(summarise(iter_graph(LIFECYCLE)), source="survey.xml")

    assert "survey.xml" in rendered
    assert "QuestionItem" in rendered
    assert "(QuestionItem)-[:USES_CODELIST]->(CodeList)" in rendered


def test_mermaid_declares_every_node_type() -> None:
    """A type with no edges is often the interesting one; keep it drawn."""
    summary = summarise(iter_graph(CDI))
    rendered = to_mermaid(summary)

    assert rendered.startswith("graph LR")
    for label in summary.nodes_by_label:
        assert f'{label}["{label}<br/>' in rendered


def test_mermaid_ids_are_safe() -> None:
    """Labels come from the input; a Mermaid id must stay an identifier."""
    summary = summarise([GraphChunk([Node("Odd Label-1", {"id": "x"}, {})], [])])

    rendered = to_mermaid(summary)

    assert "Odd_Label_1[" in rendered
    assert "Odd Label-1[" not in rendered


def test_html_is_self_contained() -> None:
    """No CDN, no external stylesheet, no script: it must work offline."""
    rendered = to_html(summarise(iter_graph(CODEBOOK)), title="survey.xml")

    assert "<script" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered
    assert "<svg" in rendered


def test_html_escapes_data_derived_text() -> None:
    """Labels are data. Unescaped, they would be markup."""
    summary = summarise([GraphChunk([Node("<img src=x>", {"id": "1"}, {})], [])])

    rendered = to_html(summary)

    assert "<img src=x>" not in rendered
    assert "&lt;img src=x&gt;" in rendered


def test_html_bar_chart_scales_to_the_largest_count() -> None:
    """A bar chart where every bar is full width says nothing."""
    summary = summarise(
        [
            GraphChunk(
                [Node("Big", {"id": str(i)}, {}) for i in range(10)]
                + [Node("Small", {"id": "s"}, {})],
                [],
            )
        ]
    )

    rendered = to_html(summary)
    widths = [int(part.split('"')[0]) for part in rendered.split('width="')[2:]]

    assert max(widths) > min(widths)


def test_empty_graph_renders_without_crashing() -> None:
    """A file that parses to nothing should say so, not raise."""
    empty = summarise([])

    assert "Nodes: 0" in to_text(empty)
    assert to_mermaid(empty).strip() == "graph LR"
    assert "No nodes." in to_html(empty)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI], ids=lambda p: p.stem)
def test_every_format_works_for_every_flavor(fmt: str, fixture: Path) -> None:
    """One previewer, three DDI flavors -- the point of the graph view."""
    assert preview(fixture, format=fmt).strip()


def test_unknown_format_is_rejected() -> None:
    """Fail on the argument, not part way through rendering."""
    with pytest.raises(ValueError, match="Unknown preview format"):
        preview(LIFECYCLE, format="pdf")


def test_preview_needs_no_optional_extra() -> None:
    """Pure string work: no rdflib, no networkx, nothing to install."""
    import ast

    source = (Path(__file__).parent.parent / "src" / "ddigraph" / "previewer.py").read_text(
        encoding="utf-8"
    )
    roots = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
    }

    assert not roots & {"rdflib", "pyshacl", "networkx", "pandas", "neo4j"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_preview_command_prints_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """The default is the terminal you already have open."""
    from ddigraph import cli

    cli.main(["preview", str(CDI)])

    assert "CDIConcept" in capsys.readouterr().out


def test_preview_command_writes_a_file(tmp_path: Path) -> None:
    """``-o`` is how the HTML page gets somewhere a browser can open it."""
    from ddigraph import cli

    out = tmp_path / "preview.html"
    cli.main(["preview", str(CODEBOOK), "--format", "html", "-o", str(out)])

    assert "<svg" in out.read_text(encoding="utf-8")


def test_preview_command_takes_no_connection_options() -> None:
    """It never opens a database, so it must not appear to."""
    from ddigraph import cli

    parser = cli.build_parser()
    args = parser.parse_args(["preview", str(CDI)])

    assert args.format == "text"
    assert not hasattr(args, "neo4j_uri")

"""Summarise a DDI file's graph shape without loading a database.

Until now the only way to see what a load produced was to open Neo4j
Browser and start writing Cypher. ``ddigraph load`` reports
``nodes=1247, relationships=3891`` and nothing about what any of them are.

This previews the *shape*, not the instances. The demo corpus runs to 65 MB
and tens of thousands of nodes; a node-per-box diagram of that is unusable.
Aggregating to label counts and ``label -[TYPE]-> label`` edge counts turns
it into roughly twenty boxes, which is a thing a person can read.

Three renderers, all pure string work with no dependencies:

* ``text`` -- the default, for the terminal you already have open.
* ``mermaid`` -- paste into the docs, a GitHub comment, or any Mermaid
  viewer. The documentation already renders Mermaid.
* ``html`` -- one self-contained file. No CDN, no external stylesheet, no
  JavaScript, so it works offline and survives being emailed.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ddigraph.graph.view import iter_graph
from ddigraph.logging import get_logger

if TYPE_CHECKING:
    from ddigraph.graph.view import GraphChunk
    from ddigraph.schema.ddi_graph import Node

logger = get_logger(__name__)

#: Renderers ``ddigraph preview`` accepts.
FORMATS: tuple[str, ...] = ("text", "mermaid", "html")

# Mermaid node ids must be bare identifiers. Labels already match this
# shape, but the input may come from an RDF file someone else wrote.
_UNSAFE_ID = re.compile(r"[^A-Za-z0-9_]")


@dataclass(slots=True)
class GraphSummary:
    """Aggregate shape of a parsed DDI graph.

    Attributes:
        nodes: Total nodes seen.
        relationships: Total relationships seen.
        nodes_by_label: Count per node label.
        edges_by_shape: Count per ``(start label, type, end label)``.
        samples: Up to ``limit`` example nodes per label.
    """

    nodes: int = 0
    relationships: int = 0
    nodes_by_label: Counter[str] = field(default_factory=Counter)
    edges_by_shape: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    samples: dict[str, list[Node]] = field(default_factory=dict)


def summarise(chunks: Iterable[GraphChunk], *, limit: int = 0) -> GraphSummary:
    """Aggregate a stream of graph chunks.

    Args:
        chunks: Chunks from :func:`ddigraph.graph.view.iter_graph` or
            :func:`ddigraph.rdf.reader.read_graph`.
        limit: Example nodes to keep per label. ``0`` keeps none, which is
            what keeps memory flat on a large file.

    Returns:
        GraphSummary: The aggregate.
    """
    summary = GraphSummary()

    for chunk in chunks:
        for node in chunk.nodes:
            summary.nodes += 1
            summary.nodes_by_label[node.label] += 1
            if limit:
                kept = summary.samples.setdefault(node.label, [])
                if len(kept) < limit:
                    kept.append(node)
        for edge in chunk.relationships:
            summary.relationships += 1
            summary.edges_by_shape[(edge.start.label, edge.type, edge.end.label)] += 1

    logger.info(
        "Summarised graph",
        extra={
            "nodes": summary.nodes,
            "relationships": summary.relationships,
            "labels": len(summary.nodes_by_label),
            "edge_shapes": len(summary.edges_by_shape),
        },
    )
    return summary


def preview(
    source: str | Path,
    *,
    format: str = "text",
    limit: int = 0,
    flavor: str | None = None,
    dataset_id: str | None = None,
    chunk_size: int = 200,
) -> str:
    """Render a preview of a DDI file's graph shape.

    Args:
        source: Path to a DDI Codebook, DDI-L or DDI-CDI file.
        format: One of :data:`FORMATS`.
        limit: Example nodes to show per label.
        flavor: Force a DDI flavor instead of sniffing the file.
        dataset_id: Dataset identifier for codebook input.
        chunk_size: Records per streamed chunk.

    Returns:
        The rendered preview.

    Raises:
        ValueError: If ``format`` is not one of :data:`FORMATS`.
    """
    if format not in FORMATS:
        raise ValueError(
            f"Unknown preview format {format!r}. Expected one of: {', '.join(FORMATS)}"
        )

    summary = summarise(
        iter_graph(source, flavor=flavor, dataset_id=dataset_id, chunk_size=chunk_size),
        limit=limit,
    )

    if format == "mermaid":
        return to_mermaid(summary)
    if format == "html":
        return to_html(summary, title=Path(source).name)
    return to_text(summary, source=str(source))


def _sorted_labels(summary: GraphSummary) -> list[tuple[str, int]]:
    """Labels by descending count, then name, so output is deterministic."""
    return sorted(summary.nodes_by_label.items(), key=lambda item: (-item[1], item[0]))


def _sorted_edges(summary: GraphSummary) -> list[tuple[tuple[str, str, str], int]]:
    """Edge shapes by descending count, then name."""
    return sorted(summary.edges_by_shape.items(), key=lambda item: (-item[1], item[0]))


def to_text(summary: GraphSummary, *, source: str = "") -> str:
    """Render a plain-text summary for the terminal."""
    lines: list[str] = []
    if source:
        lines.append(f"Preview: {source}")
    lines.append(f"Nodes: {summary.nodes}   Relationships: {summary.relationships}")

    if summary.nodes_by_label:
        lines.append("")
        lines.append("Node types")
        width = max(len(label) for label in summary.nodes_by_label)
        for label, count in _sorted_labels(summary):
            lines.append(f"  {label.ljust(width)}  {count}")

    if summary.edges_by_shape:
        lines.append("")
        lines.append("Relationships")
        for (start, rel_type, end), count in _sorted_edges(summary):
            lines.append(f"  ({start})-[:{rel_type}]->({end})  {count}")

    for label, nodes in sorted(summary.samples.items()):
        if not nodes:
            continue
        lines.append("")
        lines.append(f"Sample {label}")
        for node in nodes:
            identity = ", ".join(f"{k}={v}" for k, v in sorted(node.identity.items()))
            lines.append(f"  {identity}")

    return "\n".join(lines) + "\n"


def _mermaid_id(label: str) -> str:
    """Return a Mermaid-safe node id for a label."""
    return _UNSAFE_ID.sub("_", label) or "unknown"


def to_mermaid(summary: GraphSummary) -> str:
    """Render the shape as a Mermaid ``graph LR`` definition.

    One box per node type and one arrow per relationship shape, both
    carrying counts. Isolated types are still drawn: a label with no edges
    is usually the interesting thing on the page.
    """
    lines = ["graph LR"]

    for label, count in _sorted_labels(summary):
        lines.append(f'    {_mermaid_id(label)}["{label}<br/>{count}"]')

    for (start, rel_type, end), count in _sorted_edges(summary):
        lines.append(f"    {_mermaid_id(start)} -->|{rel_type} {count}| {_mermaid_id(end)}")

    return "\n".join(lines) + "\n"


def to_html(summary: GraphSummary, *, title: str = "DDI graph") -> str:
    """Render a self-contained HTML page.

    No external stylesheet, no CDN, no JavaScript: the file works offline
    and survives being emailed. The diagram is an inline SVG bar chart
    rather than a rendered graph layout, because a faithful layout needs a
    layout engine and the counts are what the question was actually about.
    The Mermaid source is included for anyone who wants the diagram.
    """
    esc = html.escape
    labels = _sorted_labels(summary)
    edges = _sorted_edges(summary)

    rows = "\n".join(
        f"<tr><td>{esc(label)}</td><td class='n'>{count}</td></tr>" for label, count in labels
    )
    edge_rows = "\n".join(
        f"<tr><td>{esc(start)}</td><td><code>{esc(rel_type)}</code></td>"
        f"<td>{esc(end)}</td><td class='n'>{count}</td></tr>"
        for (start, rel_type, end), count in edges
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} - ddigraph preview</title>
<style>
  :root {{ color-scheme: light dark; --fg: #1a1a1a; --bg: #ffffff;
           --muted: #666; --rule: #e0e0e0; --bar: #4051b5; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg: #e8e8e8; --bg: #16181d; --muted: #9aa0a6;
             --rule: #333842; --bar: #7986cb; }}
  }}
  body {{ font: 15px/1.5 system-ui, sans-serif; color: var(--fg);
          background: var(--bg); margin: 0 auto; padding: 2rem 1rem;
          max-width: 60rem; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 .25rem; }}
  p.sub {{ color: var(--muted); margin: 0 0 2rem; }}
  h2 {{ font-size: 1.1rem; margin: 2rem 0 .75rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .4rem .6rem;
            border-bottom: 1px solid var(--rule); }}
  td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{ font-family: ui-monospace, monospace; font-size: .9em; }}
  pre {{ background: color-mix(in srgb, var(--fg) 6%, transparent);
         padding: 1rem; overflow-x: auto; border-radius: 6px; }}
  .scroll {{ overflow-x: auto; }}
</style>
</head>
<body>
<h1>{esc(title)}</h1>
<p class="sub">{summary.nodes} nodes &middot; {summary.relationships} relationships
&middot; {len(labels)} node types &middot; {len(edges)} relationship shapes</p>

<h2>Node types</h2>
{_svg_bars(labels)}
<div class="scroll">
<table><thead><tr><th>Type</th><th class="n">Count</th></tr></thead>
<tbody>
{rows}
</tbody></table>
</div>

<h2>Relationships</h2>
<div class="scroll">
<table><thead><tr><th>From</th><th>Type</th><th>To</th><th class="n">Count</th></tr></thead>
<tbody>
{edge_rows}
</tbody></table>
</div>

<h2>Diagram source</h2>
<p class="sub">Paste into any Mermaid viewer.</p>
<pre><code>{esc(to_mermaid(summary))}</code></pre>
</body>
</html>
"""


def _svg_bars(labels: list[tuple[str, int]], *, top: int = 15) -> str:
    """Render an inline SVG bar chart of the most common node types."""
    shown = labels[:top]
    if not shown:
        return "<p>No nodes.</p>"

    esc = html.escape
    largest = shown[0][1] or 1
    row_height, gap, label_width, bar_width = 22, 4, 210, 420
    height = len(shown) * (row_height + gap)

    bars: list[str] = []
    for index, (label, count) in enumerate(shown):
        y = index * (row_height + gap)
        width = max(1, round(bar_width * count / largest))
        bars.append(
            f'<text x="{label_width - 8}" y="{y + 15}" text-anchor="end" '
            f'font-size="12" fill="currentColor">{esc(label)}</text>'
            f'<rect x="{label_width}" y="{y}" width="{width}" height="{row_height}" '
            f'rx="3" fill="var(--bar)"></rect>'
            f'<text x="{label_width + width + 6}" y="{y + 15}" font-size="12" '
            f'fill="currentColor">{count}</text>'
        )

    remainder = len(labels) - len(shown)
    caption = f"<p class='sub'>Showing the {top} most common of {len(labels)} types.</p>"
    return (
        f'<div class="scroll"><svg role="img" aria-label="Node counts by type" '
        f'width="{label_width + bar_width + 60}" height="{height}" '
        f'viewBox="0 0 {label_width + bar_width + 60} {height}">'
        f"{''.join(bars)}</svg></div>" + (caption if remainder > 0 else "")
    )


__all__ = ["FORMATS", "GraphSummary", "preview", "summarise", "to_html", "to_mermaid", "to_text"]

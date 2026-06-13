#!/usr/bin/env python3
"""Demo: Load DDI into NetworkX for local graph analysis.

This demonstrates using the adapter pattern to load DDI data into
NetworkX instead of Neo4j - useful for local analysis without a database.

Usage:
    python load_networkx.py [path/to/ddi.xml]

Requirements:
    pip install networkx matplotlib
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    import networkx as nx  # type: ignore[import-untyped]
except ImportError:
    print("Error: NetworkX required. Install with: pip install networkx")
    sys.exit(1)

from ddigraph.ingest.fragment_loader import (
    DDIFragmentParser,
    FragmentBatch,
)


class NetworkXFragmentWriter:
    """Write DDI-L fragments to a NetworkX graph."""

    def __init__(self) -> None:
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Write a batch of fragments to NetworkX."""
        counts: dict[str, int] = {}

        # Add nodes
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                props = fragment.to_dict()
                node_id = props.pop("fragment_id")
                # Remove any existing label to avoid conflict
                props.pop("label", None)
                self.graph.add_node(
                    node_id,
                    node_type=element_type,
                    **props,
                )
            counts[element_type] = len(fragments)

        # Add relationships
        for from_id, rel_type, to_id in batch.relationships:
            self.graph.add_edge(from_id, to_id, key=rel_type, type=rel_type)
        counts["relationships"] = len(batch.relationships)

        return counts


async def load_to_networkx(ddi_path: Path) -> nx.MultiDiGraph:
    """Load DDI-L file into NetworkX graph."""
    writer = NetworkXFragmentWriter()
    parser = DDIFragmentParser(ddi_path)

    totals: dict[str, int] = {}

    for batch in parser.parse_batches():
        counts = await writer.write_batch(batch)
        for key, value in counts.items():
            totals[key] = totals.get(key, 0) + value

    # Relationships are tracked separately so they don't appear as a node type.
    rel_count = totals.pop("relationships", 0)

    print("\nLoaded:")
    for key, count in sorted(totals.items()):
        if count > 0:
            print(f"  {key}: {count}")
    print(f"  Relationships (edges): {rel_count}")

    return writer.graph


def analyze_graph(g: nx.MultiDiGraph) -> None:
    """Print basic graph analysis."""
    print("\n" + "=" * 60)
    print(" NETWORKX GRAPH ANALYSIS")
    print("=" * 60)

    print("\nBasic Stats:")
    print(f"  Nodes: {g.number_of_nodes()}")
    print(f"  Edges: {g.number_of_edges()}")

    # Count by node_type
    label_counts: dict[str, int] = {}
    for _, data in g.nodes(data=True):
        label = data.get("node_type", "Unknown")
        label_counts[label] = label_counts.get(label, 0) + 1

    print("\nNodes by Type:")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")

    # Count by relationship type
    rel_counts: dict[str, int] = {}
    for _, _, data in g.edges(data=True):
        rel_type = data.get("type", "UNKNOWN")
        rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1

    print("\nRelationships by Type:")
    for rel_type, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
        print(f"  {rel_type}: {count}")

    # Find entry point (Instrument)
    instruments = [n for n, d in g.nodes(data=True) if d.get("node_type") == "Instrument"]
    if instruments:
        entry = instruments[0]
        print(f"\nEntry Point: {entry}")

        # Shortest path analysis
        reachable = nx.descendants(g, entry)
        print(f"  Reachable nodes: {len(reachable)}")

        # Depth analysis
        depths = nx.single_source_shortest_path_length(g, entry)
        max_depth = max(depths.values()) if depths else 0
        print(f"  Maximum depth: {max_depth}")

    # Connected components (treating as undirected)
    undirected = g.to_undirected()
    components = list(nx.connected_components(undirected))
    print(f"\nConnected Components: {len(components)}")
    if len(components) > 1:
        print(f"  Largest: {len(max(components, key=len))} nodes")
        print(f"  Smallest: {len(min(components, key=len))} nodes")


def export_graph(g: nx.MultiDiGraph, output_path: Path) -> None:
    """Export graph to various formats."""
    # GraphML export
    graphml_path = output_path.with_suffix(".graphml")
    nx.write_graphml(g, graphml_path)
    print(f"\nExported to: {graphml_path}")

    # Try to visualize if matplotlib is available
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]

        # Create a simplified view for visualization
        # (full graph is usually too large)
        instruments = [n for n, d in g.nodes(data=True) if d.get("node_type") == "Instrument"]
        if instruments:
            # Get nodes within 2 hops of instrument
            entry = instruments[0]
            subgraph_nodes = {entry}
            for neighbor in g.neighbors(entry):
                subgraph_nodes.add(neighbor)
                for n2 in g.neighbors(neighbor):
                    subgraph_nodes.add(n2)

            if len(subgraph_nodes) <= 50:
                subgraph = g.subgraph(subgraph_nodes)
                plt.figure(figsize=(12, 8))
                pos = nx.spring_layout(subgraph, k=2, iterations=50)

                # Color by node_type
                colors = []
                for node in subgraph.nodes():
                    node_type = subgraph.nodes[node].get("node_type", "")
                    color_map = {
                        "Instrument": "red",
                        "Sequence": "blue",
                        "IfThenElse": "orange",
                        "QuestionConstruct": "green",
                    }
                    colors.append(color_map.get(node_type, "gray"))

                nx.draw(
                    subgraph,
                    pos,
                    node_color=colors,
                    node_size=100,
                    with_labels=False,
                    alpha=0.7,
                )
                png_path = output_path.with_suffix(".png")
                plt.savefig(png_path, dpi=150, bbox_inches="tight")
                plt.close()
                print(f"Visualization: {png_path}")
    except ImportError:
        pass


async def main() -> None:
    """Load DDI file and analyze with NetworkX."""
    # Determine file path
    if len(sys.argv) > 1:
        ddi_path = Path(sys.argv[1])
    else:
        ddi_path = Path(__file__).parent / "Ireland_LabourSurvey.xml"

    if not ddi_path.exists():
        print(f"Error: File not found: {ddi_path}")
        sys.exit(1)

    print(f"File: {ddi_path.name}")
    print("Loading into NetworkX...")

    # Load
    graph = await load_to_networkx(ddi_path)

    # Analyze
    analyze_graph(graph)

    # Export
    output_path = Path("ddi_graph")
    export_graph(graph, output_path)


if __name__ == "__main__":
    asyncio.run(main())

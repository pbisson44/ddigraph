"""Demo: Load DDI into Gremlin-compatible format for graph traversal queries.

This demonstrates using the adapter pattern to prepare DDI data for
Gremlin-compatible graph databases. Exports to GraphSON format that
can be loaded into JanusGraph, Amazon Neptune, Azure Cosmos DB, etc.

For a live demo with a local Gremlin server:
    docker run -p 8182:8182 tinkerpop/gremlin-server
    python load_gremlin.py --server ws://localhost:8182/gremlin

Usage:
    python load_gremlin.py [path/to/ddi.xml]
    python load_gremlin.py --server <gremlin-ws-url> [path/to/ddi.xml]

Requirements:
    pip install gremlinpython
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from ddigraph.ingest.fragment_loader import (
    DDIFragmentParser,
    FragmentBatch,
)

# Tuple kept as a named reference because ruff format 0.15.x ``py314``
# target strips parens from inline ``except (A, B):`` clauses and
# produces invalid Python 3 syntax. Aliasing the tuple sidesteps the bug.
_OPTIONAL_GREMLIN_IMPORT_ERRORS: tuple[type[BaseException], ...] = (
    ImportError,
    AttributeError,
)
try:
    gremlin_driver = importlib.import_module("gremlin_python.driver.driver_remote_connection")
    gremlin_anonymous = importlib.import_module("gremlin_python.process.anonymous_traversal")
    gremlin_traversal = importlib.import_module("gremlin_python.process.traversal")
    gremlin_graph_traversal = importlib.import_module("gremlin_python.process.graph_traversal")
    DriverRemoteConnection = gremlin_driver.DriverRemoteConnection
    traversal = gremlin_anonymous.traversal
    T = gremlin_traversal.T
    __ = gremlin_graph_traversal.__
except _OPTIONAL_GREMLIN_IMPORT_ERRORS:
    print("Error: gremlinpython required. Install with: pip install gremlinpython")
    sys.exit(1)


class GremlinGraphSONWriter:
    """Write DDI-L fragments to GraphSON format for Gremlin import.

    GraphSON is a JSON-based format that Gremlin servers can import. This allows offline
    preparation of data for Gremlin databases.
    """

    def __init__(self) -> None:
        """Initialize GraphSON writer."""
        self.vertices: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.stats: dict[str, int] = defaultdict(int)

    def _sanitize_property_value(self, value: Any) -> Any:
        """Sanitize property values for GraphSON."""
        if value is None:
            return ""
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, (list, dict)):
            # Convert complex types to JSON strings
            return json.dumps(value)
        return str(value)

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Write a batch of fragments to GraphSON format."""
        counts: dict[str, int] = {}

        # Add vertices
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                props = fragment.to_dict()
                vertex_id = props["fragment_id"]

                # Build properties dict
                properties: dict[str, Any] = {}
                for key, value in props.items():
                    if key == "fragment_id":
                        continue  # Used as ID

                    sanitized = self._sanitize_property_value(value)
                    if sanitized or sanitized == 0 or sanitized is False:
                        # GraphSON format wraps property values
                        properties[key] = [{"id": f"{vertex_id}-{key}", "value": sanitized}]

                # Store vertex
                self.vertices[vertex_id] = {
                    "id": vertex_id,
                    "label": element_type,
                    "type": "vertex",
                    "properties": properties,
                }
                self.stats[f"vertex:{element_type}"] += 1

            counts[element_type] = len(fragments)

        # Add edges
        for from_id, rel_type, to_id in batch.relationships:
            edge = {
                "id": f"{from_id}-{rel_type}-{to_id}",
                "label": rel_type,
                "type": "edge",
                "inVLabel": self.vertices.get(to_id, {}).get("label", "Unknown"),
                "outVLabel": self.vertices.get(from_id, {}).get("label", "Unknown"),
                "inV": to_id,
                "outV": from_id,
                "properties": {},
            }
            self.edges.append(edge)
            self.stats[f"edge:{rel_type}"] += 1

        counts["relationships"] = len(batch.relationships)

        return counts

    def to_graphson(self) -> dict[str, list[dict[str, Any]]]:
        """Convert to GraphSON v3 format."""
        return {
            "vertices": list(self.vertices.values()),
            "edges": self.edges,
        }


class GremlinRemoteWriter:
    """Write DDI-L fragments to a remote Gremlin server.

    This adapter connects to a Gremlin server and writes data directly. Use with
    JanusGraph, TinkerPop Server, Neptune, Cosmos DB, etc.
    """

    def __init__(self, server_url: str) -> None:
        """Initialize connection to Gremlin server."""
        self.server_url = server_url
        self.g = traversal().with_remote(DriverRemoteConnection(server_url, "g"))
        self.stats: dict[str, int] = defaultdict(int)

    def _sanitize_property_value(self, value: Any) -> Any:
        """Sanitize property values for Gremlin."""
        if value is None:
            return ""
        elif isinstance(value, (list, dict)):
            return json.dumps(value)
        return value

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Write a batch of fragments to remote Gremlin server."""
        counts: dict[str, int] = {}

        # Add vertices
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                props = fragment.to_dict()
                vertex_id = props["fragment_id"]

                # Create vertex
                v = self.g.addV(element_type).property(T.id, vertex_id)

                # Add properties
                for key, value in props.items():
                    if key == "fragment_id":
                        continue

                    sanitized = self._sanitize_property_value(value)
                    if sanitized or sanitized == 0 or sanitized is False:
                        v = v.property(key, sanitized)

                v.next()
                self.stats[f"vertex:{element_type}"] += 1

            counts[element_type] = len(fragments)

        # Add edges
        for from_id, rel_type, to_id in batch.relationships:
            try:
                self.g.V(from_id).addE(rel_type).to(__.V(to_id)).next()
                self.stats[f"edge:{rel_type}"] += 1
            except Exception:
                # Skip if vertices don't exist
                pass

        counts["relationships"] = len(batch.relationships)

        return counts

    def close(self) -> None:
        """Close connection to Gremlin server."""
        try:
            self.g.close()
        except Exception:
            pass


async def load_to_graphson(ddi_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load DDI-L file into GraphSON format."""
    writer = GremlinGraphSONWriter()
    parser = DDIFragmentParser(ddi_path)

    totals: dict[str, int] = {}

    print("Loading batches...")
    batch_count = 0
    for batch in parser.parse_batches():
        counts = await writer.write_batch(batch)
        for key, value in counts.items():
            totals[key] = totals.get(key, 0) + value
        batch_count += 1
        if batch_count % 10 == 0:
            print(f"  Processed {batch_count} batches...")

    # Relationships are tracked separately so they don't appear as a node type.
    rel_count = totals.pop("relationships", 0)
    print("\nLoaded:")
    for key, count in sorted(totals.items()):
        if count > 0:
            print(f"  {key}: {count}")
    print(f"  Relationships (edges): {rel_count}")

    return writer.to_graphson()


async def load_to_gremlin_server(ddi_path: Path, server_url: str) -> GremlinRemoteWriter:
    """Load DDI-L file into remote Gremlin server."""
    writer = GremlinRemoteWriter(server_url)
    parser = DDIFragmentParser(ddi_path)

    totals: dict[str, int] = {}

    print(f"Loading to Gremlin server: {server_url}")
    print("Loading batches...")
    batch_count = 0
    for batch in parser.parse_batches():
        counts = await writer.write_batch(batch)
        for key, value in counts.items():
            totals[key] = totals.get(key, 0) + value
        batch_count += 1
        if batch_count % 10 == 0:
            print(f"  Processed {batch_count} batches...")

    # Relationships are tracked separately so they don't appear as a node type.
    rel_count = totals.pop("relationships", 0)
    print("\nLoaded:")
    for key, count in sorted(totals.items()):
        if count > 0:
            print(f"  {key}: {count}")
    print(f"  Relationships (edges): {rel_count}")

    return writer


def analyze_graphson(data: dict[str, list[dict[str, Any]]]) -> None:
    """Analyze the GraphSON data."""
    print("\n" + "=" * 60)
    print(" GRAPHSON ANALYSIS")
    print("=" * 60)

    vertices = data["vertices"]
    edges = data["edges"]

    print("\nBasic Stats:")
    print(f"  Vertices: {len(vertices)}")
    print(f"  Edges: {len(edges)}")

    # Count by label
    print("\nVertices by Label:")
    label_counts: dict[str, int] = defaultdict(int)
    for v in vertices:
        label_counts[v["label"]] += 1
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")

    # Count edges by type
    if edges:
        print("\nEdges by Type:")
        edge_counts: dict[str, int] = defaultdict(int)
        for e in edges:
            edge_counts[e["label"]] += 1
        for edge_type, count in sorted(edge_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {edge_type}: {count}")


def demonstrate_gremlin_queries(data: dict[str, list[dict[str, Any]]]) -> None:
    """Show example Gremlin queries that would work with this data."""
    print("\n" + "=" * 60)
    print(" EXAMPLE GREMLIN QUERIES")
    print("=" * 60)
    print(
        """Once loaded into a Gremlin server, you can run these queries:

        --- Query 1: Find Instruments ---
        g.V().hasLabel('Instrument').valueMap(true)

        --- Query 2: Sample QuestionItems ---
        g.V().hasLabel('QuestionItem')
          .project('id', 'label', 'text')
          .by(id)
          .by('label')
          .by('question_text')
          .limit(5)

        --- Query 3: Questions with CodeLists ---
        g.V().hasLabel('QuestionItem')
          .as('q')
          .out('USES_CODELIST')
          .hasLabel('CodeList')
          .as('c')
          .select('q', 'c')
          .by('label')

        --- Query 4: Reachability from Instrument ---
        g.V().hasLabel('Instrument').out().count()  // 1 hop
        g.V().hasLabel('Instrument').out().out().dedup().count()  // 2 hops

        --- Query 5: Largest Sequences ---
        g.V().hasLabel('Sequence')
          .project('id', 'label', 'outCount')
          .by(id)
          .by('label')
          .by(outE('HAS_CONSTRUCT').count())
          .order().by('outCount', desc)
          .limit(5)

        --- Query 6: Path Analysis ---
        g.V().hasLabel('Instrument')
          .repeat(out())
          .until(hasLabel('Category'))
          .path()
          .limit(10)

        --- Query 7: Control Flow Patterns ---
        g.V().hasLabel('IfThenElse')
          .where(outE('THEN'))
          .where(outE('ELSE'))
          .count()
        """
    )

    # Show some stats about what queries would find
    vertices = data["vertices"]
    edges = data["edges"]

    instruments = [v for v in vertices if v["label"] == "Instrument"]
    questions = [v for v in vertices if v["label"] == "QuestionItem"]
    sequences = [v for v in vertices if v["label"] == "Sequence"]

    print("\nExpected Results:")
    print(f"  Instruments found: {len(instruments)}")
    print(f"  QuestionItems found: {len(questions)}")
    print(f"  Sequences found: {len(sequences)}")

    # Count USES_CODELIST edges
    uses_codelist = [e for e in edges if e["label"] == "USES_CODELIST"]
    print(f"  Questions with codelists: {len(uses_codelist)}")


def export_graphson(data: dict[str, list[dict[str, Any]]], output_path: Path) -> None:
    """Export to GraphSON file."""
    print("\n" + "=" * 60)
    print(" EXPORT")
    print("=" * 60)

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nGraphSON export: {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024:.1f} KB")
    print("\nLoad into Gremlin server:")
    print("  // Using TinkerPop GraphSON I/O")
    print(f"  graph.io(graphson()).readGraph('{output_path.name}')")
    print("\nOr use gremlin-python to load programmatically")


def show_gremlin_setup() -> None:
    """Show instructions for setting up a Gremlin server."""
    print("\n" + "=" * 60)
    print(" RUNNING WITH A GREMLIN SERVER")
    print("=" * 60)
    print(
        """
To run queries against a live Gremlin server:
 
1. Start a local Gremlin server with Docker:
   docker run -p 8182:8182 tinkerpop/gremlin-server
 
2. Run this script with the --server flag:
   python load_gremlin.py --server ws://localhost:8182/gremlin
 
3. Or use managed services:
   - Amazon Neptune: ws://<neptune-endpoint>:8182/gremlin
   - Azure Cosmos DB: wss://<account>.gremlin.cosmos.azure.com:443/
 
Production Options:
  - JanusGraph: Scalable graph DB with Cassandra/HBase backend
  - Amazon Neptune: Fully managed graph database service
  - Azure Cosmos DB: Globally distributed with Gremlin API
  - DataStax Graph: Enterprise graph database
"""
    )


async def main() -> None:
    """Load DDI file and prepare for Gremlin."""
    # Parse command line args
    server_url = None
    ddi_path_arg = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--server" and i + 1 < len(args):
            server_url = args[i + 1]
            i += 2
        else:
            ddi_path_arg = args[i]
            i += 1

    # Determine file path
    if ddi_path_arg:
        ddi_path = Path(ddi_path_arg)
    else:
        ddi_path = Path(__file__).parent / "Ireland_LabourSurvey.xml"

    if not ddi_path.exists():
        print(f"Error: File not found: {ddi_path}")
        sys.exit(1)

    print(f"File: {ddi_path.name}")

    if server_url:
        # Load to remote Gremlin server
        try:
            writer = await load_to_gremlin_server(ddi_path, server_url)
            writer.close()
            print("\n" + "=" * 60)
            print("Data loaded successfully!")
            print("Connect to the Gremlin server to run queries.")
            print("=" * 60)
        except Exception as e:
            print(f"\nError connecting to Gremlin server: {e}")
            print("Make sure the server is running and accessible.")
            sys.exit(1)
    else:
        # Export to GraphSON format
        print("Exporting to GraphSON format...")
        print("(Use --server <url> to load directly to a Gremlin server)\n")

        data = await load_to_graphson(ddi_path)

        # Analyze
        analyze_graphson(data)

        # Show example queries
        demonstrate_gremlin_queries(data)

        # Export
        output_path = Path("ddi_graph.json")
        export_graphson(data, output_path)

        # Show setup instructions
        show_gremlin_setup()


if __name__ == "__main__":
    asyncio.run(main())

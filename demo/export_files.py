#!/usr/bin/env python3
"""Demo: Export DDI to JSON and CSV files.

This demonstrates using the adapter pattern to export DDI data
to file formats for analysis in other tools (Excel, pandas, etc.).

Usage:
    python export_files.py [path/to/ddi.xml] [--output-dir ./output]

Output:
    - nodes.json / nodes.csv - All nodes with properties
    - relationships.json / relationships.csv - All relationships
    - summary.json - Graph statistics
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from ddigraph.ingest.fragment_loader import (
    DDIFragmentParser,
    FragmentBatch,
)


class FileExportWriter:
    """Export DDI-L fragments to JSON and CSV files."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.nodes: list[dict[str, Any]] = []
        self.relationships: list[dict[str, Any]] = []
        self.counts: dict[str, int] = defaultdict(int)

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Collect batch data for export."""
        batch_counts: dict[str, int] = {}

        # Collect nodes
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                props = fragment.to_dict()
                # Use node_type instead of label to avoid conflicts
                props["node_type"] = element_type
                self.nodes.append(
                    {
                        "id": props.get("fragment_id"),
                        **props,
                    }
                )
            batch_counts[element_type] = len(fragments)
            self.counts[element_type] += len(fragments)

        # Collect relationships
        for from_id, rel_type, to_id in batch.relationships:
            self.relationships.append(
                {
                    "from_id": from_id,
                    "type": rel_type,
                    "to_id": to_id,
                }
            )
        batch_counts["relationships"] = len(batch.relationships)
        self.counts["relationships"] += len(batch.relationships)

        return batch_counts

    def export_json(self) -> None:
        """Export data to JSON files."""
        # Nodes
        nodes_path = self.output_dir / "nodes.json"
        with open(nodes_path, "w", encoding="utf-8") as f:
            json.dump(self.nodes, f, indent=2, default=str)
        print(f"  {nodes_path} ({len(self.nodes)} nodes)")

        # Relationships
        rels_path = self.output_dir / "relationships.json"
        with open(rels_path, "w", encoding="utf-8") as f:
            json.dump(self.relationships, f, indent=2)
        print(f"  {rels_path} ({len(self.relationships)} relationships)")

        # Summary
        summary = {
            "total_nodes": len(self.nodes),
            "total_relationships": len(self.relationships),
            "nodes_by_type": dict(self.counts),
            "relationships_by_type": self._count_relationship_types(),
        }
        summary_path = self.output_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"  {summary_path}")

    def export_csv(self) -> None:
        """Export data to CSV files."""
        # Nodes CSV
        nodes_path = self.output_dir / "nodes.csv"
        if self.nodes:
            # Get all unique keys
            all_keys: set[str] = set()
            for node in self.nodes:
                all_keys.update(node.keys())
            fieldnames = sorted(all_keys)

            with open(nodes_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.nodes)
            print(f"  {nodes_path}")

        # Relationships CSV
        rels_path = self.output_dir / "relationships.csv"
        if self.relationships:
            fieldnames = ["from_id", "type", "to_id"]
            with open(rels_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.relationships)
            print(f"  {rels_path}")

    def _count_relationship_types(self) -> dict[str, int]:
        """Count relationships by type."""
        counts: dict[str, int] = defaultdict(int)
        for rel in self.relationships:
            counts[rel["type"]] += 1
        return dict(counts)


async def export_ddi(ddi_path: Path, output_dir: Path) -> None:
    """Export DDI-L file to JSON and CSV."""
    writer = FileExportWriter(output_dir)
    parser = DDIFragmentParser(ddi_path)

    print("Parsing DDI...")
    for batch in parser.parse_batches():
        await writer.write_batch(batch)

    print(f"\nParsed: {len(writer.nodes)} nodes, {len(writer.relationships)} relationships")

    print("\nExporting JSON...")
    writer.export_json()

    print("\nExporting CSV...")
    writer.export_csv()


async def main() -> None:
    """Export DDI file to JSON and CSV."""
    parser = argparse.ArgumentParser(
        description="Export DDI-L to JSON and CSV files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "xml_path",
        nargs="?",
        type=Path,
        default=Path(__file__).parent / "Ireland_LabourSurvey.xml",
        help="Path to DDI-L XML file",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("ddi_export"),
        help="Output directory (default: ddi_export)",
    )
    args = parser.parse_args()

    if not args.xml_path.exists():
        print(f"Error: File not found: {args.xml_path}")
        sys.exit(1)

    print(f"File: {args.xml_path.name}")
    print(f"Output: {args.output_dir}")

    await export_ddi(args.xml_path, args.output_dir)

    print("\nDone! Files ready for import into Excel, pandas, etc.")


if __name__ == "__main__":
    asyncio.run(main())

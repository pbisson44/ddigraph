#!/usr/bin/env python3
r"""Standalone DDI-L graph audit for Neo4j Aura.

No dependencies except neo4j driver.

Usage:
    python audit_graph_standalone.py \
        --uri "neo4j+s://xxx.databases.neo4j.io" \
        --user neo4j \
        --password "your-password"
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from neo4j import GraphDatabase


def audit_graph(uri: str, user: str, password: str, database: str = "neo4j") -> dict[str, Any]:
    """Run full audit and return results."""
    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session(database=database) as session:
            # Node counts by label
            node_counts = {
                r["label"]: r["count"]
                for r in session.run("""MATCH (n) UNWIND labels(n) AS label RETURN
                                     label, count(*) AS count ORDER BY count DESC.""")
            }

            # Relationship counts by type
            rel_counts = {
                r["type"]: r["count"]
                for r in session.run(
                    """MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER
                    BY count DESC."""
                )
            }

            # Full relationship mapping: (Start)-[TYPE]->(End)
            rel_mapping = [
                {
                    "pattern": f"({r['start']})-[{r['rel']}]->({r['end']})",
                    "start": r["start"],
                    "relationship": r["rel"],
                    "end": r["end"],
                    "count": r["count"],
                }
                for r in session.run(
                    """MATCH (a)-[r]->(b) WITH labels(a)[0] AS start, type(r) AS rel,
                    labels(b)[0] AS end, count(*) AS count RETURN start, rel, end, count
                    ORDER BY count DESC."""
                )
            ]

            # Entry points
            entry_points = [
                {"labels": list(r["labels"]), "id": r["id"], "name": r["name"], "title": r["title"]}
                for r in session.run(
                    """MATCH (n) WHERE n:EntryPoint OR n:Instrument OR n:StudyUnit
                    RETURN labels(n) AS labels, n.fragment_id AS id, n.name AS name,
                    n.title AS title."""
                )
            ]

            # Orphan nodes (no relationships)
            orphans = [
                {"label": r["label"], "id": r["id"], "name": r["name"]}
                for r in session.run(
                    """MATCH (n) WHERE NOT (n)--() RETURN labels(n)[0] AS label,
                    n.fragment_id AS id, n.name AS name LIMIT 100."""
                )
            ]

            # Sample traversal paths
            sample_paths = []
            for r in session.run(
                """
                MATCH path = (entry)-[*1..5]->(end)
                WHERE entry:EntryPoint OR entry:Instrument OR entry:StudyUnit
                WITH path LIMIT 10
                RETURN [n IN nodes(path) | labels(n)[0]] AS labels,
                       [r IN relationships(path) | type(r)] AS rels
            """
            ):
                path_str = r["labels"][0]
                for i, rel in enumerate(r["rels"]):
                    path_str += f" -[{rel}]-> {r['labels'][i + 1]}"
                sample_paths.append(path_str)

            # Variables by representation type
            variables_by_type = {
                r["type"]: r["count"]
                for r in session.run(
                    """MATCH (v:Variable) RETURN coalesce(v.representation_type,
                    'unknown') AS type, count(*) AS count ORDER BY count DESC."""
                )
            }

            # Study structure
            study_structure = [
                dict(r)
                for r in session.run(
                    """MATCH (s:StudyUnit) OPTIONAL MATCH
                    (s)-[:HAS_DATA_COLLECTION]->(dc:DataCollection) OPTIONAL MATCH
                    (s)-[:USES_RESOURCE_PACKAGE]->(rp:ResourcePackage) RETURN
                    s.fragment_id AS id, s.title AS title, count(DISTINCT dc) AS
                    data_collections, count(DISTINCT rp) AS resource_packages."""
                )
            ]

            return {
                "node_counts": node_counts,
                "relationship_counts": rel_counts,
                "relationship_mapping": rel_mapping,
                "entry_points": entry_points,
                "orphan_nodes": orphans,
                "sample_paths": sample_paths,
                "variables_by_type": variables_by_type,
                "study_structure": study_structure,
                "totals": {
                    "nodes": sum(node_counts.values()),
                    "relationships": sum(rel_counts.values()),
                    "patterns": len(rel_mapping),
                },
            }
    finally:
        driver.close()


def print_audit(audit: dict[str, Any]) -> None:
    """Pretty print audit results."""
    print("\n" + "=" * 70)
    print(" NODE COUNTS")
    print("=" * 70)
    for label, count in audit["node_counts"].items():
        print(f"  {label}: {count}")

    print("\n" + "=" * 70)
    print(" RELATIONSHIP COUNTS")
    print("=" * 70)
    for rel_type, count in audit["relationship_counts"].items():
        print(f"  {rel_type}: {count}")

    print("\n" + "=" * 70)
    print(" RELATIONSHIP MAPPING: (Start)-[TYPE]->(End)")
    print("=" * 70)
    for r in audit["relationship_mapping"]:
        print(f"  {r['pattern']}: {r['count']}")

    print("\n" + "=" * 70)
    print(" ENTRY POINTS")
    print("=" * 70)
    for ep in audit["entry_points"]:
        display = ep.get("title") or ep.get("name") or ep.get("id")
        print(f"  {ep['labels']}: {ep['id']} ({display})")

    if audit.get("study_structure"):
        print("\n" + "=" * 70)
        print(" STUDY STRUCTURE")
        print("=" * 70)
        for s in audit["study_structure"]:
            title = s.get("title", s.get("id"))
            dc = s.get("data_collections")
            rp = s.get("resource_packages")
            print(f"  {title}: {dc} data collections, {rp} resource packages")

    if audit.get("variables_by_type"):
        print("\n" + "=" * 70)
        print(" VARIABLES BY TYPE")
        print("=" * 70)
        for vtype, count in audit["variables_by_type"].items():
            print(f"  {vtype}: {count}")

    print("\n" + "=" * 70)
    print(" SAMPLE PATHS")
    print("=" * 70)
    for path in audit["sample_paths"]:
        print(f"  {path}")

    if audit["orphan_nodes"]:
        print("\n" + "=" * 70)
        print(" ⚠️  ORPHAN NODES (no relationships)")
        print("=" * 70)
        for node in audit["orphan_nodes"]:
            print(f"  {node['label']}: {node['id']} ({node['name']})")

    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)
    print(f"  Total nodes: {audit['totals']['nodes']}")
    print(f"  Total relationships: {audit['totals']['relationships']}")
    print(f"  Unique patterns: {audit['totals']['patterns']}")
    print(f"  Entry points: {len(audit['entry_points'])}")
    print(f"  Orphan nodes: {len(audit['orphan_nodes'])}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit DDI-L graph structure in Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Neo4j Aura
  python audit_graph_standalone.py \\
      --uri "neo4j+s://xxx.databases.neo4j.io" \\
      --user neo4j --password "secret"

  # Local Neo4j
  python audit_graph_standalone.py \\
      --uri "bolt://localhost:7687" \\
      --user neo4j --password "password"

  # Output as JSON
  python audit_graph_standalone.py --uri ... --json > audit.json
        """,
    )
    parser.add_argument("--uri", required=True, help="Neo4j URI")
    parser.add_argument("--user", required=True, help="Neo4j username")
    parser.add_argument("--password", required=True, help="Neo4j password")
    parser.add_argument("--database", default="neo4j", help="Database name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    audit = audit_graph(args.uri, args.user, args.password, args.database)

    if args.json:
        print(json.dumps(audit, indent=2))
    else:
        print_audit(audit)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Audit DDI-L graph structure in Neo4j.

Queries the graph to show node counts, relationship mappings, and
potential issues for validation.

Usage:
    python audit_graph.py                  # Use .env for credentials
    python audit_graph.py --uri bolt://... # Override connection
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Session


def get_node_counts(session: Session) -> dict[str, int]:
    """Get count of each node label."""
    result = session.run("""
        MATCH (n)
        WITH labels(n) AS labels, count(*) AS count
        UNWIND labels AS label
        RETURN label, sum(count) AS count
        ORDER BY count DESC
    """)
    return {record["label"]: record["count"] for record in result}


def get_relationship_counts(session: Session) -> dict[str, int]:
    """Get count of each relationship type."""
    result = session.run("""
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        ORDER BY count DESC
    """)
    return {record["type"]: record["count"] for record in result}


def get_relationship_mapping(session: Session) -> list[dict[str, Any]]:
    """Get full mapping of (StartLabel)-[TYPE]->(EndLabel) with counts."""
    result = session.run("""
        MATCH (a)-[r]->(b)
        WITH labels(a)[0] AS start_label,
             type(r) AS rel_type,
             labels(b)[0] AS end_label,
             count(*) AS count
        RETURN start_label, rel_type, end_label, count
        ORDER BY start_label, rel_type, end_label
    """)
    return [
        {
            "start": record["start_label"],
            "relationship": record["rel_type"],
            "end": record["end_label"],
            "count": record["count"],
        }
        for record in result
    ]


def get_orphan_nodes(session: Session) -> list[dict[str, Any]]:
    """Find nodes with no incoming or outgoing relationships."""
    result = session.run("""
        MATCH (n)
        WHERE NOT (n)--()
        RETURN labels(n)[0] AS label, n.fragment_id AS id, n.name AS name
        LIMIT 100
    """)
    return [dict(record) for record in result]


def get_entry_points(session: Session) -> list[dict[str, Any]]:
    """Find entry point nodes (Instrument, EntryPoint, or StudyUnit)."""
    result = session.run("""
        MATCH (n)
        WHERE n:EntryPoint OR n:Instrument OR n:StudyUnit
        RETURN labels(n) AS labels, n.fragment_id AS id, n.name AS name, n.title AS title
    """)
    return [dict(record) for record in result]


def get_unreachable_from_entry(session: Session) -> list[dict[str, Any]]:
    """Find constructs not reachable from any entry point."""
    result = session.run("""
        MATCH (entry)
        WHERE entry:EntryPoint OR entry:Instrument OR entry:StudyUnit
        MATCH (entry)-[*]->(reachable)
        WITH collect(DISTINCT elementId(reachable)) AS reachable_ids
        MATCH (n)
        WHERE (n:Sequence OR n:QuestionConstruct OR n:IfThenElse OR n:Loop 
               OR n:QuestionItem OR n:CodeList)
          AND NOT elementId(n) IN reachable_ids
          AND NOT n:EntryPoint
          AND NOT n:Instrument
          AND NOT n:StudyUnit
        RETURN labels(n)[0] AS label, n.fragment_id AS id, n.name AS name
        LIMIT 50
    """)
    return [dict(record) for record in result]


def get_sample_paths(session: Session, limit: int = 5) -> list[str]:
    """Get sample paths from entry point to show structure."""
    result = session.run(
        """
        MATCH path = (entry)-[*1..4]->(end)
        WHERE entry:EntryPoint OR entry:Instrument OR entry:StudyUnit
        RETURN [node IN nodes(path) | labels(node)[0]] AS node_labels,
               [rel IN relationships(path) | type(rel)] AS rel_types
        LIMIT $limit
    """,
        limit=limit,
    )
    paths = []
    for record in result:
        labels = record["node_labels"]
        rels = record["rel_types"]
        path_str = labels[0]
        for i, rel in enumerate(rels):
            path_str += f" -[{rel}]-> {labels[i + 1]}"
        paths.append(path_str)
    return paths


def get_questions_without_codelists(session: Session) -> list[dict[str, Any]]:
    """Find QuestionItems with code response type that don't have a CodeList."""
    result = session.run("""
        MATCH (q:QuestionItem)
        WHERE q.response_type = 'code' AND NOT (q)-[:USES_CODELIST]->()
        RETURN q.fragment_id AS id, q.name AS name,
               substring(q.question_text, 0, 100) AS text_preview
        LIMIT 50
    """)
    return [dict(record) for record in result]


def get_codelists_without_categories(session: Session) -> list[dict[str, Any]]:
    """Find CodeLists that don't have any Categories."""
    result = session.run("""
        MATCH (cl:CodeList)
        WHERE NOT (cl)-[:HAS_CATEGORY]->()
        RETURN cl.fragment_id AS id, cl.name AS name
        LIMIT 50
    """)
    return [dict(record) for record in result]


def get_variables_by_type(session: Session) -> dict[str, int]:
    """Get count of variables by representation type."""
    result = session.run("""
        MATCH (v:Variable)
        RETURN coalesce(v.representation_type, 'unknown') AS type, count(*) AS count
        ORDER BY count DESC
    """)
    return {record["type"]: record["count"] for record in result}


def get_data_collection_summary(session: Session) -> list[dict[str, Any]]:
    """Get summary of data collections and their instruments."""
    result = session.run("""
        MATCH (dc:DataCollection)
        OPTIONAL MATCH (dc)-[:USES_INSTRUMENT]->(i:Instrument)
        RETURN dc.fragment_id AS id, dc.name AS name, 
               count(i) AS instrument_count
        LIMIT 20
    """)
    return [dict(record) for record in result]


def get_study_structure(session: Session) -> list[dict[str, Any]]:
    """Get study units and their data collections."""
    result = session.run("""
        MATCH (s:StudyUnit)
        OPTIONAL MATCH (s)-[:HAS_DATA_COLLECTION]->(dc:DataCollection)
        OPTIONAL MATCH (s)-[:USES_RESOURCE_PACKAGE]->(rp:ResourcePackage)
        RETURN s.fragment_id AS id, s.title AS title,
               count(DISTINCT dc) AS data_collections,
               count(DISTINCT rp) AS resource_packages
    """)
    return [dict(record) for record in result]


def print_section(
    title: str,
    data: dict[str, Any] | list[Any] | None,
    format_func: Callable[[Any], str] | None = None,
) -> None:
    """Print a formatted section."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print("=" * 60)
    if not data:
        print("  (none)")
        return
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"  {key}: {value}")
    elif isinstance(data, list):
        for item in data:
            if format_func:
                print(f"  {format_func(item)}")
            elif isinstance(item, dict):
                print(f"  {item}")
            else:
                print(f"  {item}")


def main() -> None:
    """Run the audit."""
    parser = argparse.ArgumentParser(description="Audit DDI-L graph in Neo4j")
    parser.add_argument("--uri", help="Neo4j URI (default: from .env)")
    parser.add_argument("--user", help="Neo4j user (default: from .env)")
    parser.add_argument("--password", help="Neo4j password (default: from .env)")
    parser.add_argument("--database", default="neo4j", help="Database name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Load from .env if not provided
    uri: str
    user: str
    password: str
    database: str

    if not all([args.uri, args.user, args.password]):
        try:
            from ddigraph.config import Settings

            env_file = Path(__file__).parent / ".env"
            settings = Settings(_env_file=env_file) if env_file.exists() else Settings()
            uri = args.uri or settings.neo4j_uri
            user = args.user or settings.neo4j_user
            password = args.password or settings.neo4j_password.get_secret_value()
            database = args.database or settings.neo4j_database
        except ImportError:
            print("Error: Provide --uri, --user, --password or install ddigraph")
            sys.exit(1)
    else:
        uri = args.uri
        user = args.user
        password = args.password
        database = args.database

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        driver.verify_connectivity()

        with driver.session(database=database) as session:
            # Collect all audit data
            audit: dict[str, Any] = {
                "node_counts": get_node_counts(session),
                "relationship_counts": get_relationship_counts(session),
                "relationship_mapping": get_relationship_mapping(session),
                "entry_points": get_entry_points(session),
                "orphan_nodes": get_orphan_nodes(session),
                "unreachable_constructs": get_unreachable_from_entry(session),
                "sample_paths": get_sample_paths(session),
                "questions_without_codelists": get_questions_without_codelists(session),
                "codelists_without_categories": get_codelists_without_categories(session),
                "variables_by_type": get_variables_by_type(session),
                "data_collections": get_data_collection_summary(session),
                "study_structure": get_study_structure(session),
            }

            if args.json:
                print(json.dumps(audit, indent=2, default=str))
            else:
                # Pretty print
                print_section("Node Counts", audit["node_counts"])
                print_section("Relationship Counts", audit["relationship_counts"])
                print_section(
                    "Relationship Mapping (Start)-[TYPE]->(End)",
                    audit["relationship_mapping"],
                    lambda r: f"({r['start']})-[{r['relationship']}]->({r['end']}): {r['count']}",
                )
                print_section(
                    "Entry Points",
                    audit["entry_points"],
                    lambda e: (
                        f"{e.get('labels', [])}: {e.get('id')} ({e.get('title') or e.get('name')})"
                    ),
                )
                print_section(
                    "Study Structure",
                    audit["study_structure"],
                    lambda s: (
                        f"{s.get('title', s.get('id'))}: "
                        f"{s.get('data_collections')} data collections, "
                        f"{s.get('resource_packages')} resource packages"
                    ),
                )
                print_section(
                    "Data Collections",
                    audit["data_collections"],
                    lambda d: (
                        f"{d.get('name', d.get('id'))}: {d.get('instrument_count')} instruments"
                    ),
                )
                print_section("Variables by Type", audit["variables_by_type"])
                print_section("Sample Paths from Entry Point", audit["sample_paths"])

                # Potential issues
                print_section("⚠️  Orphan Nodes (no relationships)", audit["orphan_nodes"])
                print_section(
                    "⚠️  Unreachable Constructs",
                    audit["unreachable_constructs"],
                )
                print_section(
                    "⚠️  Questions without CodeLists",
                    audit["questions_without_codelists"],
                    lambda q: (
                        f"{q['name']}: {q['text_preview']}..."
                        if q.get("text_preview")
                        else q["name"]
                    ),
                )
                print_section(
                    "⚠️  CodeLists without Categories",
                    audit["codelists_without_categories"],
                )

                # Summary
                node_counts = audit["node_counts"]
                rel_counts = audit["relationship_counts"]
                total_nodes = sum(node_counts.values()) if isinstance(node_counts, dict) else 0
                total_rels = sum(rel_counts.values()) if isinstance(rel_counts, dict) else 0
                issues = (
                    len(audit["orphan_nodes"])
                    + len(audit["unreachable_constructs"])
                    + len(audit["codelists_without_categories"])
                )
                print(f"\n{'=' * 60}")
                print(" SUMMARY")
                print("=" * 60)
                print(f"  Total nodes: {total_nodes}")
                print(f"  Total relationships: {total_rels}")
                print(f"  Unique relationship patterns: {len(audit['relationship_mapping'])}")
                print(f"  Entry points: {len(audit['entry_points'])}")
                print(f"  Potential issues: {issues}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()

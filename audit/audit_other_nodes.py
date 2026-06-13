#!/usr/bin/env python3
"""Audit how Neo4j nodes are labelled -- explain what shows up as "Other".

Neo4j Browser/Bloom only colours the most common labels and groups the rest
into an "Other" bucket in the legend, so "Other (399)" usually just means
less-frequent DDI labels -- not unlabelled or broken nodes. This script reports
the full picture so you can see exactly what those nodes are, and flags the two
cases that *would* be real problems:

  * nodes with **no label** at all, and
  * nodes carrying a label that is **not part of the DDI schema**.

Usage:
    python audit_other_nodes.py                       # use .env for credentials
    python audit_other_nodes.py --uri bolt://... --user neo4j --password pw
    python audit_other_nodes.py --element-id "4:b677fa4d-...:146"   # inspect one node
    python audit_other_nodes.py --fragment-id "urn:ddi:ie.cso:...:3"
    python audit_other_nodes.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase, Session


def _known_labels() -> set[str] | None:
    """Return the set of labels defined by the DDI schema, if importable."""
    try:
        from ddigraph.schema.definitions import DDISchema
    except ImportError:
        return None
    labels = {
        node.label
        for node in DDISchema.get_all_nodes(include_fragments=True, include_cdi=True)
    }
    # EntryPoint is a marker label added after load, not a fragment type.
    labels.add("EntryPoint")
    return labels


def label_counts(session: Session) -> list[dict[str, Any]]:
    """Count nodes per individual label (a multi-label node counts once per label)."""
    result = session.run(
        """
        MATCH (n)
        UNWIND labels(n) AS label
        RETURN label, count(*) AS count
        ORDER BY count DESC
        """
    )
    return [{"label": r["label"], "count": r["count"]} for r in result]


def label_set_counts(session: Session) -> list[dict[str, Any]]:
    """Count nodes per distinct *combination* of labels (reveals multi-label nodes)."""
    result = session.run(
        """
        MATCH (n)
        WITH labels(n) AS label_set, count(*) AS count
        RETURN label_set, count
        ORDER BY count DESC
        """
    )
    return [{"labels": list(r["label_set"]), "count": r["count"]} for r in result]


def unlabelled_nodes(session: Session, limit: int = 50) -> list[dict[str, Any]]:
    """Nodes with no label at all -- these are genuine problems."""
    result = session.run(
        """
        MATCH (n)
        WHERE size(labels(n)) = 0
        RETURN elementId(n) AS element_id,
               n.fragment_id AS fragment_id,
               n.urn AS urn,
               keys(n) AS keys
        LIMIT $limit
        """,
        limit=limit,
    )
    return [dict(r) for r in result]


def unexpected_label_nodes(
    session: Session, known: set[str], limit: int = 50
) -> list[dict[str, Any]]:
    """Nodes whose label set is not covered by the DDI schema."""
    result = session.run(
        """
        MATCH (n)
        WHERE any(l IN labels(n) WHERE NOT l IN $known)
        WITH labels(n) AS label_set, count(*) AS count
        RETURN label_set, count
        ORDER BY count DESC
        LIMIT $limit
        """,
        known=list(known),
        limit=limit,
    )
    return [{"labels": list(r["label_set"]), "count": r["count"]} for r in result]


def inspect_node(
    session: Session, *, element_id: str | None, fragment_id: str | None
) -> dict[str, Any] | None:
    """Return the labels and properties of a single node by elementId or fragment_id."""
    if element_id is not None:
        query = "MATCH (n) WHERE elementId(n) = $value RETURN n, labels(n) AS labels"
        value = element_id
    elif fragment_id is not None:
        query = "MATCH (n {fragment_id: $value}) RETURN n, labels(n) AS labels"
        value = fragment_id
    else:
        return None
    record = session.run(query, value=value).single()
    if record is None:
        return {"found": False}
    return {
        "found": True,
        "labels": list(record["labels"]),
        "properties": dict(record["n"]),
    }


def run_audit(session: Session, known: set[str] | None) -> dict[str, Any]:
    """Collect the full label audit."""
    per_label = label_counts(session)
    per_set = label_set_counts(session)
    unlabelled = unlabelled_nodes(session)
    unexpected = unexpected_label_nodes(session, known) if known is not None else []
    return {
        "label_counts": per_label,
        "label_set_counts": per_set,
        "unlabelled_nodes": unlabelled,
        "unexpected_label_nodes": unexpected,
        "known_labels_available": known is not None,
        "totals": {
            "distinct_labels": len(per_label),
            "distinct_label_sets": len(per_set),
            "unlabelled": len(unlabelled),
        },
    }


def print_audit(audit: dict[str, Any]) -> None:
    """Pretty-print the audit."""
    print("\n" + "=" * 60)
    print(" NODE COUNTS BY LABEL")
    print("=" * 60)
    for row in audit["label_counts"]:
        print(f"  {row['label']}: {row['count']}")

    print("\n" + "=" * 60)
    print(" NODE COUNTS BY LABEL COMBINATION (multi-label nodes)")
    print("=" * 60)
    for row in audit["label_set_counts"]:
        labels = row["labels"] or ["<no label>"]
        print(f"  {':'.join(labels)}: {row['count']}")

    print("\n" + "=" * 60)
    print(" ⚠️  Nodes with NO label")
    print("=" * 60)
    if audit["unlabelled_nodes"]:
        for row in audit["unlabelled_nodes"]:
            print(f"  {row['element_id']}  keys={row.get('keys')}")
    else:
        print("  none ✅")

    if audit["known_labels_available"]:
        print("\n" + "=" * 60)
        print(" ⚠️  Nodes with a label outside the DDI schema")
        print("=" * 60)
        if audit["unexpected_label_nodes"]:
            for row in audit["unexpected_label_nodes"]:
                print(f"  {':'.join(row['labels'])}: {row['count']}")
        else:
            print("  none ✅")
    else:
        print("\n(Install ddigraph to also flag labels outside the DDI schema.)")

    t = audit["totals"]
    print("\n" + "=" * 60)
    print(" SUMMARY")
    print("=" * 60)
    print(f"  Distinct labels: {t['distinct_labels']}")
    print(f"  Distinct label combinations: {t['distinct_label_sets']}")
    print(f"  Unlabelled nodes: {t['unlabelled']}")
    print(
        "\n  Note: a Neo4j Browser/Bloom legend only colours the most common labels "
        "and groups\n  the rest as \"Other\". The per-label counts above show what "
        "that bucket actually contains."
    )


def main() -> None:
    """Run the label audit."""
    parser = argparse.ArgumentParser(description='Audit node labels ("Other" nodes) in Neo4j')
    parser.add_argument("--uri", help="Neo4j URI (default: from .env)")
    parser.add_argument("--user", help="Neo4j user (default: from .env)")
    parser.add_argument("--password", help="Neo4j password (default: from .env)")
    parser.add_argument(
        "--database", default=None, help="Database name (default: from .env, else neo4j)"
    )
    parser.add_argument("--element-id", help="Inspect a single node by Neo4j elementId")
    parser.add_argument("--fragment-id", help="Inspect a single node by fragment_id")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

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
            print("Error: provide --uri, --user, --password or install ddigraph for .env support")
            sys.exit(1)
    else:
        uri = args.uri
        user = args.user
        password = args.password
        database = args.database or "neo4j"

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            if args.element_id or args.fragment_id:
                node = inspect_node(
                    session, element_id=args.element_id, fragment_id=args.fragment_id
                )
                print(json.dumps(node, indent=2, default=str))
                return

            known = _known_labels()
            audit = run_audit(session, known)
            if args.json:
                print(json.dumps(audit, indent=2, default=str))
            else:
                print_audit(audit)
    finally:
        driver.close()


if __name__ == "__main__":
    main()

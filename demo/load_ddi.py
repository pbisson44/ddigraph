#!/usr/bin/env python3
"""Load DDI XML into Neo4j with auto-detection of format.

Usage:
    python load_ddi.py                     # Load Ireland_LabourSurvey.xml
    python load_ddi.py path/to/file.xml    # Load a specific file

Requires a .env file in this folder with Neo4j credentials:
    DDIGRAPH_NEO4J_URI=bolt://localhost:7687
    DDIGRAPH_NEO4J_USER=neo4j
    DDIGRAPH_NEO4J_PASSWORD=your-password
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from neo4j import AsyncGraphDatabase

from ddigraph import DDIFragmentLoader, DDILoader, detect_ddi_format
from ddigraph.config import Settings
from ddigraph.graph.bootstrap import ensure_schema


async def main() -> None:
    # Determine file to load
    demo_dir = Path(__file__).parent
    if len(sys.argv) > 1:
        ddi_path = Path(sys.argv[1])
    else:
        ddi_path = demo_dir / "Ireland_LFS_Series.xml"

    if not ddi_path.exists():
        print(f"Error: File not found: {ddi_path}")
        sys.exit(1)

    # Load settings from .env
    env_file = demo_dir / ".env"
    settings = Settings(_env_file=env_file) if env_file.exists() else Settings()

    # Detect format
    ddi_format = detect_ddi_format(ddi_path)
    print(f"File: {ddi_path.name}")
    print(f"Format: {ddi_format}")

    # Connect to Neo4j
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    try:
        await driver.verify_connectivity()
        print(f"Connected to: {settings.neo4j_uri}")

        # Bootstrap schema
        include_fragments = ddi_format == "lifecycle"
        await ensure_schema(
            driver,
            database=settings.neo4j_database,
            include_fragments=include_fragments,
        )
        print("Schema ready")

        # Load data
        print("Loading...")
        result: dict[str, int]
        if ddi_format == "lifecycle":
            fragment_loader = DDIFragmentLoader(driver, settings=settings)
            result = await fragment_loader.load(ddi_path)
        else:
            codebook_loader = DDILoader(driver, settings=settings)
            result = await codebook_loader.load(
                ddi_path,
                dataset_id=ddi_path.stem,
                dataset_name=ddi_path.stem.replace("_", " ").title(),
            )

        # Print results
        print("\nResults:")
        for key, count in sorted(result.items()):
            if count > 0:
                print(f"  {key}: {count}")

        # Verify total nodes
        async with driver.session(database=settings.neo4j_database) as session:
            record = await session.run("MATCH (n) RETURN count(n) AS count")
            data = await record.single()
            total = data["count"] if data else 0
        print(f"\nTotal nodes in database: {total}")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())

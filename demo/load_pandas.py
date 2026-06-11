#!/usr/bin/env python3
"""Demo: Load DDI into pandas DataFrames for analysis.

This demonstrates using the adapter pattern to load DDI data into
pandas DataFrames for data analysis and manipulation.

Usage:
    python load_pandas.py [path/to/ddi.xml]

Requirements:
    pip install pandas
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import pandas as pd  # type: ignore[import-untyped]
except ImportError:
    print("Error: pandas required. Install with: pip install pandas")
    sys.exit(1)

from ddigraph.ingest.fragment_loader import (
    DDIFragmentParser,
    FragmentBatch,
)


class PandasFragmentWriter:
    """Collect DDI-L fragments into pandas DataFrames."""

    def __init__(self) -> None:
        self.nodes_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.relationships_data: list[dict[str, Any]] = []

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Collect batch data into lists for DataFrame creation."""
        counts: dict[str, int] = {}

        # Collect nodes by type
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                self.nodes_data[element_type].append(fragment.to_dict())
            counts[element_type] = len(fragments)

        # Collect relationships
        for from_id, rel_type, to_id in batch.relationships:
            self.relationships_data.append(
                {
                    "from_id": from_id,
                    "type": rel_type,
                    "to_id": to_id,
                }
            )
        counts["relationships"] = len(batch.relationships)

        return counts

    def to_dataframes(self) -> dict[str, pd.DataFrame]:
        """Convert collected data to DataFrames."""
        dfs: dict[str, pd.DataFrame] = {}

        # Create DataFrame for each node type
        for node_type, records in self.nodes_data.items():
            if records:
                dfs[node_type] = pd.DataFrame(records)

        # Create relationships DataFrame
        if self.relationships_data:
            dfs["_relationships"] = pd.DataFrame(self.relationships_data)

        return dfs


async def load_to_pandas(ddi_path: Path) -> dict[str, pd.DataFrame]:
    """Load DDI-L file into pandas DataFrames."""
    writer = PandasFragmentWriter()
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

    return writer.to_dataframes()


def analyze_dataframes(dfs: dict[str, pd.DataFrame]) -> None:
    """Analyze the loaded DataFrames."""
    print("\n" + "=" * 60)
    print(" PANDAS DATAFRAME ANALYSIS")
    print("=" * 60)

    # Overview
    print("\nDataFrames Created:")
    for name, df in dfs.items():
        print(f"  {name}: {len(df)} rows, {len(df.columns)} columns")

    # Question analysis
    if "QuestionItem" in dfs:
        df = dfs["QuestionItem"]
        print("\n--- QuestionItem Analysis ---")
        print(f"Total questions: {len(df)}")

        if "response_type" in df.columns:
            print("\nResponse types:")
            print(df["response_type"].value_counts().to_string())

        if "question_text" in df.columns:
            # Average question length
            df["text_length"] = df["question_text"].fillna("").str.len()
            print("\nQuestion text length:")
            print(f"  Mean: {df['text_length'].mean():.0f} chars")
            print(f"  Max: {df['text_length'].max()} chars")

            # Sample questions
            print("\nSample questions:")
            sample = df[df["question_text"].notna()].head(3)
            for _, row in sample.iterrows():
                text = (
                    row["question_text"][:80] + "..."
                    if len(str(row["question_text"])) > 80
                    else row["question_text"]
                )
                print(f"  - {row.get('name', 'unnamed')}: {text}")

    # CodeList analysis
    if "CodeList" in dfs:
        df = dfs["CodeList"]
        print("\n--- CodeList Analysis ---")
        print(f"Total code lists: {len(df)}")

        if "code_count" in df.columns:
            print("\nCodes per list:")
            print(f"  Mean: {df['code_count'].mean():.1f}")
            print(f"  Max: {df['code_count'].max()}")

    # Category analysis
    if "Category" in dfs:
        df = dfs["Category"]
        print("\n--- Category Analysis ---")
        print(f"Total categories: {len(df)}")

    # Relationship analysis
    if "_relationships" in dfs:
        df = dfs["_relationships"]
        print("\n--- Relationship Analysis ---")
        print(f"Total relationships: {len(df)}")
        print("\nBy type:")
        print(df["type"].value_counts().to_string())

    # Control flow analysis
    if "IfThenElse" in dfs:
        df = dfs["IfThenElse"]
        print("\n--- Control Flow Analysis ---")
        print(f"Conditional branches (IfThenElse): {len(df)}")

        if "condition" in df.columns:
            has_condition = df["condition"].notna().sum()
            print(f"  With explicit condition: {has_condition}")


def demonstrate_queries(dfs: dict[str, pd.DataFrame]) -> None:
    """Show example pandas queries."""
    print("\n" + "=" * 60)
    print(" EXAMPLE PANDAS QUERIES")
    print("=" * 60)

    # Join questions with relationships
    if "QuestionItem" in dfs and "_relationships" in dfs:
        questions = dfs["QuestionItem"]
        rels = dfs["_relationships"]

        # Questions that use codelists
        codelist_rels = rels[rels["type"] == "USES_CODELIST"]
        questions_with_codes = questions[questions["fragment_id"].isin(codelist_rels["from_id"])]

        print(f"\nQuestions with CodeLists: {len(questions_with_codes)}")
        print(f"Questions without CodeLists: {len(questions) - len(questions_with_codes)}")

    # Analyze sequences
    if "Sequence" in dfs and "_relationships" in dfs:
        rels = dfs["_relationships"]

        # Count children per sequence
        has_construct = rels[rels["type"] == "HAS_CONSTRUCT"]
        children_per_seq = has_construct.groupby("from_id").size()

        if len(children_per_seq) > 0:
            print("\nSequence complexity:")
            print(f"  Mean children: {children_per_seq.mean():.1f}")
            print(f"  Max children: {children_per_seq.max()}")


def export_to_excel(dfs: dict[str, pd.DataFrame], output_path: Path) -> None:
    """Export DataFrames to Excel workbook."""
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for name, df in dfs.items():
                # Truncate sheet name if needed (Excel limit is 31 chars)
                sheet_name = name[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"\nExported to Excel: {output_path}")
    except ImportError:
        print("\nNote: Install openpyxl for Excel export: pip install openpyxl")


async def main() -> None:
    """Load DDI file and analyze with pandas."""
    # Determine file path
    if len(sys.argv) > 1:
        ddi_path = Path(sys.argv[1])
    else:
        ddi_path = Path(__file__).parent / "Ireland_LabourSurvey.xml"

    if not ddi_path.exists():
        print(f"Error: File not found: {ddi_path}")
        sys.exit(1)

    print(f"File: {ddi_path.name}")
    print("Loading into pandas DataFrames...")

    # Load
    dfs = await load_to_pandas(ddi_path)

    # Analyze
    analyze_dataframes(dfs)

    # Example queries
    demonstrate_queries(dfs)

    # Export
    export_to_excel(dfs, Path("ddi_data.xlsx"))


if __name__ == "__main__":
    asyncio.run(main())

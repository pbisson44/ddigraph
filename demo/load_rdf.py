"""Demo: Load DDI into RDF/SPARQL for semantic web applications.

This demonstrates using the adapter pattern to load DDI data into
RDF (Resource Description Framework) for use with SPARQL queries
and semantic web tools.

Usage:
    python load_rdf.py [path/to/ddi.xml]

Requirements:
    pip install rdflib
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from ddigraph.ingest.fragment_loader import (
    DDIFragmentParser,
    FragmentBatch,
)

# Tuple kept as a named reference because ruff format 0.15.x ``py314``
# target strips parens from inline ``except (A, B):`` clauses and
# produces invalid Python 3 syntax. Aliasing the tuple sidesteps the bug.
_OPTIONAL_RDF_IMPORT_ERRORS: tuple[type[BaseException], ...] = (
    ImportError,
    AttributeError,
)
try:
    rdflib = importlib.import_module("rdflib")
    rdflib_namespace = importlib.import_module("rdflib.namespace")
    Graph = rdflib.Graph
    Literal = rdflib.Literal
    Namespace = rdflib.Namespace
    URIRef = rdflib.URIRef
    RDF = rdflib_namespace.RDF
    RDFS = rdflib_namespace.RDFS
    XSD = rdflib_namespace.XSD
except _OPTIONAL_RDF_IMPORT_ERRORS:
    print("Error: rdflib required. Install with: pip install rdflib")
    sys.exit(1)

ResultRow = Any

# Define DDI namespace for our RDF vocabulary
DDI = Namespace("http://ddialliance.org/ontology#")
DDIDATA = Namespace("http://example.org/ddi/data/")


class RDFFragmentWriter:
    """Write DDI-L fragments to an RDF graph."""

    def __init__(self) -> None:
        """Initialize RDF graph with namespaces."""
        self.graph = Graph()

        # Bind namespaces for readable serialization
        self.graph.bind("ddi", DDI)
        self.graph.bind("ddidata", DDIDATA)
        self.graph.bind("rdf", RDF)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

    def _create_uri(self, fragment_id: str) -> Any:
        """Create URI for a fragment."""
        return DDIDATA[fragment_id.replace(":", "_")]

    def _convert_property_value(self, value: Any) -> Any:
        """Convert Python value to RDF Literal with appropriate datatype."""
        if isinstance(value, bool):
            return Literal(value, datatype=XSD.boolean)
        elif isinstance(value, int):
            return Literal(value, datatype=XSD.integer)
        elif isinstance(value, float):
            return Literal(value, datatype=XSD.double)
        else:
            return Literal(str(value))

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Write a batch of fragments to RDF graph."""
        counts: dict[str, int] = {}

        # Add fragments as RDF resources
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                # Create subject URI
                subject = self._create_uri(fragment.to_dict()["fragment_id"])

                # Add type (rdf:type)
                self.graph.add((subject, RDF.type, DDI[element_type]))

                # Add label if present
                props = fragment.to_dict()
                if props.get("label"):
                    self.graph.add((subject, RDFS.label, Literal(props["label"])))

                # Add all properties as predicates
                for key, value in props.items():
                    if key in ("fragment_id", "label", "element_type"):
                        continue  # Skip metadata fields

                    if value is not None:
                        predicate = DDI[key]
                        obj_literal = self._convert_property_value(value)
                        self.graph.add((subject, predicate, obj_literal))

            counts[element_type] = len(fragments)

        # Add relationships as RDF triples
        for from_id, rel_type, to_id in batch.relationships:
            subject = self._create_uri(from_id)
            predicate = DDI[rel_type]
            obj_ref = self._create_uri(to_id)
            self.graph.add((subject, predicate, obj_ref))

        counts["relationships"] = len(batch.relationships)

        return counts


async def load_to_rdf(ddi_path: Path) -> Any:
    """Load DDI-L file into RDF graph."""
    writer = RDFFragmentWriter()
    parser = DDIFragmentParser(ddi_path)

    totals: dict[str, int] = {}

    for batch in parser.parse_batches():
        counts = await writer.write_batch(batch)
        for key, value in counts.items():
            totals[key] = totals.get(key, 0) + value

    print("\nLoaded:")
    for key, count in sorted(totals.items()):
        if count > 0:
            print(f"  {key}: {count}")

    return writer.graph


def analyze_rdf_graph(g: Any) -> None:
    """Analyze the RDF graph with basic statistics."""
    print("\n" + "=" * 60)
    print(" RDF GRAPH ANALYSIS")
    print("=" * 60)

    print("\nBasic Stats:")
    print(f"  Total triples: {len(g)}")

    # Count subjects (unique resources)
    subjects = set(g.subjects())
    print(f"  Unique resources: {len(subjects)}")

    # Count by rdf:type
    type_query = """
        SELECT ?type (COUNT(?s) as ?count)
        WHERE {
            ?s rdf:type ?type .
        }
        GROUP BY ?type
        ORDER BY DESC(?count)
    """

    print("\nResources by Type:")
    for row in cast(Iterable[ResultRow], g.query(type_query)):
        type_name = str(row.type).replace(str(DDI), "ddi:")
        print(f"  {type_name}: {row.count}")

    # Count predicates
    predicates = set(g.predicates())
    print(f"\nUnique predicates: {len(predicates)}")

    # Count relationship types (excluding rdf:type, rdfs:label, and properties)
    rel_query = """
        SELECT ?predicate (COUNT(*) as ?count)
        WHERE {
            ?s ?predicate ?o .
            FILTER(STRSTARTS(STR(?predicate), STR(ddi:)))
            FILTER(?predicate NOT IN (rdf:type, rdfs:label))
            FILTER(isURI(?o))
        }
        GROUP BY ?predicate
        ORDER BY DESC(?count)
        LIMIT 10
    """

    print("\nTop Relationships:")
    for row in cast(Iterable[ResultRow], g.query(rel_query)):
        pred_name = str(row.predicate).replace(str(DDI), "ddi:")
        print(f"  {pred_name}: {row.count}")


def demonstrate_sparql_queries(g: Any) -> None:
    """Demonstrate useful SPARQL queries."""
    print("\n" + "=" * 60)
    print(" SPARQL QUERY EXAMPLES")
    print("=" * 60)

    # Query 1: Find all Instruments (entry points)
    print("\n--- Query 1: Find Instruments ---")
    query1 = """
        SELECT ?instrument ?label
        WHERE {
            ?instrument rdf:type ddi:Instrument .
            OPTIONAL { ?instrument rdfs:label ?label }
        }
    """
    results = list(cast(Iterable[ResultRow], g.query(query1)))
    print(f"Found {len(results)} instrument(s)")
    for row in results[:3]:
        label = row.label if row.label else "No label"
        print(f"  {label}")

    # Query 2: Find all QuestionItems with their text
    print("\n--- Query 2: Sample QuestionItems ---")
    query2 = """
        SELECT ?question ?label ?text
        WHERE {
            ?question rdf:type ddi:QuestionItem .
            OPTIONAL { ?question rdfs:label ?label }
            OPTIONAL { ?question ddi:question_text ?text }
        }
        LIMIT 5
    """
    for row in cast(Iterable[ResultRow], g.query(query2)):
        label = row.label if row.label else "unnamed"
        text = (
            (str(row.text)[:60] + "...")
            if row.text and len(str(row.text)) > 60
            else (row.text or "No text")
        )
        print(f"  {label}: {text}")

    # Query 3: Find questions with their codelists (using graph pattern)
    print("\n--- Query 3: Questions with CodeLists ---")
    query3 = """
        SELECT ?question ?questionLabel ?codelist ?codelistLabel
        WHERE {
            ?question rdf:type ddi:QuestionItem .
            ?question ddi:USES_CODELIST ?codelist .
            ?codelist rdf:type ddi:CodeList .
            OPTIONAL { ?question rdfs:label ?questionLabel }
            OPTIONAL { ?codelist rdfs:label ?codelistLabel }
        }
        LIMIT 5
    """
    results = list(cast(Iterable[ResultRow], g.query(query3)))
    print(f"Found {len(results)} question-codelist pairs (showing first 5)")
    for row in results[:5]:
        q_label = row.questionLabel if row.questionLabel else "unnamed"
        c_label = row.codelistLabel if row.codelistLabel else "unnamed"
        print(f"  {q_label} -> {c_label}")

    # Query 4: Path queries - questions 2 hops from Instrument
    print("\n--- Query 4: Control Flow Depth ---")
    query4 = """
        SELECT (COUNT(DISTINCT ?question) as ?count)
        WHERE {
            ?instrument rdf:type ddi:Instrument .
            ?instrument ?p1 ?middle .
            ?middle ?p2 ?question .
            ?question rdf:type ddi:QuestionItem .
        }
    """
    for row in cast(Iterable[ResultRow], g.query(query4)):
        print(f"  Questions 2 hops from Instrument: {row.count}")

    # Query 5: Sequences with most constructs
    print("\n--- Query 5: Largest Sequences ---")
    query5 = """
        SELECT ?sequence ?label (COUNT(?construct) as ?constructCount)
        WHERE {
            ?sequence rdf:type ddi:Sequence .
            ?sequence ddi:HAS_CONSTRUCT ?construct .
            OPTIONAL { ?sequence rdfs:label ?label }
        }
        GROUP BY ?sequence ?label
        ORDER BY DESC(?constructCount)
        LIMIT 5
    """
    results = list(cast(Iterable[ResultRow], g.query(query5)))
    if results:
        print("  Top sequences by construct count:")
        for row in results:
            label = row.label if row.label else "unnamed"
            print(f"    {label}: {row.constructCount} constructs")


def export_rdf(g: Any, output_base: Path) -> None:
    """Export RDF graph to various formats."""
    print("\n" + "=" * 60)
    print(" RDF EXPORT")
    print("=" * 60)

    # Turtle format (human-readable)
    turtle_path = output_base.with_suffix(".ttl")
    g.serialize(destination=turtle_path, format="turtle")
    print(f"\nTurtle format: {turtle_path}")
    print("  (Human-readable RDF syntax)")

    # N-Triples format (simple, line-oriented)
    nt_path = output_base.with_suffix(".nt")
    g.serialize(destination=nt_path, format="nt")
    print(f"\nN-Triples format: {nt_path}")
    print("  (Simple triple-per-line format)")

    # RDF/XML format (XML serialization)
    xml_path = output_base.with_suffix(".rdf")
    g.serialize(destination=xml_path, format="xml")
    print(f"\nRDF/XML format: {xml_path}")
    print("  (W3C standard XML format)")

    # JSON-LD format (JSON for linked data)
    try:
        jsonld_path = output_base.with_suffix(".jsonld")
        g.serialize(destination=jsonld_path, format="json-ld")
        print(f"\nJSON-LD format: {jsonld_path}")
        print("  (JSON for Linked Data)")
    except Exception:
        print("\nNote: JSON-LD export requires rdflib-jsonld: pip install rdflib-jsonld")

    # Show sample Turtle output
    print("\n--- Sample Turtle Output (first 20 lines) ---")
    turtle_str = g.serialize(format="turtle")
    lines = turtle_str.split("\n")[:20]
    for line in lines:
        print(line)
    if len(turtle_str.split("\n")) > 20:
        print("  ...")


def demonstrate_ontology() -> None:
    """Explain the DDI RDF ontology mapping."""
    print("\n" + "=" * 60)
    print(" DDI RDF ONTOLOGY")
    print("=" * 60)
    print(
        """
The DDI fragments are mapped to RDF using this ontology:
 
Namespaces:
  ddi:      http://ddialliance.org/ontology#
  ddidata:  http://example.org/ddi/data/
 
Resource URIs:
  Each fragment: ddidata:<fragment_id>
 
Types (rdf:type):
  ddi:Instrument, ddi:QuestionItem, ddi:CodeList, etc.
 
Properties:
  Fragment properties -> ddi:<property_name>
  Examples: ddi:question_text, ddi:response_type, ddi:name
 
Relationships:
  Fragment references -> ddi:<relationship_type>
  Examples: ddi:USES_CODELIST, ddi:HAS_CONSTRUCT, ddi:ASKS_QUESTION
 
Example triple:
  ddidata:q1 rdf:type ddi:QuestionItem .
  ddidata:q1 rdfs:label "What is your age?" .
  ddidata:q1 ddi:question_text "What is your age?" .
  ddidata:q1 ddi:USES_CODELIST ddidata:cl1 .
 
This allows SPARQL queries like:
  SELECT ?question WHERE {
    ?question rdf:type ddi:QuestionItem .
    ?question ddi:USES_CODELIST ?codelist .
  }
"""
    )


async def main() -> None:
    """Load DDI file and analyze with RDF/SPARQL."""
    # Determine file path
    if len(sys.argv) > 1:
        ddi_path = Path(sys.argv[1])
    else:
        ddi_path = Path(__file__).parent / "Ireland_LabourSurvey.xml"

    if not ddi_path.exists():
        print(f"Error: File not found: {ddi_path}")
        sys.exit(1)

    print(f"File: {ddi_path.name}")
    print("Loading into RDF graph...")

    # Load
    graph = await load_to_rdf(ddi_path)

    # Analyze
    analyze_rdf_graph(graph)

    # SPARQL queries
    demonstrate_sparql_queries(graph)

    # Explain ontology
    demonstrate_ontology()

    # Export
    output_path = Path("ddi_graph")
    export_rdf(graph, output_path)

    print("\n" + "=" * 60)
    print("Use these files with:")
    print("  - Apache Jena for SPARQL queries")
    print("  - Protégé for ontology visualization")
    print("  - Any triplestore (Virtuoso, GraphDB, Stardog, etc.)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

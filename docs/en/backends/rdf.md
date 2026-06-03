# RDF/SPARQL Backend

ddigraph can export DDI metadata to RDF triples for use with SPARQL endpoints and semantic web tools.

## Overview

The RDF backend converts DDI entities into RDF triples using standard vocabularies:

- **DDI-RDF**: DDI Alliance's RDF vocabulary (when available)
- **Dublin Core**: Standard metadata terms
- **SKOS**: For code lists and categories
- **Custom namespace**: For DDI-specific properties

## Dependencies

RDFLib is included with ddigraph:

```bash
pip install ddigraph  # includes rdflib
```

For remote SPARQL endpoints, you may need additional drivers:

```bash
pip install sparqlwrapper  # for remote SPARQL queries
```

## Basic Usage

### Parse DDI to RDF

```python
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS
from ddigraph import DDIFragmentParser

# Define namespaces
DDI = Namespace("http://ddi.example.org/")
DATA = Namespace("http://data.example.org/")

g = Graph()
g.bind("ddi", DDI)
g.bind("data", DATA)
g.bind("skos", SKOS)
g.bind("dcterms", DCTERMS)

# Parse DDI and create triples
parser = DDIFragmentParser()
for fragment in parser.parse("survey.xml"):
    subj = DATA[fragment.fragment_id]

    # Type triple
    g.add((subj, RDF.type, DDI[fragment.element_type]))

    # Label
    if fragment.label:
        g.add((subj, RDFS.label, Literal(fragment.label)))

    # URN as identifier
    if fragment.urn:
        g.add((subj, DCTERMS.identifier, Literal(fragment.urn)))

    # Relationships
    for rel_type, ref in fragment.references:
        obj = DATA[ref.id]
        g.add((subj, DDI[rel_type], obj))

# Serialize
print(g.serialize(format="turtle"))
```

### Export Formats

```python
# Turtle (human-readable)
g.serialize("output.ttl", format="turtle")

# N-Triples (streaming)
g.serialize("output.nt", format="nt")

# RDF/XML
g.serialize("output.rdf", format="xml")

# JSON-LD
g.serialize("output.jsonld", format="json-ld")
```

## Full Example

See `demo/load_rdf.py` for a complete example:

```python
"""Load DDI into RDF graph and perform SPARQL queries."""

from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, XSD

from ddigraph.ingest.fragment_loader import DDIFragmentParser

DDI = Namespace("http://ddialliance.org/Specification/DDI-Lifecycle/3.3/")
DATA = Namespace("http://example.org/data/")


def load_ddi_to_rdf(ddi_path: str) -> Graph:
    """Parse DDI-L file and create RDF graph."""
    g = Graph()
    g.bind("ddi", DDI)
    g.bind("data", DATA)
    g.bind("skos", SKOS)

    parser = DDIFragmentParser()

    for fragment in parser.parse(ddi_path):
        subj = DATA[fragment.fragment_id]

        # Node type
        g.add((subj, RDF.type, DDI[fragment.element_type]))

        # Properties
        if fragment.label:
            g.add((subj, RDFS.label, Literal(fragment.label)))
        if fragment.urn:
            g.add((subj, DDI.urn, Literal(fragment.urn)))

        # Special handling for QuestionItems
        if fragment.element_type == "QuestionItem":
            props = fragment.to_dict()
            if props.get("question_text"):
                g.add((subj, DDI.questionText, Literal(props["question_text"])))

        # Categories as SKOS concepts
        if fragment.element_type == "Category":
            g.add((subj, RDF.type, SKOS.Concept))
            props = fragment.to_dict()
            if props.get("category_label"):
                g.add((subj, SKOS.prefLabel, Literal(props["category_label"])))

        # Relationships
        for rel_type, ref in fragment.references:
            obj = DATA[ref.id]
            g.add((subj, DDI[rel_type], obj))

    return g


def main():
    ddi_file = "data/Ireland_LabourSurvey.xml"

    g = load_ddi_to_rdf(ddi_file)
    print(f"Created {len(g)} triples")

    # Export
    g.serialize("output.ttl", format="turtle")

    # Query
    query = """
    PREFIX ddi: <http://ddialliance.org/Specification/DDI-Lifecycle/3.3/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?item ?label ?text
    WHERE {
        ?item a ddi:QuestionItem .
        OPTIONAL { ?item rdfs:label ?label }
        OPTIONAL { ?item ddi:questionText ?text }
    }
    LIMIT 10
    """

    for row in g.query(query):
        print(f"{row.label}: {row.text}")


if __name__ == "__main__":
    main()
```

## SPARQL Queries

### Local Queries

```python
# Count by type
query = """
SELECT ?type (COUNT(?s) AS ?count)
WHERE { ?s a ?type }
GROUP BY ?type
ORDER BY DESC(?count)
"""

for row in g.query(query):
    print(f"{row.type}: {row.count}")
```

### Find Questions with Code Lists

```sparql
PREFIX ddi: <http://ddialliance.org/Specification/DDI-Lifecycle/3.3/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?question ?questionText ?codeList
WHERE {
    ?question a ddi:QuestionItem ;
              ddi:questionText ?questionText ;
              ddi:USES_CODELIST ?codeList .
}
```

### Traverse Control Flow

```sparql
PREFIX ddi: <http://ddialliance.org/Specification/DDI-Lifecycle/3.3/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?instrument ?construct ?constructType
WHERE {
    ?instrument a ddi:Instrument ;
                ddi:HAS_CONSTRUCT+ ?construct .
    ?construct a ?constructType .
}
```

## Remote SPARQL Endpoints

### Loading to a Triplestore

```python
from SPARQLWrapper import SPARQLWrapper

# Virtuoso example
sparql = SPARQLWrapper("http://localhost:8890/sparql")
sparql.setMethod("POST")

# Insert data
insert_query = """
INSERT DATA {
    GRAPH <http://example.org/ddi/> {
        %s
    }
}
""" % g.serialize(format="nt")

sparql.setQuery(insert_query)
sparql.query()
```

### Querying Remote Endpoints

```python
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:8890/sparql")
sparql.setReturnFormat(JSON)

sparql.setQuery("""
    SELECT ?s ?p ?o
    FROM <http://example.org/ddi/>
    WHERE { ?s ?p ?o }
    LIMIT 100
""")

results = sparql.query().convert()
for result in results["results"]["bindings"]:
    print(result)
```

## DDI-RDF Vocabulary

ddigraph uses semantic relationship types that map to DDI concepts:

| ddigraph Relationship | RDF Property | Description |
| --------------------- | ------------ | ----------- |
| `HAS_CONSTRUCT` | `ddi:hasConstruct` | Sequence contains construct |
| `USES_CODELIST` | `ddi:usesCodeList` | Question uses code list |
| `HAS_CATEGORY` | `ddi:hasCategory` | CodeList contains category |
| `ASKS_QUESTION` | `ddi:asksQuestion` | Construct references question |
| `USES_CONCEPT` | `ddi:usesConcept` | Entity references concept |

## Integration with Linked Data

### Linking to External Vocabularies

```python
from rdflib import OWL

# Link categories to external vocabularies
g.add((DATA["category-1"], OWL.sameAs, URIRef("http://eurovoc.europa.eu/123")))

# Use standard ontologies
g.add((DATA["variable-1"], DCTERMS.subject, URIRef("http://dbpedia.org/resource/Employment")))
```

### Publishing as Linked Data

```python
# Add VoID dataset description
VOID = Namespace("http://rdfs.org/ns/void#")

dataset = DATA["dataset"]
g.add((dataset, RDF.type, VOID.Dataset))
g.add((dataset, DCTERMS.title, Literal("DDI Survey Metadata")))
g.add((dataset, VOID.sparqlEndpoint, URIRef("http://example.org/sparql")))
```

## See Also

- [Adapter Architecture](../user-guide/adapter.md) - Building custom adapters
- [Relationship Model](../user-guide/relationships.md) - DDI relationship types
- [DDI-RDF Vocabulary](https://ddi-alliance.atlassian.net/wiki/spaces/DDI4/pages/932085774/RDF) - Official DDI-RDF specification

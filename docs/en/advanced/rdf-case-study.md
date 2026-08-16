# Case study: publishing a code list as linked data

A statistical agency has a labour force survey documented in DDI. Someone
outside the agency wants to know whether the survey's employment-status
categories mean the same thing as theirs.

Nothing in the DDI file answers that. This page walks through making it
answerable, using only the `ddigraph` command line and a small DDI file.

Every code block below runs. They are executed as part of the test suite,
against a fixture that ships with the repository.

## The starting point

The survey is a DDI-L file. Ask what is in it:

<!-- runnable -->
```bash
ddigraph detect "$FIXTURE"
```

## Step 1: turn it into RDF

<!-- runnable -->
```bash
ddigraph export "$FIXTURE" --format turtle -o survey.ttl
head -20 survey.ttl
```

Two things in that output matter.

The subjects are DDI URNs. `urn:ddi:test.org:cat1:1.0` is the identifier
the agency already assigned. ddigraph does not invent a new one, so the
same object keeps the same name wherever it travels.

The categories are `skos:Concept`, and they point at their code list with
`skos:inScheme`. Any SKOS tool understands that, with no knowledge of DDI.

## Step 2: check it is what you think

Shapes come from the same schema that builds the Neo4j constraints:

<!-- runnable -->
```bash
ddigraph export "$FIXTURE" --format turtle -o survey.ttl
ddigraph shapes -o shapes.ttl --flavor lifecycle
python - <<'PY'
import pyshacl
import rdflib

data = rdflib.Graph().parse("survey.ttl", format="turtle")
shapes = rdflib.Graph().parse("shapes.ttl", format="turtle")
conforms, _graph, report = pyshacl.validate(data, shacl_graph=shapes)
print("conforms:", conforms)
assert conforms, report
PY
```

Send `shapes.ttl` along with the data and the recipient can run the same
check before trusting it.

## Step 3: answer the actual question

The original question was whether two code lists agree. That is a SPARQL
query now:

<!-- runnable -->
```python
import os

import rdflib

import ddigraph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")
graph = rdflib.Graph().parse("survey.ttl", format="turtle")

rows = graph.query("""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?scheme ?label
    WHERE {
        ?concept skos:inScheme ?scheme ;
                 skos:prefLabel ?label .
    }
    ORDER BY ?label
""")

for scheme, label in rows:
    print(f"{label} -> {scheme}")
```

If the DDI file records external references for its categories, those
become `skos:exactMatch`. That is the link that says "this category is the
same as EuroVoc's", and it is what makes the answer machine-checkable
rather than a matter of reading two PDFs.

## Step 4: keep the graph

The RDF is not a dead end. It reads back:

<!-- runnable -->
```python
import os

import ddigraph
from ddigraph.rdf.reader import read_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

labels = sorted({node.label for chunk in read_graph("survey.ttl") for node in chunk.nodes})
print("recovered types:", labels)
```

So a colleague can send you Turtle, and you can load it into Neo4j exactly
as if it had been the original XML:

```bash
ddigraph load survey.ttl
```

## Why the details matter

Two things in the output above are easy to get wrong, and both decide
whether the result is worth sending to anyone.

The predicate is a published term, not a relationship name. Emitting
`ddi:USES_CODELIST` would carry a database convention into a format meant
for exchange, and no consumer would recognise it.

The subject keeps its URN intact. Flattening
`urn:ddi:test.org:cat1:1.0` into something like
`urn_ddi_test.org_cat1_1.0` destroys the one identifier the DDI world
already agrees on.

Get either wrong and the file still parses — it simply joins to nothing.

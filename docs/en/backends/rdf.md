# RDF and SPARQL

ddigraph reads and writes RDF. You can turn a DDI file into Turtle,
JSON-LD, N-Triples or RDF/XML, check it against SHACL shapes, and read it
back again.

## Install

RDF support is an optional extra:

```bash
pip install "ddigraph[rdf]"
```

Add SHACL validation with:

```bash
pip install "ddigraph[shacl]"
```

## Export a file

No database is needed. The `export` command reads DDI and writes a file:

```bash
ddigraph export survey.xml --format turtle -o survey.ttl
```

It works on all three DDI flavors: Codebook, Lifecycle, and CDI. Other
formats are `ntriples`, `jsonld`, `rdfxml`, `json` and `csv`. The `json`
and `csv` formats need no extra at all.

From Python:

<!-- runnable -->
```python
import os

import ddigraph

result = ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")
print(result.nodes, "nodes,", result.triples, "triples")
```

## The vocabulary

Every graph uses one namespace, and that namespace has its own version:

```text
https://pbisson44.github.io/ddigraph/ns/1.0/
```

The version belongs to the vocabulary, not to the package. It changes only
when a term changes meaning, so a query you write today keeps working.

That IRI resolves. Open it and you get the
[vocabulary reference](../ns/1.0.md), with
[vocabulary.ttl](../ns/vocabulary.ttl) beside it — every class and
predicate, generated from the same schema that drives the exporter.

### Published terms come first

Where the DDI Alliance or the wider linked-data world already has a term,
ddigraph uses it. That is what lets your data join to other people's data.

| DDI concept | RDF class |
| --- | --- |
| Study, StudyUnit | `disco:Study` |
| Variable | `disco:Variable` |
| Question, QuestionItem | `disco:Question` |
| Universe | `disco:Universe` |
| DataFile | `disco:DataFile` |
| CodeList, CodeScheme | `skos:ConceptScheme` |
| Category, Concept | `skos:Concept` |
| CategoryGroup | `xkos:ClassificationLevel` |
| Organization | `foaf:Organization` |

[DISCO][disco] is the DDI Alliance's own RDF vocabulary, built from DDI
Codebook and DDI Lifecycle. [XKOS][xkos] extends SKOS for statistical
classifications.

DDI has about 250 node types and DISCO defines 16 classes. Everything with
no published equivalent gets a term in the ddigraph namespace.

### Every node carries two types

A node gets the published class *and* a ddigraph class:

```turtle
<urn:ddi:ie.cso:q-4711:1.0.0>
    a disco:Question , ddigraph:QuestionItem ;
    skos:prefLabel "Main activity status"@en-IE .
```

The published class is what other tools read. The ddigraph class says which
DDI type it really was. Both `Question` and `QuestionItem` map to
`disco:Question`, so without the second type you could not tell them apart
again.

### Predicates

Relationship names are `lowerCamelCase`. A `HAS_CONSTRUCT` edge in the graph
becomes `ddigraph:hasConstruct` in RDF. Where a published predicate exists,
it is used instead:

| Graph relationship | RDF predicate |
| --- | --- |
| `USES_CONCEPT` | `disco:concept` |
| `ASKS_QUESTION` | `disco:question` |
| `USES_CODELIST` | `disco:responseDomain` |
| `IN_DATASET` | `dcterms:isPartOf` |
| `HAS_CATEGORY` | `skos:inScheme` |

### Subject IRIs

DDI URNs are reused as-is when a record has one:

```text
urn:ddi:ie.cso:q-4711:1.0.0
```

A URN is already unique worldwide, so nothing is gained by minting a new
IRI. Records with no URN get a `urn:ddigraph:` identifier. Pass
`--base-uri` to use your own namespace when you publish:

```bash
ddigraph export survey.xml --format turtle -o out.ttl \
  --base-uri https://example.org/id/
```

## Code lists are SKOS

Code lists and categories are the part of DDI most likely to be useful
outside DDI. They come out as proper SKOS:

```turtle
<urn:ddi:test.org:cl1:1.0>
    a skos:ConceptScheme , ddigraph:CodeList ;
    skos:prefLabel "Age Groups" .

<urn:ddi:test.org:cat1:1.0>
    a skos:Concept , ddigraph:Category ;
    skos:inScheme <urn:ddi:test.org:cl1:1.0> ;
    skos:prefLabel "Under 18" .
```

Note the direction. The DDI file nests categories inside a code list, but
SKOS puts the link on the member, as `skos:inScheme`. `skos:member` belongs
to `skos:Collection`, not to `skos:ConceptScheme`.

External references become `skos:exactMatch`. That is the link you use to
join a code list to EuroVoc, DBpedia or any other published vocabulary.

## Query with SPARQL

Once a file is loaded into rdflib you can query it:

<!-- runnable -->
```python
import os

import rdflib

import ddigraph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

graph = rdflib.Graph().parse("survey.ttl", format="turtle")
rows = graph.query("""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?category ?label ?scheme
    WHERE {
        ?category a skos:Concept ;
                  skos:prefLabel ?label ;
                  skos:inScheme ?scheme .
    }
""")

for category, label, scheme in rows:
    print(label, "in", scheme)
```

The same file loads into any triple store: Jena, GraphDB, Virtuoso,
Stardog, Blazegraph.

## Validate with SHACL

`ddigraph shapes` writes SHACL shapes for the vocabulary. They come from
the same schema that builds the Neo4j constraints, so they cannot drift:

```bash
ddigraph shapes -o shapes.ttl --flavor lifecycle
```

Pass `--flavor` when you validate real data. A file has exactly one flavor,
and 21 DDI type names appear in more than one flavor with different keys.

<!-- runnable -->
```python
import os

import pyshacl
import rdflib

import ddigraph
from ddigraph.rdf.shacl import shapes_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

data = rdflib.Graph().parse("survey.ttl", format="turtle")
conforms, _report_graph, report = pyshacl.validate(
    data, shacl_graph=shapes_graph(flavor="lifecycle")
)

print("conforms:", conforms)
assert conforms, report
```

## Read RDF back

RDF is an input format too. `read_graph` parses Turtle, JSON-LD, N-Triples
and RDF/XML into the same shape the DDI parsers produce:

<!-- runnable -->
```python
import os

import ddigraph
from ddigraph.rdf.reader import read_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

nodes = [node for chunk in read_graph("survey.ttl") for node in chunk.nodes]
print(len(nodes), "nodes read back")
print(sorted({node.label for node in nodes}))
```

The round trip loses nothing. Export a file, read it back, export it again,
and you get the same triples.

You can also load RDF straight into Neo4j:

```bash
ddigraph export survey.xml --format turtle -o out.ttl
ddigraph load out.ttl
```

The reader ignores subjects with no ddigraph type. Point it at unrelated
RDF and you get nothing back, rather than nonsense.

## Build your own graph

`iter_graph` gives you the nodes and relationships directly, for any DDI
flavor. Use it when you want to drive a store ddigraph does not support:

<!-- runnable -->
```python
import os

from ddigraph import iter_graph

for chunk in iter_graph(os.environ["CDI_FIXTURE"]):
    for node in chunk.nodes:
        print(node.label, node.identity)
    for edge in chunk.relationships:
        print(edge.start.label, "-", edge.type, "->", edge.end.label)
```

[disco]: https://rdf-vocabulary.ddialliance.org/discovery.html
[xkos]: https://rdf-vocabulary.ddialliance.org/xkos.html

# Lesson 4 — Joining the wider world

!!! abstract "What you will learn"
    - Export a DDI file as RDF that other systems can read
    - Read the two-type trick that makes the export reversible
    - Query an export with SPARQL

This lesson needs the RDF extra: `pip install "ddigraph[rdf]"`.

## The problem with your own vocabulary

A graph in your database is useful to you. A graph other people can join
to is useful to everyone. That is what RDF is for: a shared way of saying
"this thing is a question, and it uses that code list", where *question*
and *uses* mean the same to every reader.

The catch is that "shared" only works if you use terms other people already
use. Invent your own and you have XML with extra steps.

The failure mode looks like this, and it is common enough to be worth
recognising:

```text
ddi:USES_CODELIST      # a Neo4j relationship name
ddi:question_text      # a Python attribute name
```

Both leak an internal naming convention into a format whose entire purpose
is to be external — one from the database, one from the source code. And a
`ddi:` prefix pointing at a domain you do not control cannot be looked up
by anyone. Output like that joins to nothing.

## Three layers

The fix has three parts, and every RDF vocabulary worth using does
something like this.

**Reuse published terms.** The DDI Alliance publishes RDF vocabularies —
DISCO for studies, variables and questions; XKOS for classifications. Code
lists map onto SKOS, the standard for controlled vocabularies. Where a term
exists, use it.

**Mint one namespace for the rest.** DISCO defines 16 classes; DDI has
about 250 concepts. The remainder need terms, and they live under one
namespace that [resolves to a page describing them](../ns/1.0.md).

**Emit both types.** Explained below — it is the interesting part.

## Your first export

<!-- runnable -->
```python
import os

import ddigraph

result = ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")
print(result.nodes, "nodes ->", result.triples, "triples")
```

Look at what came out for the question:

```turtle
<urn:ddi:test.org:q1:1.0> a disco:Question,
        ddigraph:QuestionItem ;
    rdfs:label "Question 1" ;
    dcterms:identifier "urn:ddi:test.org:q1:1.0" ;
    dcterms:publisher "test.org" ;
    disco:questionText "What is your age?" .
```

Three things to notice.

**The subject is the DDI URN** from lesson 1 — `urn:ddi:test.org:q1:1.0`.
Not a made-up URL. It is already globally unique, so there is nothing to
invent.

**The predicates are published terms.** `disco:questionText`,
`dcterms:publisher`, `rdfs:label`. No `USES_CODELIST` anywhere.

**There are two types.** `disco:Question` *and* `ddigraph:QuestionItem`.

## Why two types

That last one looks redundant. It is not, and the reason is worth
understanding because it is what makes the round trip work.

The mapping to standard classes is **many-to-one**:

| ddigraph label | Standard class |
| ---------------- | ---------------- |
| `Question` | `disco:Question` |
| `QuestionItem` | `disco:Question` |
| `CodeScheme` | `skos:ConceptScheme` |
| `CodeList` | `skos:ConceptScheme` |
| `CategoryScheme` | `skos:ConceptScheme` |

Given only `disco:Question`, you cannot tell whether it started as a
`Question` or a `QuestionItem`. The information is gone.

So every node carries both: the standard class for anyone else, and the
project class for identity. A consumer doing interoperability reads
`disco:Question` and ignores the other. The ddigraph reader reads
`ddigraph:QuestionItem` and rebuilds the original graph exactly.

That is why this works:

```bash
ddigraph export survey.xml --format turtle -o out.ttl
ddigraph load out.ttl        # straight back in, nothing lost
```

## Code lists become SKOS

Controlled vocabularies get special treatment, because SKOS is the
best-supported standard in this whole space. A `CodeList` becomes a
`skos:ConceptScheme`, and each `Category` a `skos:Concept`:

<!-- runnable -->
```python
import os

import rdflib

import ddigraph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

graph = rdflib.Graph().parse("survey.ttl", format="turtle")
rows = graph.query("""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    SELECT ?concept ?label
    WHERE { ?concept a skos:Concept ; skos:prefLabel ?label }
""")
for concept, label in rows:
    print(concept, "->", label)
```

```text
urn:ddi:test.org:cat1:1.0 -> Under 18
```

That is a SPARQL query against your survey metadata, using a vocabulary
that thesaurus tools, EuroVoc and the whole SKOS ecosystem already speak.

!!! note "Direction is not decoration"
    The graph says `CodeList -HAS_CATEGORY-> Category`, because that is how
    the XML nests. SKOS says the opposite: the *concept* carries
    `skos:inScheme` pointing at its scheme, and `skos:member` belongs to
    `skos:Collection`, not `skos:ConceptScheme`.

    So the exporter swaps subject and object for those edges. Emitting the
    graph direction verbatim would produce SKOS that validators reject —
    correct-looking triples that say the scheme is inside the concept.

## Exercise

Export the Codebook fixture and count how many distinct RDF types it uses.
Then count how many of those are project-namespace types rather than
published ones.

??? success "Solution"
    ```python
    import os

    import rdflib

    import ddigraph
    from ddigraph.rdf.vocabulary import DDIGRAPH

    ddigraph.export(os.environ["CODEBOOK_FIXTURE"], "cb.ttl", format="turtle")
    graph = rdflib.Graph().parse("cb.ttl", format="turtle")

    types = {str(t) for t in graph.objects(None, rdflib.RDF.type)}
    project = {t for t in types if t.startswith(DDIGRAPH)}

    print(len(types), "types,", len(project), "of them project-namespace")
    ```

    Most will be project-namespace, and that is expected: DISCO covers 16
    classes against DDI's ~250. The published terms carry the concepts
    other people care about — studies, variables, questions, code lists —
    and the rest are still recorded rather than dropped.

## Check yourself

- Why is the subject IRI a DDI URN rather than a URL under your domain?
- What breaks if you emit only the standard `rdf:type`?
- Why does the exporter reverse the direction of `HAS_CATEGORY`?

---

Next: [Proving it is right](05-validation.md) — checking an export against
machine-readable rules.

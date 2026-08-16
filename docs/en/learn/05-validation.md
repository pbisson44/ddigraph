# Lesson 5 — Proving it is right

!!! abstract "What you will learn"
    - Check a DDI file against the official XSD before you trust it
    - Check an RDF export against SHACL shapes after you produce it
    - Tell the two apart, and know which one answers which question

This lesson needs `pip install "ddigraph[shacl]"`.

## Two different questions

There are two moments where "is this right?" is worth asking, and they need
different tools.

**Before.** Is this file valid DDI? That is a question about the XML, and
the answer comes from the XSD the DDI Alliance publishes.

**After.** Is what I produced valid RDF, with the right classes and the
required properties? That is a question about the graph, and the answer
comes from SHACL shapes.

Neither substitutes for the other. A perfectly valid DDI file can produce
nonsense RDF if the exporter is wrong. A perfect export can come from a
file that never conformed to anything.

## Before: XSD

The package ships the official schemas — 154 XSD files across Codebook 2.6,
Lifecycle 3.1 through 3.3, and CDI 1.0. `ddigraph validate` picks the right
one:

<!-- runnable -->
```bash
ddigraph validate "$FIXTURE" --max-issues 3 || true
```

```text
File:   fragment_instance.xml
Flavor: lifecycle 3.3
Schema: instance_3_3.xsd
Result: invalid (3 issue(s))
  line 8: Element '{ddi:datacollection:3_3}Instrument', attribute 'id': The attribute 'id' is not allowed.
```

It picked `instance_3_3.xsd` on its own. The flavor came from the root
element; the *version* came from the namespace the document declares —
`ddi:datacollection:3_3`. Validating DDI-L 3.3 against the 3.1 schema would
produce a page of nonsense, so it is not left to you to remember.

The same from Python:

<!-- runnable -->
```python
import os

from ddigraph.validation import validate

result = validate(os.environ["FIXTURE"], max_issues=3)

print("valid:", result.valid)
print("schema:", result.schema.name)
for issue in result.issues:
    print(" ", issue)
```

!!! warning "That fixture really is invalid, and that is the point"
    Every XML fixture in this repository fails XSD validation. They are
    synthetic — written to exercise the parsers, not to conform. The
    Codebook one is a bare `<codeBook>` with no namespace at all.

    A good deal of published DDI is in the same position: it parses, it
    loads, it does not strictly validate. That is why `ddigraph load` does
    not validate unless you ask. Refusing files that work would make the
    tool less useful, not more.

Ask for strictness when you want it:

```bash
ddigraph load survey.xml --validate    # refuse the file if it does not conform
ddigraph export survey.xml --validate -o out.ttl
```

`ddigraph validate` exits non-zero on a violation, so a CI step is one
line:

```bash
ddigraph validate survey.xml || exit 1
```

??? info "A wrinkle in the Codebook schema"
    The DDI-Codebook 2.6 schema published by the Alliance is not itself
    valid XSD. In 55 places an `xs:attribute` holds its `xs:annotation`
    *after* its `xs:simpleType`, while the specification requires
    `(annotation?, simpleType?)`. Every conforming parser rejects it.

    ddigraph repairs the ordering in memory before compiling, so Codebook
    validation works. The file on disk is left byte-identical to what the
    Alliance published — its checksum is in `schemas/manifest.json` and has
    to keep matching. Reordering is safe because `xs:annotation` is
    documentation and nothing reads it.

## After: SHACL

SHACL describes what a *graph* must look like: this class must carry that
property, this link must point at that kind of node. `ddigraph shapes`
generates the shapes from `DDISchema` — the same table that builds the
Neo4j constraints — so they cannot drift from what the exporter emits.

<!-- runnable -->
```python
import os

import pyshacl
import rdflib

import ddigraph
from ddigraph.rdf.shacl import shapes_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

data = rdflib.Graph().parse("survey.ttl", format="turtle")
conforms, _graph, _text = pyshacl.validate(data, shacl_graph=shapes_graph(flavor="lifecycle"))
print("conforms:", conforms)
```

```text
conforms: True
```

The export conforms even though the source file does not pass XSD. That is
not a contradiction — it is the two questions being genuinely different.
The parser is forgiving, so it reads a slightly non-conformant file and
still produces a well-formed graph.

Or from the command line:

```bash
ddigraph shapes -o shapes.ttl --flavor lifecycle
```

## Why `--flavor` matters here

Pass `--flavor` when validating real data. Twenty-one DDI type names appear
in more than one flavor — `Category`, `CodeList`, `Universe` — with
different identity fields. Without a flavor, shapes for all three are
emitted, and any constraint the flavors disagree about is dropped rather
than guessed at.

You met this in lesson 2, as the `CDI` prefix on every CDI type name. Same
collision, handled two different ways.

## Exercise

Validate the CDI fixture against its XSD, then export it and validate the
export against CDI shapes. Do the two agree?

??? success "Solution"
    ```python
    import os

    import pyshacl
    import rdflib

    import ddigraph
    from ddigraph.rdf.shacl import shapes_graph
    from ddigraph.validation import validate

    xsd = validate(os.environ["CDI_FIXTURE"], max_issues=1)
    print("XSD valid:", xsd.valid)

    ddigraph.export(os.environ["CDI_FIXTURE"], "cdi.ttl", format="turtle")
    data = rdflib.Graph().parse("cdi.ttl", format="turtle")
    conforms, _g, _t = pyshacl.validate(data, shacl_graph=shapes_graph(flavor="cdi"))
    print("SHACL conforms:", conforms)
    ```

    They disagree: XSD says no, SHACL says yes. The fixture declares the
    namespace `http://ddi-cdi/1.0`, which is not the one the published
    schema uses, so the XSD has no matching declaration for the root
    element. The parser does not care about that, produces a correct graph,
    and the export conforms.

    Disagreement between the two is informative, not a bug. It tells you
    the problem is in the *input document*, not in what you built from it.

## Check yourself

- Which of the two would catch a typo in an element name in the source XML?
- Which would catch an exporter that forgot to emit `skos:prefLabel`?
- Why does `ddigraph load` not validate by default?

---

Next: [Build your own pipeline](06-your-own-pipeline.md) — sending DDI
somewhere this package has never heard of.

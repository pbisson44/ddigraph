# Lesson 1 — Metadata is already a graph

!!! abstract "What you will learn"
    - What DDI is, and what problem it solves
    - Why survey metadata fits a graph better than a table
    - What the three DDI flavors are and why there are three

## The problem DDI solves

A survey produces two things. The data — rows of answers. And everything
you need to make sense of those rows: what was asked, of whom, in what
order, what the codes mean, who ran it, how it was weighted.

That second part is the metadata. Lose it and the data is a spreadsheet of
numbers nobody can read. A column called `Q4A` holding the value `3` means
nothing on its own.

DDI (Data Documentation Initiative) is a standard for writing that
metadata down. It is XML, it is maintained by an international alliance of
data archives, and it is what most social science archives use.

## Why a graph

Look at what the metadata actually says:

- A **question** uses a **code list**
- A **code list** contains **categories**
- A **question** is about a **concept**
- A **question** applies to a **universe** — the people it is asked of
- A **variable** comes from a **question**
- A **sequence** contains **questions**, and sequences nest

Every one of those is a link between two things. That is a graph: things
and the links between them.

You can store this in tables. People do. But the questions you actually
want to ask are questions about paths:

> Which variables trace back to questions that used this code list?

In SQL that is a chain of joins whose length depends on how deep the
nesting goes — and you have to know the depth in advance. In a graph
database it is one pattern:

```cypher
MATCH (v:Variable)-[*]->(c:CodeList {fragment_id: 'cl-employment'})
RETURN v.name
```

The `*` means "however many hops it takes". That is the difference. It is
not that graphs are faster; it is that the question is expressible.

!!! note "When a table is the right answer"
    If you only ever ask "give me every variable in this study", a table
    is simpler and you should use one. Graphs earn their keep when the
    interesting questions are about *connections*, and in survey metadata
    they usually are.

## Three flavors, one standard

DDI comes in three shapes. You will meet all of them.

| Flavor | What it is | Root element |
| -------- | ----------- | -------------- |
| **Codebook** (DDI-C 2.x) | The older, simpler one. Everything hangs off one study. | `<codeBook>` |
| **Lifecycle** (DDI-L 3.x) | Metadata split into reusable *fragments* that reference each other. | `<FragmentInstance>` |
| **CDI** (DDI-CDI 1.0) | The newest. Describes data across domains, not just surveys. | CDI namespace |

There are three because they were designed at different times for
different jobs, and archives hold files in all three. A tool that reads
only one of them is a tool you will outgrow.

Lifecycle is the one that is *obviously* a graph — a fragment referencing
another fragment is an edge, written down as an edge. Codebook and CDI
express the same idea through nesting and references instead.

## See it

Enough theory. Ask the package what flavor a file is:

<!-- runnable -->
```python
import os

import ddigraph

for name in ("FIXTURE", "CODEBOOK_FIXTURE", "CDI_FIXTURE"):
    path = os.environ[name]
    print(ddigraph.detect(path))
```

That prints `lifecycle`, `codebook`, `cdi`. It works by reading the root
XML element — no configuration, no guessing on your part.

## Exercise

Open `tests/fixtures/fragment_instance.xml` in an editor. It is short.
Find the `<r:CodeListReference>` element inside the question, and the
`<l:CodeList>` fragment it points at.

What connects them? Write down the two pieces of information that make the
link work.

??? success "Solution"
    The reference carries an **agency**, an **ID** and a **version**, and
    the code list fragment declares the same three:

    ```xml
    <r:CodeListReference>
        <r:Agency>test.org</r:Agency>
        <r:ID>cl1</r:ID>
        <r:Version>1.0</r:Version>
        <r:TypeOfObject>CodeList</r:TypeOfObject>
    </r:CodeListReference>
    ```

    ```xml
    <l:CodeList id="cl1" agency="test.org" version="1.0">
    ```

    Agency plus ID plus version is a **URN** —
    `urn:ddi:test.org:cl1:1.0` — and it is globally unique. That is why
    DDI-L fragments can live in separate files and still link up, and it
    is the identifier ddigraph uses as the subject when it writes RDF.
    You will see it again in lesson 4.

    `TypeOfObject` is the fourth piece. It says what kind of thing is
    being referenced, which is how a parser knows the edge is
    `USES_CODELIST` and not something else.

## Check yourself

- Why does a question about *paths* favour a graph over a table?
- Which DDI flavor stores its edges explicitly, and why do the other two not?
- What three pieces of information make a DDI-L reference resolvable?

---

Next: [Look before you load](02-first-look.md) — inspecting a file you
have never seen, without setting up anything.

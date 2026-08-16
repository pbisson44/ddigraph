# Lesson 6 — Build your own pipeline

!!! abstract "What you will learn"
    - Send DDI to a store this package has never heard of
    - Handle the two-phase ordering correctly
    - Know which parts are shipped and which are examples

## What actually ships

Know this before writing anything, because it decides how much work is
ahead of you.

| Target | Status |
| -------- | -------- |
| Neo4j | Shipped: `ddigraph load` |
| RDF / SPARQL | Shipped: `ddigraph export`, `ddigraph load out.ttl` |
| JSON / CSV | Shipped: `ddigraph export` |
| NetworkX, pandas, Gremlin | Worked examples in `demo/`, not shipped adapters |

Anything not in the first three you write yourself — and lesson 3 already
showed you the whole interface you need.

## The pattern

Three steps, and only the middle one is subtle.

1. Collect nodes, keyed by identity.
2. Collect edges, whose endpoints refer to those keys.
3. Write both to wherever you like.

The reason to collect before writing is the two-phase ordering from lesson
3: for DDI-L, every node arrives before any edge does, and an edge may
point at a node from a much earlier chunk. Writing edges as they arrive
would mean looking up nodes you have already thrown away.

<!-- runnable -->
```python
import os

from ddigraph import iter_graph


def node_key(node):
    """A stable key from the whole identity, not just the first field."""
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


nodes, edges = {}, []

for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        nodes[node_key(node)] = node
    for edge in chunk.relationships:
        edges.append((node_key(edge.start), edge.type, node_key(edge.end)))

print(len(nodes), "nodes,", len(edges), "edges")

dangling = [e for e in edges if e[0] not in nodes or e[2] not in nodes]
print("dangling endpoints:", len(dangling))
```

```text
6 nodes, 5 edges
dangling endpoints: 0
```

That `node_key` function is the part worth copying. Using
`next(iter(node.identity.values()))` — the first identity field — looks
equivalent and is not. Some node types are keyed on several fields
together, and taking only the first silently merges distinct nodes into
one. Nothing errors; you simply end up with fewer nodes than you had, and
their properties mixed together.

## A real target

NetworkX, in nine more lines:

<!-- runnable -->
```python
import os

import networkx as nx

from ddigraph import iter_graph


def node_key(node):
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


graph = nx.DiGraph()

for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        graph.add_node(node_key(node), node_type=node.label, **node.properties)
    for edge in chunk.relationships:
        graph.add_edge(node_key(edge.start), node_key(edge.end), type=edge.type)

print(graph.number_of_nodes(), "nodes,", graph.number_of_edges(), "edges")
print("acyclic:", nx.is_directed_acyclic_graph(graph))
```

```text
6 nodes, 5 edges
acyclic: True
```

Note `node_type=`, not `label=`. DDI records carry their own `label`
property, so `**node.properties` already supplies one, and passing
`label=node.label` as well raises `TypeError: got multiple values for
keyword argument 'label'`. It is an easy line to write and an easy one to
miss.

Because `add_node` here is keyed by identity, NetworkX merges repeats
naturally, so you can skip the collect step. A store without that property
needs the two-pass version above.

## It works on RDF too

`read_graph` yields the same `GraphChunk` values, so anything you build on
`iter_graph` reads Turtle, JSON-LD, N-Triples and RDF/XML for free:

<!-- runnable -->
```python
import os

import ddigraph
from ddigraph.rdf.reader import read_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

labels = sorted({node.label for chunk in read_graph("survey.ttl") for node in chunk.nodes})
print(labels)
```

```text
['Category', 'CodeList', 'Instrument', 'QuestionConstruct', 'QuestionItem', 'Sequence']
```

Same labels the XML produced, back out of RDF. That is the two-`rdf:type`
trick from lesson 4 paying off: without the project-namespace type, this
would return `Question` where the original said `QuestionItem`.

## Streaming, if you need it

Both examples above hold the whole graph in memory. For a 65 MB file with
tens of thousands of nodes that may be fine, or may not.

If it is not, do what `GraphChunkWriter` does: write each chunk as it
arrives and let the *store* resolve endpoints by identity. In Cypher that
is `MERGE` on the identity, which creates the node if the edge arrives
first and matches it if not. Any store with an upsert keyed on your
identity can do the same.

## Exercise

Write a pipeline that reports, for each node type, which relationship types
it participates in. Run it on all three fixtures.

??? success "Solution"
    ```python
    import collections
    import os

    from ddigraph import iter_graph

    for name in ("FIXTURE", "CODEBOOK_FIXTURE", "CDI_FIXTURE"):
        shapes = collections.defaultdict(set)
        for chunk in iter_graph(os.environ[name]):
            for edge in chunk.relationships:
                shapes[edge.start.label].add(f"-{edge.type}->")
                shapes[edge.end.label].add(f"<-{edge.type}-")

        print(f"--- {name}")
        for label in sorted(shapes)[:4]:
            print(f"  {label}: {', '.join(sorted(shapes[label]))}")
    ```

    One loop, three flavors, no branching on which is which. That is the
    whole payoff of the graph view: you wrote this against `iter_graph` and
    it works on formats you have never looked at.

## Where to go next

Next: [Grounding a model in the graph](07-grounding-an-llm.md) — putting
this metadata in front of a language model without letting it invent the
parts it does not know.

Two other things worth reading:

- The [RDF case study](../advanced/rdf-case-study.md) takes one code list
  from DDI all the way to validated linked data — this whole course applied
  to one realistic problem.
- [Custom Adapters](../user-guide/adapter.md) covers the async writer
  interface, for feeding a database rather than building a file.

And if something here was wrong or unclear,
[open an issue](https://github.com/pbisson44/ddigraph/issues). Every example
in these lessons runs in CI, so "this does not work" is a bug worth
reporting.

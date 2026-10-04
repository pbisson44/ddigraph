# NetworkX Backend

NetworkX provides in-memory graph analysis without requiring an external database. Ideal for
prototyping, local analysis, and integration with Python data science tools.

## Dependencies

NetworkX is an optional extra:

```bash
pip install "ddigraph[networkx]"
```

For visualization:

```bash
pip install matplotlib  # basic plots
pip install pyvis       # interactive HTML visualization
```

## Basic Usage

<!-- runnable -->
```python
import os

from ddigraph.backends.networkx import to_networkx

G = to_networkx(os.environ["FIXTURE"])

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
```

The source can be DDI XML of any flavor, or an RDF export such as
`survey.ttl`. You can also pass chunks you already have from
`ddigraph.iter_graph()`.

## What Is in the Graph

`G` is a `MultiDiGraph`. It is directed, because DDI links are. It is
*multi*, because two nodes can be joined by more than one kind of link.

- **Node ids** look like `"Variable:v1"`: the node's type, then its key. The
  type is part of the id because a key is only unique within its type. A
  codebook may use `c1` for a category and for a concept.
- **Node attributes** are `node_type`, `node_key`, the identity fields and
  every property that has a value. The type is called `node_type`, not
  `label`, because most DDI records have a `label` of their own: the
  human-readable one.
- **Edges** carry `relationship`, their type. The edge key is the type too,
  so loading the same file twice does not double any edge.

<!-- runnable -->
```python
import os
from collections import Counter

from ddigraph.backends.networkx import to_networkx

G = to_networkx(os.environ["FIXTURE"])

types = Counter(data["node_type"] for _, data in G.nodes(data=True))
for node_type, count in types.most_common():
    print(f"{node_type}: {count}")
```

## Several Files, One Graph

Pass `graph=` to add to a graph you already have. Nodes the files share
merge into one:

```python
G = to_networkx("wave1.xml")
G = to_networkx("wave2.xml", graph=G)
```

## Graph Analysis

### Basic Statistics

```python
# Graph info
print(f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Connected components (for undirected view)
undirected = G.to_undirected()
components = list(nx.connected_components(undirected))
print(f"Connected components: {len(components)}")

# Density
print(f"Density: {nx.density(G):.4f}")
```

### Centrality Metrics

```python
# Degree centrality
degree_cent = nx.degree_centrality(G)

# Betweenness centrality
betweenness = nx.betweenness_centrality(G)

# PageRank
pagerank = nx.pagerank(G)

# Find most important nodes
important = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
for node_id, score in important:
    print(f"{G.nodes[node_id]['node_type']}: {score:.4f}")
```

### Path Analysis

```python
# Find all paths between nodes
instrument_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "Instrument"]
question_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "QuestionItem"]

if instrument_nodes and question_nodes:
    paths = list(nx.all_simple_paths(G, instrument_nodes[0], question_nodes[0], cutoff=10))
    print(f"Found {len(paths)} paths")

# Shortest path
if nx.has_path(G, instrument_nodes[0], question_nodes[0]):
    path = nx.shortest_path(G, instrument_nodes[0], question_nodes[0])
    print(f"Shortest path: {' -> '.join(path)}")
```

### Subgraph Extraction

```python
# Extract subgraph by node type
question_items = [n for n, d in G.nodes(data=True) if d.get("node_type") == "QuestionItem"]
code_lists = [n for n, d in G.nodes(data=True) if d.get("node_type") == "CodeList"]
categories = [n for n, d in G.nodes(data=True) if d.get("node_type") == "Category"]

subgraph_nodes = set(question_items + code_lists + categories)
subgraph = G.subgraph(subgraph_nodes)
print(f"Subgraph: {subgraph.number_of_nodes()} nodes")

# Extract ego network (neighbors of a node)
ego = nx.ego_graph(G, instrument_nodes[0], radius=2)
print(f"Ego network: {ego.number_of_nodes()} nodes")
```

## Visualization

### Matplotlib

```python
import matplotlib.pyplot as plt

# Simple layout
pos = nx.spring_layout(G, k=2, iterations=50)

# Color by node type
color_map = {
    "Instrument": "red",
    "Sequence": "blue",
    "QuestionConstruct": "green",
    "QuestionItem": "orange",
    "CodeList": "purple",
    "Category": "yellow",
}
colors = [color_map.get(G.nodes[n].get("node_type", ""), "gray") for n in G.nodes()]

plt.figure(figsize=(16, 12))
nx.draw(G, pos, node_color=colors, node_size=50, with_labels=False, alpha=0.7)
plt.savefig("ddi_graph.png", dpi=150)
plt.show()
```

### PyVis (Interactive HTML)

```python
from pyvis.network import Network

net = Network(height="800px", width="100%", directed=True)

# Add nodes with colors
for node_id, data in G.nodes(data=True):
    node_type = data.get("node_type", "Unknown")
    label = data.get("label", node_id)[:30]
    color = color_map.get(node_type, "gray")
    net.add_node(node_id, label=label, color=color, title=f"{node_type}: {label}")

# Add edges
for source, target, data in G.edges(data=True):
    rel = data.get("relationship", "")
    net.add_edge(source, target, title=rel)

net.show("ddi_interactive.html")
```

## Export Formats

GraphML and GEXF cannot store lists, and some DDI properties are lists.
Build the graph with `flatten_lists=True` to join them with `|` first:

<!-- runnable -->
```python
import os

import networkx as nx

from ddigraph.backends.networkx import to_networkx

G = to_networkx(os.environ["FIXTURE"], flatten_lists=True)
nx.write_graphml(G, "survey.graphml")
nx.write_gexf(G, "survey.gexf")  # for Gephi
```

Node-link JSON keeps lists as they are:

```python
import json

with open("graph.json", "w") as f:
    json.dump(nx.node_link_data(G, edges="edges"), f, indent=2)
```

## As Tables Instead

For tables, use the [pandas backend](pandas.md). It reads the same file
into one DataFrame of nodes and one of relationships.

## Memory

The whole graph lives in memory, attributes included. If you only need the
structure, drop the attributes you will not use:

```python
for _, data in G.nodes(data=True):
    for key in [k for k in data if k not in ("node_type", "node_key")]:
        del data[key]
```

## See Also

- [pandas](pandas.md) - The same graph, as two tables
- [Gremlin](gremlin.md) - The same graph, in a database
- [NetworkX Documentation](https://networkx.org/documentation/stable/)

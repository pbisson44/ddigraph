# NetworkX Backend

NetworkX provides in-memory graph analysis without requiring an external database. Ideal for
prototyping, local analysis, and integration with Python data science tools.

## Dependencies

NetworkX is included with ddigraph:

```bash
pip install ddigraph  # includes networkx
```

For visualization:

```bash
pip install matplotlib  # basic plots
pip install pyvis       # interactive HTML visualization
```

## Basic Usage

### Load DDI to NetworkX

```python
import networkx as nx
from ddigraph import DDIFragmentParser

G = nx.MultiDiGraph()  # Directed graph with parallel edges
parser = DDIFragmentParser()

for fragment in parser.parse("survey.xml"):
    # Add node with properties
    G.add_node(
        fragment.fragment_id,
        label=fragment.element_type,
        name=fragment.label or "",
        urn=fragment.urn or "",
        **fragment.to_dict(),
    )

    # Add edges
    for rel_type, ref in fragment.references:
        G.add_edge(fragment.fragment_id, ref.id, key=rel_type, relationship=rel_type)

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
```

## Full Example

See `demo/load_networkx.py` for a complete example:

```python
"""Load DDI into NetworkX for graph analysis."""

import networkx as nx
from collections import Counter
from ddigraph.ingest.fragment_loader import DDIFragmentParser


def load_ddi_to_networkx(ddi_path: str) -> nx.MultiDiGraph:
    """Parse DDI-L file and create NetworkX graph."""

    G = nx.MultiDiGraph()
    parser = DDIFragmentParser()
    fragment_ids = set()

    for fragment in parser.parse(ddi_path):
        props = fragment.to_dict()

        G.add_node(
            fragment.fragment_id,
            node_type=fragment.element_type,
            label=fragment.label or "",
            urn=fragment.urn or "",
            agency=fragment.agency or "",
            version=fragment.version or "",
            **{k: v for k, v in props.items() if v is not None},
        )
        fragment_ids.add(fragment.fragment_id)

    # Second pass for edges
    parser = DDIFragmentParser()
    for fragment in parser.parse(ddi_path):
        for rel_type, ref in fragment.references:
            if ref.id in fragment_ids:
                G.add_edge(fragment.fragment_id, ref.id, key=rel_type, relationship=rel_type)

    return G


def analyze_graph(G: nx.MultiDiGraph):
    """Perform basic graph analysis."""

    print(f"Nodes: {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")

    # Node types
    types = Counter(data.get("node_type") for _, data in G.nodes(data=True))
    print("\nNode types:")
    for node_type, count in types.most_common(10):
        print(f"  {node_type}: {count}")

    # Relationship types
    rels = Counter(data.get("relationship") for _, _, data in G.edges(data=True))
    print("\nRelationship types:")
    for rel_type, count in rels.most_common(10):
        print(f"  {rel_type}: {count}")

    # Degree centrality
    centrality = nx.degree_centrality(G)
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nMost connected nodes:")
    for node_id, score in top_nodes:
        node_type = G.nodes[node_id].get("node_type", "Unknown")
        label = G.nodes[node_id].get("label", "")
        print(f"  {node_type} ({label}): {score:.4f}")


if __name__ == "__main__":
    G = load_ddi_to_networkx("data/Ireland_LabourSurvey.xml")
    analyze_graph(G)

    # Export
    nx.write_graphml(G, "ddi_graph.graphml")
    print("\nExported to ddi_graph.graphml")
```

## Graph Analysis

### Basic Statistics

```python
# Graph info
print(nx.info(G))

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

```python
# GraphML (supports attributes)
nx.write_graphml(G, "graph.graphml")

# GEXF (Gephi format)
nx.write_gexf(G, "graph.gexf")

# JSON (node-link format)
import json

data = nx.node_link_data(G)
with open("graph.json", "w") as f:
    json.dump(data, f, indent=2)

# Adjacency list
nx.write_adjlist(G, "graph.adjlist")

# Edge list
nx.write_edgelist(G, "graph.edgelist")
```

## Integration with pandas

```python
import pandas as pd

# Nodes to DataFrame
nodes_df = pd.DataFrame([{"id": n, **data} for n, data in G.nodes(data=True)])
print(nodes_df.head())

# Edges to DataFrame
edges_df = pd.DataFrame([{"source": u, "target": v, **data} for u, v, data in G.edges(data=True)])
print(edges_df.head())

# Export to CSV
nodes_df.to_csv("nodes.csv", index=False)
edges_df.to_csv("edges.csv", index=False)
```

## Memory Considerations

For large DDI files, consider:

```python
# Use DiGraph instead of MultiDiGraph if parallel edges aren't needed
G = nx.DiGraph()

# Process in chunks
parser = DDIFragmentParser()
for i, fragment in enumerate(parser.parse("large_file.xml")):
    G.add_node(fragment.fragment_id, node_type=fragment.element_type)

    if i % 1000 == 0:
        print(f"Processed {i} fragments")
```

## See Also

- [Adapter Architecture](../user-guide/adapter.md) - Building custom adapters
- [pandas demo](https://github.com/pbisson44/ddigraph/blob/main/demo/load_pandas.py) - Tabular analysis alternative
- [NetworkX Documentation](https://networkx.org/documentation/stable/)

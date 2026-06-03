# NetworkX

NetworkX fournit une analyse de graphes en mémoire sans nécessiter de base de données externe. Idéal
pour le prototypage, l'analyse locale et l'intégration avec les outils de science des données Python.

## Dépendances

NetworkX est inclus avec ddigraph :

```bash
pip install ddigraph  # inclut networkx
```

Pour la visualisation :

```bash
pip install matplotlib  # graphiques de base
pip install pyvis       # visualisation HTML interactive
```

## Utilisation de base

### Charger DDI dans NetworkX

```python
import networkx as nx
from ddigraph import DDIFragmentParser

G = nx.MultiDiGraph()  # Graphe orienté avec arêtes parallèles
parser = DDIFragmentParser()

for fragment in parser.parse("survey.xml"):
    # Ajouter un noeud avec ses propriétés
    G.add_node(
        fragment.fragment_id,
        label=fragment.element_type,
        name=fragment.label or "",
        urn=fragment.urn or "",
        **fragment.to_dict()
    )

    # Ajouter les arêtes
    for rel_type, ref in fragment.references:
        G.add_edge(
            fragment.fragment_id,
            ref.id,
            key=rel_type,
            relationship=rel_type
        )

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
```

## Exemple complet

Consultez `demo/load_networkx.py` pour un exemple complet :

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
            **{k: v for k, v in props.items() if v is not None}
        )
        fragment_ids.add(fragment.fragment_id)

    # Second pass for edges
    parser = DDIFragmentParser()
    for fragment in parser.parse(ddi_path):
        for rel_type, ref in fragment.references:
            if ref.id in fragment_ids:
                G.add_edge(
                    fragment.fragment_id,
                    ref.id,
                    key=rel_type,
                    relationship=rel_type
                )

    return G


def analyze_graph(G: nx.MultiDiGraph):
    """Perform basic graph analysis."""

    print(f"Nodes: {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")

    # Node types
    types = Counter(data.get('node_type') for _, data in G.nodes(data=True))
    print("\nNode types:")
    for node_type, count in types.most_common(10):
        print(f"  {node_type}: {count}")

    # Relationship types
    rels = Counter(data.get('relationship') for _, _, data in G.edges(data=True))
    print("\nRelationship types:")
    for rel_type, count in rels.most_common(10):
        print(f"  {rel_type}: {count}")

    # Degree centrality
    centrality = nx.degree_centrality(G)
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nMost connected nodes:")
    for node_id, score in top_nodes:
        node_type = G.nodes[node_id].get('node_type', 'Unknown')
        label = G.nodes[node_id].get('label', '')
        print(f"  {node_type} ({label}): {score:.4f}")


if __name__ == "__main__":
    G = load_ddi_to_networkx("data/Ireland_LabourSurvey.xml")
    analyze_graph(G)

    # Export
    nx.write_graphml(G, "ddi_graph.graphml")
    print("\nExported to ddi_graph.graphml")
```

## Analyse de graphes

### Statistiques de base

```python
# Informations sur le graphe
print(nx.info(G))

# Composantes connexes (pour la vue non orientée)
undirected = G.to_undirected()
components = list(nx.connected_components(undirected))
print(f"Composantes connexes : {len(components)}")

# Densité
print(f"Densité : {nx.density(G):.4f}")
```

### Métriques de centralité

```python
# Centralité de degré
degree_cent = nx.degree_centrality(G)

# Centralité d'intermédiation
betweenness = nx.betweenness_centrality(G)

# PageRank
pagerank = nx.pagerank(G)

# Trouver les noeuds les plus importants
important = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
for node_id, score in important:
    print(f"{G.nodes[node_id]['node_type']}: {score:.4f}")
```

### Analyse de chemins

```python
# Trouver tous les chemins entre les noeuds
instrument_nodes = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'Instrument']
question_nodes = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'QuestionItem']

if instrument_nodes and question_nodes:
    paths = list(nx.all_simple_paths(G, instrument_nodes[0], question_nodes[0], cutoff=10))
    print(f"{len(paths)} chemins trouvés")

# Plus court chemin
if nx.has_path(G, instrument_nodes[0], question_nodes[0]):
    path = nx.shortest_path(G, instrument_nodes[0], question_nodes[0])
    print(f"Plus court chemin : {' -> '.join(path)}")
```

### Extraction de sous-graphes

```python
# Extraire un sous-graphe par type de noeud
question_items = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'QuestionItem']
code_lists = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'CodeList']
categories = [n for n, d in G.nodes(data=True) if d.get('node_type') == 'Category']

subgraph_nodes = set(question_items + code_lists + categories)
subgraph = G.subgraph(subgraph_nodes)
print(f"Sous-graphe : {subgraph.number_of_nodes()} noeuds")

# Extraire le réseau ego (voisins d'un noeud)
ego = nx.ego_graph(G, instrument_nodes[0], radius=2)
print(f"Réseau ego : {ego.number_of_nodes()} noeuds")
```

## Visualisation

### Matplotlib

```python
import matplotlib.pyplot as plt

# Disposition simple
pos = nx.spring_layout(G, k=2, iterations=50)

# Couleur par type de noeud
color_map = {
    'Instrument': 'red',
    'Sequence': 'blue',
    'QuestionConstruct': 'green',
    'QuestionItem': 'orange',
    'CodeList': 'purple',
    'Category': 'yellow'
}
colors = [color_map.get(G.nodes[n].get('node_type', ''), 'gray') for n in G.nodes()]

plt.figure(figsize=(16, 12))
nx.draw(G, pos, node_color=colors, node_size=50, with_labels=False, alpha=0.7)
plt.savefig("ddi_graph.png", dpi=150)
plt.show()
```

### PyVis (HTML interactif)

```python
from pyvis.network import Network

net = Network(height="800px", width="100%", directed=True)

# Ajouter les noeuds avec des couleurs
for node_id, data in G.nodes(data=True):
    node_type = data.get('node_type', 'Unknown')
    label = data.get('label', node_id)[:30]
    color = color_map.get(node_type, 'gray')
    net.add_node(node_id, label=label, color=color, title=f"{node_type}: {label}")

# Ajouter les arêtes
for source, target, data in G.edges(data=True):
    rel = data.get('relationship', '')
    net.add_edge(source, target, title=rel)

net.show("ddi_interactive.html")
```

## Formats d'export

```python
# GraphML (prend en charge les attributs)
nx.write_graphml(G, "graph.graphml")

# GEXF (format Gephi)
nx.write_gexf(G, "graph.gexf")

# JSON (format node-link)
import json
data = nx.node_link_data(G)
with open("graph.json", "w") as f:
    json.dump(data, f, indent=2)

# Liste d'adjacence
nx.write_adjlist(G, "graph.adjlist")

# Liste d'arêtes
nx.write_edgelist(G, "graph.edgelist")
```

## Intégration avec pandas

```python
import pandas as pd

# Noeuds vers DataFrame
nodes_df = pd.DataFrame([
    {"id": n, **data}
    for n, data in G.nodes(data=True)
])
print(nodes_df.head())

# Arêtes vers DataFrame
edges_df = pd.DataFrame([
    {"source": u, "target": v, **data}
    for u, v, data in G.edges(data=True)
])
print(edges_df.head())

# Exporter en CSV
nodes_df.to_csv("nodes.csv", index=False)
edges_df.to_csv("edges.csv", index=False)
```

## Considérations mémoire

Pour les fichiers DDI volumineux, considérez :

```python
# Utiliser DiGraph au lieu de MultiDiGraph si les arêtes parallèles ne sont pas nécessaires
G = nx.DiGraph()

# Traiter par blocs
parser = DDIFragmentParser()
for i, fragment in enumerate(parser.parse("large_file.xml")):
    G.add_node(fragment.fragment_id, node_type=fragment.element_type)

    if i % 1000 == 0:
        print(f"Processed {i} fragments")
```

## Voir aussi

- [Architecture des adaptateurs](../user-guide/adapter.md) - Construction d'adaptateurs personnalisés
- [pandas demo](https://github.com/pbisson44/ddigraph/blob/main/demo/load_pandas.py) - Alternative d'analyse tabulaire
- [Documentation NetworkX](https://networkx.org/documentation/stable/)

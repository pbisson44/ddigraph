# NetworkX

NetworkX fournit une analyse de graphes en mémoire sans nécessiter de base de données externe. Idéal
pour le prototypage, l'analyse locale et l'intégration avec les outils de science des données Python.

## Dépendances

NetworkX est un extra optionnel :

```bash
pip install "ddigraph[networkx]"
```

Pour la visualisation :

```bash
pip install matplotlib  # graphiques de base
pip install pyvis       # visualisation HTML interactive
```

## Utilisation de base

<!-- runnable -->
```python
import os

from ddigraph.backends.networkx import to_networkx

G = to_networkx(os.environ["FIXTURE"])

print(f"Graphe : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
```

La source peut être du DDI XML de n'importe quelle variante, ou un export
RDF comme `survey.ttl`. Vous pouvez aussi passer des blocs déjà obtenus avec
`ddigraph.iter_graph()`.

## Contenu du graphe

`G` est un `MultiDiGraph`. Il est orienté, car les liens DDI le sont. Il est
*multiple*, car deux nœuds peuvent être reliés par plusieurs sortes de liens.

- **Les identifiants de nœud** ont la forme `"Variable:v1"` : le type du
  nœud, puis sa clé. Le type fait partie de l'identifiant, car une clé n'est
  unique qu'au sein de son type. Un codebook peut utiliser `c1` pour une
  catégorie et pour un concept.
- **Les attributs de nœud** sont `node_type`, `node_key`, les champs
  d'identité et chaque propriété qui a une valeur. Le type s'appelle
  `node_type` et non `label`, car la plupart des enregistrements DDI ont leur
  propre `label` : le libellé lisible.
- **Les arêtes** portent `relationship`, leur type. La clé de l'arête est
  aussi le type : charger deux fois le même fichier ne double aucune arête.

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

## Plusieurs fichiers, un graphe

Passez `graph=` pour compléter un graphe existant. Les nœuds communs aux
fichiers fusionnent :

```python
G = to_networkx("wave1.xml")
G = to_networkx("wave2.xml", graph=G)
```

## Analyse de graphes

### Statistiques de base

```python
# Informations sur le graphe
print(f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

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
instrument_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "Instrument"]
question_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "QuestionItem"]

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
question_items = [n for n, d in G.nodes(data=True) if d.get("node_type") == "QuestionItem"]
code_lists = [n for n, d in G.nodes(data=True) if d.get("node_type") == "CodeList"]
categories = [n for n, d in G.nodes(data=True) if d.get("node_type") == "Category"]

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

### PyVis (HTML interactif)

```python
from pyvis.network import Network

net = Network(height="800px", width="100%", directed=True)

# Ajouter les noeuds avec des couleurs
for node_id, data in G.nodes(data=True):
    node_type = data.get("node_type", "Unknown")
    label = data.get("label", node_id)[:30]
    color = color_map.get(node_type, "gray")
    net.add_node(node_id, label=label, color=color, title=f"{node_type}: {label}")

# Ajouter les arêtes
for source, target, data in G.edges(data=True):
    rel = data.get("relationship", "")
    net.add_edge(source, target, title=rel)

net.show("ddi_interactive.html")
```

## Formats d'export

GraphML et GEXF ne savent pas stocker de listes, et certaines propriétés DDI
en sont. Construisez le graphe avec `flatten_lists=True` pour les joindre
d'abord avec `|` :

<!-- runnable -->
```python
import os

import networkx as nx

from ddigraph.backends.networkx import to_networkx

G = to_networkx(os.environ["FIXTURE"], flatten_lists=True)
nx.write_graphml(G, "survey.graphml")
nx.write_gexf(G, "survey.gexf")  # pour Gephi
```

Le JSON node-link conserve les listes telles quelles :

```python
import json

with open("graph.json", "w") as f:
    json.dump(nx.node_link_data(G, edges="edges"), f, indent=2)
```

## Sous forme de tableaux

Pour des tableaux, utilisez le [backend pandas](pandas.md). Il lit le même
fichier dans un DataFrame de nœuds et un DataFrame de relations.

## Mémoire

Tout le graphe tient en mémoire, attributs compris. Si seule la structure
vous intéresse, retirez les attributs inutiles :

```python
for _, data in G.nodes(data=True):
    for key in [k for k in data if k not in ("node_type", "node_key")]:
        del data[key]
```

## Voir aussi

- [pandas](pandas.md) - Le même graphe, en deux tableaux
- [Gremlin](gremlin.md) - Le même graphe, dans une base de données
- [Documentation NetworkX](https://networkx.org/documentation/stable/)

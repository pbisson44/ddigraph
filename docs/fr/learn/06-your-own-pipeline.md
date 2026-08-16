# Leçon 6 — Construire votre pipeline

!!! abstract "Ce que vous allez apprendre"
    - Envoyer du DDI vers un magasin dont ce package n'a jamais entendu parler
    - Gérer correctement l'ordonnancement en deux phases
    - Savoir quelles parties sont fournies et lesquelles sont des exemples

## Ce qui est réellement fourni

Sachez-le avant d'écrire quoi que ce soit : cela détermine la quantité de
travail qui vous attend.

| Cible | Statut |
| ------- | -------- |
| Neo4j | Fourni : `ddigraph load` |
| RDF / SPARQL | Fourni : `ddigraph export`, `ddigraph load out.ttl` |
| JSON / CSV | Fourni : `ddigraph export` |
| NetworkX, pandas, Gremlin | Exemples dans `demo/`, pas des adaptateurs fournis |

Tout ce qui n'est pas dans les trois premières lignes, vous l'écrivez
vous-même — et la leçon 3 vous a déjà montré toute l'interface nécessaire.

## Le motif

Trois étapes, dont seule celle du milieu est subtile.

1. Collecter les nœuds, indexés par identité.
2. Collecter les arcs, dont les extrémités renvoient à ces clés.
3. Écrire les deux où vous voulez.

La raison de collecter avant d'écrire est l'ordonnancement en deux phases
de la leçon 3 : pour DDI-L, tous les nœuds arrivent avant le premier arc,
et un arc peut désigner un nœud d'un morceau bien antérieur. Écrire les
arcs à leur arrivée voudrait dire chercher des nœuds déjà jetés.

<!-- runnable -->
```python
import os

from ddigraph import iter_graph


def node_key(node):
    """Une clé stable tirée de toute l'identité, pas du premier champ."""
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


nodes, edges = {}, []

for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        nodes[node_key(node)] = node
    for edge in chunk.relationships:
        edges.append((node_key(edge.start), edge.type, node_key(edge.end)))

print(len(nodes), "nœuds,", len(edges), "arcs")

dangling = [e for e in edges if e[0] not in nodes or e[2] not in nodes]
print("extrémités orphelines :", len(dangling))
```

```text
6 nœuds, 5 arcs
extrémités orphelines : 0
```

Cette fonction `node_key` est la partie à recopier. Utiliser
`next(iter(node.identity.values()))` — le premier champ d'identité —
paraît équivalent et ne l'est pas. Certains types de nœuds sont identifiés
par plusieurs champs ensemble, et ne prendre que le premier fusionne
silencieusement des nœuds distincts en un seul. Rien ne lève d'erreur :
vous vous retrouvez simplement avec moins de nœuds qu'au départ, et leurs
propriétés mélangées.

## Une vraie cible

NetworkX, en neuf lignes de plus :

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

print(graph.number_of_nodes(), "nœuds,", graph.number_of_edges(), "arcs")
print("acyclique :", nx.is_directed_acyclic_graph(graph))
```

```text
6 nœuds, 5 arcs
acyclique : True
```

Notez `node_type=`, et non `label=`. Les enregistrements DDI portent leur
propre propriété `label` : `**node.properties` en fournit donc déjà une, et
passer en plus `label=node.label` lève `TypeError: got multiple values for
keyword argument 'label'`. C'est une ligne facile à écrire et facile à
manquer.

Comme `add_node` est ici indexé par identité, NetworkX fusionne
naturellement les répétitions : vous pouvez donc sauter l'étape de
collecte. Un magasin sans cette propriété a besoin de la version en deux
passes ci-dessus.

## Cela marche aussi sur du RDF

`read_graph` produit les mêmes `GraphChunk` : tout ce que vous construisez
sur `iter_graph` lit donc gratuitement Turtle, JSON-LD, N-Triples et
RDF/XML.

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

Les mêmes libellés que produisait le XML, ressortis du RDF. C'est l'astuce
des deux `rdf:type` de la leçon 4 qui paie : sans le type de l'espace de
noms projet, on obtiendrait `Question` là où l'original disait
`QuestionItem`.

## En flux, si nécessaire

Les deux exemples ci-dessus gardent tout le graphe en mémoire. Pour un
fichier de 65 Mo comptant des dizaines de milliers de nœuds, cela peut
convenir — ou non.

Si ce n'est pas le cas, faites ce que fait `GraphChunkWriter` : écrivez
chaque morceau à son arrivée et laissez le *magasin* résoudre les
extrémités par identité. En Cypher, c'est `MERGE` sur l'identité, qui crée
le nœud si l'arc arrive en premier et le retrouve sinon. Tout magasin
disposant d'un upsert sur votre identité peut faire de même.

## Exercice

Écrivez un pipeline qui indique, pour chaque type de nœud, à quels types de
relations il participe. Exécutez-le sur les trois fichiers.

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

    Une seule boucle, trois variantes, aucun branchement selon laquelle.
    C'est tout le bénéfice de la vue graphe : vous avez écrit ceci contre
    `iter_graph` et cela fonctionne sur des formats que vous n'avez jamais
    regardés.

## Ensuite

Suivant : [Ancrer un modèle dans le graphe](07-grounding-an-llm.md) — mettre
ces métadonnées sous les yeux d'un modèle de langage sans le laisser
inventer ce qu'il ne sait pas.

Deux autres lectures utiles :

- L'[étude de cas RDF](../advanced/rdf-case-study.md) mène une liste de
  codes de DDI jusqu'aux données liées validées — tout ce cours appliqué à
  un seul problème réaliste.
- [Adaptateurs personnalisés](../user-guide/adapter.md) couvre l'interface
  d'écriture asynchrone, pour alimenter une base plutôt que produire un
  fichier.

Et si quelque chose ici était faux ou obscur,
[ouvrez un ticket](https://github.com/pbisson44/ddigraph/issues). Chaque
exemple de ces leçons s'exécute en CI : « ça ne marche pas » est donc un
bogue qui mérite d'être signalé.

# RDF et SPARQL

ddigraph lit et écrit du RDF. Vous pouvez convertir un fichier DDI en
Turtle, JSON-LD, N-Triples ou RDF/XML, le vérifier avec des formes SHACL,
puis le relire.

## Installation

Le support RDF est un extra optionnel :

```bash
pip install "ddigraph[rdf]"
```

Ajoutez la validation SHACL avec :

```bash
pip install "ddigraph[shacl]"
```

## Exporter un fichier

Aucune base de données n'est nécessaire. La commande `export` lit du DDI et
écrit un fichier :

```bash
ddigraph export survey.xml --format turtle -o survey.ttl
```

Elle fonctionne pour les trois variantes DDI : Codebook, Lifecycle et CDI.
Les autres formats sont `ntriples`, `jsonld`, `rdfxml`, `json` et `csv`. Les
formats `json` et `csv` ne demandent aucun extra.

Depuis Python :

<!-- runnable -->
```python
import os

import ddigraph

result = ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")
print(result.nodes, "nodes,", result.triples, "triples")
```

## Le vocabulaire

Chaque graphe utilise un seul espace de noms, qui possède sa propre
version :

```text
https://pbisson44.github.io/ddigraph/ns/1.0/
```

La version appartient au vocabulaire, pas au paquet. Elle change uniquement
quand un terme change de sens : une requête écrite aujourd'hui continue donc
de fonctionner.

Cet IRI se résout. Ouvrez-le et vous obtenez la
[référence du vocabulaire](../ns/1.0.md), avec
[vocabulary.ttl](../ns/vocabulary.ttl) à côté : chaque classe et chaque
prédicat, générés à partir du schéma qui pilote l'exportateur.

### Les termes publiés d'abord

Quand l'Alliance DDI ou le monde du web sémantique propose déjà un terme,
ddigraph l'utilise. C'est ce qui permet de relier vos données à celles des
autres.

| Concept DDI | Classe RDF |
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

[DISCO][disco] est le vocabulaire RDF de l'Alliance DDI, construit à partir
de DDI Codebook et DDI Lifecycle. [XKOS][xkos] étend SKOS pour les
classifications statistiques.

DDI compte environ 250 types de nœuds et DISCO définit 16 classes. Tout ce
qui n'a pas d'équivalent publié reçoit un terme dans l'espace de noms
ddigraph.

### Chaque nœud porte deux types

Un nœud reçoit la classe publiée *et* une classe ddigraph :

```turtle
<urn:ddi:ie.cso:q-4711:1.0.0>
    a disco:Question , ddigraph:QuestionItem ;
    skos:prefLabel "Main activity status"@en-IE .
```

La classe publiée est celle que lisent les autres outils. La classe ddigraph
indique le type DDI réel. `Question` et `QuestionItem` deviennent tous deux
`disco:Question` : sans le second type, on ne pourrait plus les distinguer.

### Les prédicats

Les noms de relations sont en `lowerCamelCase`. Une relation `HAS_CONSTRUCT`
devient `ddigraph:hasConstruct`. Quand un prédicat publié existe, il est
utilisé à la place :

| Relation du graphe | Prédicat RDF |
| --- | --- |
| `USES_CONCEPT` | `disco:concept` |
| `ASKS_QUESTION` | `disco:question` |
| `USES_CODELIST` | `disco:responseDomain` |
| `IN_DATASET` | `dcterms:isPartOf` |
| `HAS_CATEGORY` | `skos:inScheme` |

### Les IRI des sujets

Les URN DDI sont réutilisés tels quels quand l'enregistrement en possède
un :

```text
urn:ddi:ie.cso:q-4711:1.0.0
```

Un URN est déjà unique à l'échelle mondiale : créer un nouvel IRI
n'apporterait rien. Les enregistrements sans URN reçoivent un identifiant
`urn:ddigraph:`. Utilisez `--base-uri` pour votre propre espace de noms au
moment de publier :

```bash
ddigraph export survey.xml --format turtle -o out.ttl \
  --base-uri https://example.org/id/
```

## Les listes de codes sont du SKOS

Les listes de codes et les catégories sont la partie de DDI la plus utile
en dehors de DDI. Elles sortent en SKOS correct :

```turtle
<urn:ddi:test.org:cl1:1.0>
    a skos:ConceptScheme , ddigraph:CodeList ;
    skos:prefLabel "Age Groups" .

<urn:ddi:test.org:cat1:1.0>
    a skos:Concept , ddigraph:Category ;
    skos:inScheme <urn:ddi:test.org:cl1:1.0> ;
    skos:prefLabel "Under 18" .
```

Notez le sens du lien. Le fichier DDI imbrique les catégories dans la liste
de codes, mais SKOS place le lien sur le membre, via `skos:inScheme`.
`skos:member` appartient à `skos:Collection`, pas à `skos:ConceptScheme`.

Les références externes deviennent `skos:exactMatch`. C'est le lien qui relie
une liste de codes à EuroVoc, DBpedia ou tout autre vocabulaire publié.

## Interroger avec SPARQL

Une fois le fichier chargé dans rdflib, vous pouvez l'interroger :

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

Le même fichier se charge dans n'importe quel triplestore : Jena, GraphDB,
Virtuoso, Stardog, Blazegraph.

## Valider avec SHACL

`ddigraph shapes` écrit les formes SHACL du vocabulaire. Elles viennent du
schéma qui construit aussi les contraintes Neo4j : elles ne peuvent donc pas
diverger.

```bash
ddigraph shapes -o shapes.ttl --flavor lifecycle
```

Utilisez `--flavor` pour valider des données réelles. Un fichier a une seule
variante, et 21 noms de types DDI apparaissent dans plusieurs variantes avec
des clés différentes.

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

## Relire du RDF

Le RDF est aussi un format d'entrée. `read_graph` analyse Turtle, JSON-LD,
N-Triples et RDF/XML vers la forme produite par les analyseurs DDI :

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

L'aller-retour ne perd rien. Exportez un fichier, relisez-le, exportez-le à
nouveau : vous obtenez les mêmes triplets.

Vous pouvez aussi charger du RDF directement dans Neo4j :

```bash
ddigraph export survey.xml --format turtle -o out.ttl
ddigraph load out.ttl
```

Le lecteur ignore les sujets sans type ddigraph. Pointez-le vers du RDF
étranger et vous n'obtenez rien, plutôt que n'importe quoi.

## Construire votre propre graphe

`iter_graph` donne directement les nœuds et les relations, pour toutes les
variantes DDI. Utilisez-le pour alimenter un stockage que ddigraph ne gère
pas :

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

# Étude de cas : publier une liste de codes en données liées

Un institut statistique documente une enquête sur la population active en
DDI. Une personne extérieure veut savoir si les catégories de statut
d'emploi de cette enquête signifient la même chose que les siennes.

Rien dans le fichier DDI ne répond à cette question. Cette page montre
comment y répondre, avec la seule ligne de commande `ddigraph` et un petit
fichier DDI.

Chaque bloc de code ci-dessous fonctionne. Ils sont exécutés par la suite de
tests, sur un fichier d'exemple livré avec le dépôt.

## Le point de départ

L'enquête est un fichier DDI-L. Demandez ce qu'il contient :

<!-- runnable -->
```bash
ddigraph detect "$FIXTURE"
```

## Étape 1 : convertir en RDF

<!-- runnable -->
```bash
ddigraph export "$FIXTURE" --format turtle -o survey.ttl
head -20 survey.ttl
```

Deux éléments comptent dans cette sortie.

Les sujets sont des URN DDI. `urn:ddi:test.org:cat1:1.0` est l'identifiant
déjà attribué par l'institut. ddigraph n'en invente pas un nouveau : le même
objet garde donc le même nom partout où il circule.

Les catégories sont des `skos:Concept` et pointent vers leur liste de codes
avec `skos:inScheme`. Tout outil SKOS comprend cela, sans rien savoir de
DDI.

## Étape 2 : vérifier le contenu

Les formes viennent du schéma qui construit aussi les contraintes Neo4j :

<!-- runnable -->
```bash
ddigraph export "$FIXTURE" --format turtle -o survey.ttl
ddigraph shapes -o shapes.ttl --flavor lifecycle
python - <<'PY'
import pyshacl
import rdflib

data = rdflib.Graph().parse("survey.ttl", format="turtle")
shapes = rdflib.Graph().parse("shapes.ttl", format="turtle")
conforms, _graph, report = pyshacl.validate(data, shacl_graph=shapes)
print("conforms:", conforms)
assert conforms, report
PY
```

Envoyez `shapes.ttl` avec les données : le destinataire peut lancer la même
vérification avant de leur faire confiance.

## Étape 3 : répondre à la question

La question initiale était de savoir si deux listes de codes concordent.
C'est désormais une requête SPARQL :

<!-- runnable -->
```python
import os

import rdflib

import ddigraph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")
graph = rdflib.Graph().parse("survey.ttl", format="turtle")

rows = graph.query("""
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

    SELECT ?scheme ?label
    WHERE {
        ?concept skos:inScheme ?scheme ;
                 skos:prefLabel ?label .
    }
    ORDER BY ?label
""")

for scheme, label in rows:
    print(f"{label} -> {scheme}")
```

Si le fichier DDI enregistre des références externes pour ses catégories,
elles deviennent des `skos:exactMatch`. C'est le lien qui dit « cette
catégorie est la même que celle d'EuroVoc », et c'est ce qui rend la réponse
vérifiable par une machine plutôt que par la lecture de deux PDF.

## Étape 4 : conserver le graphe

Le RDF n'est pas une impasse. Il se relit :

<!-- runnable -->
```python
import os

import ddigraph
from ddigraph.rdf.reader import read_graph

ddigraph.export(os.environ["FIXTURE"], "survey.ttl", format="turtle")

labels = sorted({node.label for chunk in read_graph("survey.ttl") for node in chunk.nodes})
print("recovered types:", labels)
```

Un collègue peut donc vous envoyer du Turtle, que vous chargez dans Neo4j
exactement comme s'il s'agissait du XML d'origine :

```bash
ddigraph load survey.ttl
```

## Pourquoi ces détails comptent

Deux choses dans la sortie ci-dessus sont faciles à rater, et toutes deux
décident si le résultat vaut la peine d'être envoyé à quelqu'un.

Le prédicat est un terme publié, pas un nom de relation. Émettre
`ddi:USES_CODELIST` transporterait une convention de base de données dans
un format destiné à l'échange, et aucun consommateur ne la reconnaîtrait.

Le sujet conserve son URN intact. Aplatir `urn:ddi:test.org:cat1:1.0` en
quelque chose comme `urn_ddi_test.org_cat1_1.0` détruit le seul
identifiant sur lequel le monde DDI s'accorde déjà.

Ratez l'un des deux et le fichier s'analyse toujours — simplement, il ne se
joint à rien.

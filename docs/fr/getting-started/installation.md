# Installation

## Prérequis

- Python 3.12 à 3.14
- pip, uv, pipx ou un autre gestionnaire de paquets Python

## Installation de base

Installez ddigraph depuis PyPI :

```bash
pip install ddigraph
```

Avec [uv](https://docs.astral.sh/uv/) :

```bash
uv pip install ddigraph
```

L'installation de base est légère. Elle ne tire que six paquets
d'exécution : lxml, neo4j, orjson, pydantic, pydantic-settings et
xmlschema. Le pilote Neo4j est inclus, donc le backend Neo4j
fonctionne d'emblée. Les autres backends sont des extras optionnels
(voir ci-dessous).

## Extras de backend

Chaque backend autre que Neo4j est livré comme extra optionnel.
N'installez que ceux dont votre cible a besoin :

```bash
pip install "ddigraph[rdf]"        # RDF / SPARQL (rdflib)
pip install "ddigraph[gremlin]"    # bases Gremlin (gremlinpython)
pip install "ddigraph[networkx]"   # graphes NetworkX en mémoire
pip install "ddigraph[pandas]"     # export pandas / Excel
pip install "ddigraph[sdmx]"       # interopérabilité SDMX
pip install "ddigraph[all]"        # tous les extras de backend
```

Si un extra manque, le backend correspondant lève une erreur claire
qui nomme le paquet à installer. Rien d'autre ne casse.

## Extras de développement et de documentation

Pour les tests, le linting, la vérification de types et les audits
d'empaquetage :

```bash
pip install "ddigraph[dev]"
```

Pour construire le site de documentation :

```bash
pip install "ddigraph[docs]"
```

Combinez-les :

```bash
pip install "ddigraph[dev,docs]"
```

## Depuis les sources

Clonez le dépôt, puis installez-le en mode éditable :

```bash
git clone https://github.com/pbisson44/neo4ddi.git
cd neo4ddi
pip install -e ".[dev,docs]"
```

## Vérifier l'installation

```python
import ddigraph
print(ddigraph.__version__)
```

Ou depuis la ligne de commande :

```bash
ddigraph version
```

## Services de backend

Certains backends ont besoin d'un service en cours d'exécution.
D'autres tournent en mémoire.

### Neo4j (inclus)

Le pilote Neo4j est dans l'installation de base. Il vous faut tout de
même un serveur Neo4j :

- [Neo4j Desktop](https://neo4j.com/download/) (le plus simple pour le développement)
- l'image [Neo4j Docker](https://hub.docker.com/_/neo4j)
- Neo4j Aura (cloud géré)

### RDF / SPARQL

Installez `ddigraph[rdf]`. rdflib construit le graphe sur votre
machine. Un triplestore est une base de données RDF pour les systèmes
en production. Les plus courants :

- Virtuoso
- GraphDB
- Stardog
- Apache Jena Fuseki

### Gremlin

Installez `ddigraph[gremlin]`. Il fonctionne avec ces bases :

- Apache TinkerPop (tests locaux)
- JanusGraph
- Amazon Neptune
- Azure Cosmos DB (API Gremlin)

### NetworkX

Installez `ddigraph[networkx]`. Il étudie les graphes en mémoire. Vous
n'avez besoin d'aucun service externe.

## Configuration d'environnement

ddigraph lit ses paramètres depuis des variables d'environnement.
Créez un fichier `.env` :

```bash
# Connexion Neo4j (pour le backend Neo4j)
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=votre-mot-de-passe

# Paramètres d'ingestion
DDIGRAPH_CHUNK_SIZE=200
DDIGRAPH_WRITER_CONCURRENCY=1
DDIGRAPH_LOG_LEVEL=INFO
```

Vous pouvez aussi définir n'importe lequel de ces paramètres sans
option avec `--tune` ou un fichier TOML `--config`. Voir la
[référence CLI](../reference/cli.md) pour la liste complète.

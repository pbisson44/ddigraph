# Neo4j

Neo4j est le backend par défaut et le plus complet pour ddigraph. Il offre un stockage graphe natif
avec de puissantes capacités de requête Cypher.

## Installation

### Docker (Recommandé pour le développement)

```bash
docker run -d --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:latest
```

### Neo4j Desktop

Téléchargez depuis [neo4j.com/download](https://neo4j.com/download/) et créez une base de données locale.

### Neo4j Aura (Cloud)

Créez une instance gratuite sur [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura/).

## Configuration

Définissez les variables d'environnement :

```bash
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=your-password
export DDIGRAPH_NEO4J_DATABASE=neo4j  # optionnel, 'neo4j' par défaut
```

Ou utilisez un fichier `.env` :

```ini
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=your-password
```

## Chargement des données

### CLI

```bash
# Initialiser le schéma (crée les contraintes et les index)
ddigraph bootstrap

# Charger un DDI Codebook
ddigraph load survey.xml --dataset-id my-survey

# Charger un DDI-L FragmentInstance
ddigraph load questionnaire.xml

# Remplacer les données existantes
ddigraph load survey.xml --dataset-id my-survey --replace
```

### API Python

```python
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph import DDILoader, DDIFragmentLoader, detect_ddi_format
from ddigraph.config import Settings
from ddigraph.graph.bootstrap import ensure_schema


async def main():
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    # Initialiser le schéma
    await ensure_schema(driver, include_fragments=True)

    # Charger les données
    path = "survey.xml"
    if detect_ddi_format(path) == "lifecycle":
        loader = DDIFragmentLoader(driver, settings=settings)
        result = await loader.load(path)
    else:
        loader = DDILoader(driver, settings=settings)
        result = await loader.load(path, dataset_id="demo")

    print(result)
    await driver.close()


asyncio.run(main())
```

## Schéma

ddigraph crée le schéma Neo4j suivant :

### Contraintes

Des contraintes d'unicité sont créées pour chaque type de noeud :

```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Dataset) REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:QuestionItem) REQUIRE n.fragment_id IS UNIQUE
-- etc.
```

### Index

Index secondaires pour les patterns de requêtes courants :

```cypher
CREATE INDEX IF NOT EXISTS FOR (n:Variable) ON (n.label)
CREATE INDEX IF NOT EXISTS FOR (n:QuestionItem) ON (n.question_text)
-- etc.
```

## Exemples de requêtes

### Requêtes DDI Codebook

```cypher
-- Toutes les variables d'un jeu de données
MATCH (d:Dataset {id: 'demo'})<-[:IN_DATASET]-(v:Variable)
RETURN v.name, v.label, v.description

-- Variables avec leurs concepts
MATCH (v:Variable)-[:USES_CONCEPT]->(c:Concept)
RETURN v.name, c.name

-- Questions et leurs variables
MATCH (v:Variable)-[:ASKED_AS]->(q:Question)
RETURN v.name, q.text

-- Groupes de variables
MATCH (vg:VarGroup)-[:GROUPS]->(v:Variable)
RETURN vg.label, collect(v.name) AS variables
```

### Requêtes DDI-L FragmentInstance

```cypher
-- Flux du questionnaire depuis l'instrument
MATCH path = (i:Instrument)-[:HAS_CONSTRUCT*1..10]->(c)
RETURN path

-- Branchement conditionnel
MATCH (ite:IfThenElse)-[:THEN]->(then_seq)
OPTIONAL MATCH (ite)-[:ELSE]->(else_seq)
RETURN ite.condition, then_seq.label, else_seq.label

-- Questions avec listes de codes
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN q.name, q.question_text, cl.name, collect(cat.category_label) AS options

-- Trouver toutes les questions dans une séquence
MATCH (s:Sequence)-[:HAS_CONSTRUCT*]->(qc:QuestionConstruct)-[:ASKS_QUESTION]->(q)
RETURN s.label, q.name, q.question_text
```

### Requêtes inter-formats

```cypher
-- Statistiques des relations
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(*) AS count
ORDER BY count DESC

-- Nombre de noeuds par type
MATCH (n)
RETURN labels(n)[0] AS node_type, count(*) AS count
ORDER BY count DESC
```

## Optimisation des performances

### Taille des lots

Ajustez la taille des lots pour les fichiers volumineux :

```bash
export DDIGRAPH_CHUNK_SIZE=500  # défaut : 200
```

### Concurrence d'écriture

Augmentez le nombre d'écrivains concurrents (nécessite suffisamment de connexions Neo4j) :

```bash
export DDIGRAPH_WRITER_CONCURRENCY=4  # défaut : 1
```

### Pool de connexions

Pour les scénarios à haut débit :

```python
settings = Settings(
    max_connection_pool_size=50,
    connection_timeout=30.0,
    transaction_timeout=120.0,
)
```

## Neo4jGraphAdapter

La classe `Neo4jGraphAdapter` gère les opérations spécifiques à Neo4j :

```python
from ddigraph.schema.neo4j_adapter import Neo4jGraphAdapter

adapter = Neo4jGraphAdapter(driver, settings)

# Écrire un lot
await adapter.write_batch(graph)

# Purger un jeu de données
await adapter.purge_dataset("my-dataset")
```

## Dépannage

### Problèmes de connexion

```python
# Tester la connexion
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
driver.verify_connectivity()
```

### Problèmes de mémoire

Pour les fichiers très volumineux, réduisez la taille des lots :

```bash
export DDIGRAPH_CHUNK_SIZE=100
```

### Délais d'expiration des transactions

Augmentez le délai d'expiration des transactions pour les réseaux lents :

```python
settings = Settings(transaction_timeout=300.0)  # 5 minutes
```

## Voir aussi

- [Architecture des adaptateurs](../user-guide/adapter.md) - Fonctionnement des adaptateurs
- [Optimisation des performances](../advanced/tuning.md) - Stratégies d'optimisation
- [Référence CLI](../reference/cli.md) - Options de la ligne de commande

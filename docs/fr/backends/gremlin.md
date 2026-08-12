# Gremlin

ddigraph prend en charge les bases de données graphe compatibles Gremlin via le framework Apache TinkerPop.

## Bases de données prises en charge

| Base de données | Connexion | Cas d'utilisation |
| --------------- | --------- | ----------------- |
| **Apache TinkerGraph** | En mémoire | Tests locaux, développement |
| **JanusGraph** | WebSocket/HTTP | Production, distribué |
| **Amazon Neptune** | WebSocket | Cloud AWS, service géré |
| **Azure Cosmos DB** | WebSocket | Cloud Azure, API Gremlin |

## Dépendances

GremlinPython est inclus avec ddigraph :

```bash
pip install ddigraph  # inclut gremlinpython
```

## Utilisation de base

### Connexion au serveur Gremlin

```python
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection

# Serveur TinkerPop local
connection = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
g = traversal().withRemote(connection)

# AWS Neptune
# connection = DriverRemoteConnection(
#     'wss://your-neptune-endpoint:8182/gremlin',
#     'g'
# )
```

### Charger des données DDI

```python
from ddigraph import DDIFragmentParser

parser = DDIFragmentParser()

for fragment in parser.parse("survey.xml"):
    # Créer un sommet
    vertex = (
        g.addV(fragment.element_type)
        .property("id", fragment.fragment_id)
        .property("label", fragment.label or "")
        .property("urn", fragment.urn or "")
        .next()
    )

    # Stocker pour la création des arêtes
    vertices[fragment.fragment_id] = vertex

# Créer les arêtes (seconde passe)
parser = DDIFragmentParser()
for fragment in parser.parse("survey.xml"):
    for rel_type, ref in fragment.references:
        if ref.id in vertices:
            g.V(vertices[fragment.fragment_id]).addE(rel_type).to(vertices[ref.id]).iterate()

connection.close()
```

## Exemple complet

Consultez `demo/load_gremlin.py` pour un exemple complet :

```python
"""Load DDI into Gremlin-compatible graph database."""

from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.graph_traversal import __

from ddigraph.ingest.fragment_loader import DDIFragmentParser


def load_ddi_to_gremlin(ddi_path: str, gremlin_endpoint: str = "ws://localhost:8182/gremlin"):
    """Parse DDI-L file and load into Gremlin database."""

    connection = DriverRemoteConnection(gremlin_endpoint, "g")
    g = traversal().withRemote(connection)

    try:
        # Clear existing data (optional)
        g.V().drop().iterate()

        parser = DDIFragmentParser()
        fragment_ids = set()

        # First pass: create all vertices
        for fragment in parser.parse(ddi_path):
            props = fragment.to_dict()

            vertex = g.addV(fragment.element_type)
            vertex = vertex.property("fragment_id", fragment.fragment_id)

            if fragment.label:
                vertex = vertex.property("label", fragment.label)
            if fragment.urn:
                vertex = vertex.property("urn", fragment.urn)
            if fragment.agency:
                vertex = vertex.property("agency", fragment.agency)
            if fragment.version:
                vertex = vertex.property("version", fragment.version)

            # Add type-specific properties
            if fragment.element_type == "QuestionItem":
                if props.get("question_text"):
                    vertex = vertex.property("question_text", props["question_text"])
            elif fragment.element_type == "Category":
                if props.get("category_label"):
                    vertex = vertex.property("category_label", props["category_label"])

            vertex.next()
            fragment_ids.add(fragment.fragment_id)

        print(f"Created {len(fragment_ids)} vertices")

        # Second pass: create edges
        edge_count = 0
        parser = DDIFragmentParser()

        for fragment in parser.parse(ddi_path):
            for rel_type, ref in fragment.references:
                if ref.id in fragment_ids:
                    g.V().has("fragment_id", fragment.fragment_id).addE(rel_type).to(
                        __.V().has("fragment_id", ref.id)
                    ).iterate()
                    edge_count += 1

        print(f"Created {edge_count} edges")

    finally:
        connection.close()


def query_examples(gremlin_endpoint: str = "ws://localhost:8182/gremlin"):
    """Example Gremlin queries."""

    connection = DriverRemoteConnection(gremlin_endpoint, "g")
    g = traversal().withRemote(connection)

    try:
        # Count vertices by type
        counts = g.V().groupCount().by(__.label()).next()
        print("Vertex counts by type:")
        for label, count in counts.items():
            print(f"  {label}: {count}")

        # Find all questions
        questions = g.V().hasLabel("QuestionItem").valueMap(True).toList()
        print(f"\nFound {len(questions)} questions")

        # Traverse from instrument to questions
        paths = (
            g.V()
            .hasLabel("Instrument")
            .repeat(__.out("HAS_CONSTRUCT"))
            .until(__.hasLabel("QuestionConstruct"))
            .out("ASKS_QUESTION")
            .path()
            .toList()
        )

        print(f"\nFound {len(paths)} paths from Instrument to Question")

    finally:
        connection.close()


if __name__ == "__main__":
    load_ddi_to_gremlin("data/Ireland_LabourSurvey.xml")
    query_examples()
```

## Requêtes Gremlin

### Traversées de base

```groovy
// Compter les sommets par libellé
g.V().groupCount().by(label)

// Trouver tous les QuestionItems
g.V().hasLabel('QuestionItem').valueMap(true)

// Obtenir un fragment spécifique par ID
g.V().has('fragment_id', 'abc-123').valueMap(true)
```

### Traversées de relations

```groovy
// De l'Instrument à tous les constructs
g.V().hasLabel('Instrument').out('HAS_CONSTRUCT').valueMap(true)

// Questions avec leurs listes de codes
g.V().hasLabel('QuestionItem')
    .as('q')
    .out('USES_CODELIST')
    .as('cl')
    .select('q', 'cl')
    .by(valueMap('label', 'question_text'))
    .by(valueMap('label'))

// Catégories dans une liste de codes
g.V().has('fragment_id', 'codelist-123')
    .out('HAS_CATEGORY')
    .valueMap('category_label')
```

### Requêtes de chemins

```groovy
// Chemin complet de l'Instrument aux Questions
g.V().hasLabel('Instrument')
    .repeat(out('HAS_CONSTRUCT'))
    .until(hasLabel('QuestionConstruct'))
    .out('ASKS_QUESTION')
    .path()
    .by('label')

// Branchements conditionnels
g.V().hasLabel('IfThenElse')
    .project('condition', 'then', 'else')
    .by('condition')
    .by(out('THEN').values('label'))
    .by(out('ELSE').values('label'))
```

## Configuration spécifique aux bases de données

### JanusGraph

```python
from gremlin_python.driver.serializer import GraphSONSerializersV3d0

connection = DriverRemoteConnection(
    "ws://localhost:8182/gremlin", "g", message_serializer=GraphSONSerializersV3d0()
)
```

### Amazon Neptune

```python
from gremlin_python.driver import client

# Authentification IAM
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Connexion WebSocket avec SigV4
connection = DriverRemoteConnection(
    "wss://your-cluster.region.neptune.amazonaws.com:8182/gremlin", "g"
)
```

### Azure Cosmos DB

```python
from gremlin_python.driver import client, serializer

# Cosmos DB nécessite un sérialiseur spécifique
connection = DriverRemoteConnection(
    "wss://your-account.gremlin.cosmos.azure.com:443/",
    "g",
    username="/dbs/your-database/colls/your-graph",
    password="your-primary-key",
)
```

## Chargement par lots

Pour les fichiers DDI volumineux, utilisez des écritures par lots :

```python
BATCH_SIZE = 100

vertices_batch = []
parser = DDIFragmentParser()

for i, fragment in enumerate(parser.parse("large_survey.xml")):
    vertices_batch.append(fragment)

    if len(vertices_batch) >= BATCH_SIZE:
        # Soumettre le lot
        for f in vertices_batch:
            g.addV(f.element_type).property("fragment_id", f.fragment_id).property(
                "label", f.label or ""
            ).iterate()
        vertices_batch = []
        print(f"Processed {i + 1} vertices")

# Dernier lot
for f in vertices_batch:
    g.addV(f.element_type).property("fragment_id", f.fragment_id).property(
        "label", f.label or ""
    ).iterate()
```

## Voir aussi

- [Architecture des adaptateurs](../user-guide/adapter.md) - Construction d'adaptateurs personnalisés
- [Modèle de relations](../user-guide/relationships.md) - Types de relations DDI
- [Documentation Apache TinkerPop](https://tinkerpop.apache.org/docs/current/)

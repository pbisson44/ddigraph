# Backend Gremlin

ddigraph écrit dans toute base de données graphe qui parle Gremlin, le
langage de requête d'Apache TinkerPop.

## Bases de données prises en charge

| Base de données | Connexion | Usage |
| --------------- | --------- | ----- |
| **Apache TinkerGraph** | En mémoire, via Gremlin Server | Tests locaux, développement |
| **JanusGraph** | WebSocket | Production, distribué |
| **Amazon Neptune** | WebSocket | Cloud AWS, service géré |
| **Azure Cosmos DB** | WebSocket | Cloud Azure, API Gremlin |

## Dépendances

gremlinpython est un extra optionnel :

```bash
pip install "ddigraph[gremlin]"
```

Pour essayer en local, lancez l'image officielle du serveur :

```bash
docker run --rm -p 8182:8182 tinkerpop/gremlin-server:3.8.2
```

## Charger du DDI

`write_gremlin` prend une source de traversée et un fichier. Elle renvoie le
nombre de sommets et d'arêtes écrits.

```python
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal

from ddigraph.backends.gremlin import write_gremlin

connection = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
g = traversal().with_(connection)

result = write_gremlin(g, "survey.xml")
print(result.nodes, "sommets,", result.relationships, "arêtes")

connection.close()
```

Le fichier peut être du DDI XML de n'importe quelle variante, ou un export
RDF comme `survey.ttl`. Vous pouvez aussi passer des blocs déjà obtenus avec
`ddigraph.iter_graph()`.

## Ce qui est écrit

- **Chaque sommet a une `node_key`.** C'est l'identité du nœud, sous forme
  de chaîne. Trouvez un sommet par son label et sa clé :
  `g.V().has("Variable", "node_key", "v1")`.
- **Le chargement peut être répété.** Chaque écriture est un upsert. Un
  sommet n'est créé que si aucun sommet n'a déjà ce label et cette clé. Une
  arête n'est créée que si le même type ne relie pas déjà les deux mêmes
  sommets. Chargez un fichier deux fois : rien ne change.
- **`label` et `id` sont renommés** en `ddi_label` et `ddi_id`. Certaines
  bases traitent ces noms comme le label et l'identifiant de l'élément
  lui-même. Cosmos DB les refuse purement et simplement.
- **Les listes deviennent des chaînes**, jointes avec `|`. Les bases
  diffèrent trop dans leur façon de stocker les listes pour s'y fier.

## Options

| Option | Défaut | Description |
| -------- | -------- | ------------- |
| `batch_size` | `50` | Sommets ou arêtes par requête |
| `cardinality` | `"single"` | Remplacer une valeur au rechargement. Passez `None` si votre base ne gère que les propriétés de type liste |
| `flavor` | détectée | Forcer une variante DDI |
| `dataset_id` | nom du fichier | Identifiant du jeu de données pour un Codebook |

Le résultat a aussi un compte `skipped`. Il compte les arêtes non écrites
faute de sommet d'extrémité. Il doit valoir zéro. Sinon, le journal indique
combien.

## Vitesse

Chaque requête coûte un aller-retour vers le serveur : les écritures sont
donc groupées. Sur un grand graphe, indexez d'abord `node_key` : chaque
upsert cherche un sommet par cette propriété. La façon d'ajouter un index
dépend de la base. JanusGraph passe par son API de gestion. Neptune indexe
déjà chaque propriété.

## Requêtes Gremlin

### Traversées de base

```groovy
// Compter les sommets par label
g.V().groupCount().by(label)

// Trouver tous les QuestionItems
g.V().hasLabel('QuestionItem').valueMap(true)

// Obtenir un nœud par sa clé
g.V().has('QuestionItem', 'node_key', 'urn:ddi:test.org:q1:1.0').valueMap(true)
```

### Traversées de relations

```groovy
// De l'Instrument à toutes ses constructions
g.V().hasLabel('Instrument').out('HAS_CONSTRUCT').valueMap(true)

// Questions avec leurs listes de codes
g.V().hasLabel('QuestionItem')
    .as('q')
    .out('USES_CODELIST')
    .as('cl')
    .select('q', 'cl')
    .by(valueMap('ddi_label', 'question_text'))
    .by(valueMap('ddi_label'))

// Catégories d'une liste de codes
g.V().has('CodeList', 'node_key', 'urn:ddi:test.org:cl1:1.0')
    .out('HAS_CATEGORY')
    .valueMap('category_label')
```

### Requêtes de chemins

```groovy
// Chemin complet de l'Instrument aux questions
g.V().hasLabel('Instrument')
    .repeat(out('HAS_CONSTRUCT'))
    .until(hasLabel('QuestionConstruct'))
    .out('REFERENCES_QUESTION')
    .path()
    .by('ddi_label')

// Branches conditionnelles
g.V().hasLabel('IfThenElse')
    .project('then', 'else')
    .by(out('THEN').values('ddi_label').fold())
    .by(out('ELSE').values('ddi_label').fold())
```

## Configuration propre à chaque base

### JanusGraph

```python
from gremlin_python.driver.serializer import GraphSONSerializersV3d0

connection = DriverRemoteConnection(
    "ws://localhost:8182/gremlin", "g", message_serializer=GraphSONSerializersV3d0()
)
```

### Amazon Neptune

```python
connection = DriverRemoteConnection(
    "wss://your-cluster.region.neptune.amazonaws.com:8182/gremlin", "g"
)
```

Avec l'authentification IAM, signez la requête WebSocket avec SigV4. La
documentation AWS explique comment.

### Azure Cosmos DB

```python
from gremlin_python.driver import serializer

connection = DriverRemoteConnection(
    "wss://your-account.gremlin.cosmos.azure.com:443/",
    "g",
    username="/dbs/your-database/colls/your-graph",
    password="your-primary-key",
    message_serializer=serializer.GraphSONSerializersV2d0(),
)
```

## Voir aussi

- [NetworkX](networkx.md) - Le même graphe, en mémoire
- [pandas](pandas.md) - Le même graphe, en deux tableaux
- [Modèle de relations](../user-guide/relationships.md) - Types de relations DDI
- [Documentation Apache TinkerPop](https://tinkerpop.apache.org/docs/current/)

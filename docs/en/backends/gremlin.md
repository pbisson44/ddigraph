# Gremlin Backend

ddigraph writes to any graph database that speaks Gremlin, the query
language of Apache TinkerPop.

## Supported Databases

| Database | Connection | Use Case |
| -------- | ---------- | -------- |
| **Apache TinkerGraph** | In-memory, via Gremlin Server | Local testing, development |
| **JanusGraph** | WebSocket | Production, distributed |
| **Amazon Neptune** | WebSocket | AWS cloud, managed service |
| **Azure Cosmos DB** | WebSocket | Azure cloud, Gremlin API |

## Dependencies

gremlinpython is an optional extra:

```bash
pip install "ddigraph[gremlin]"
```

To try it locally, run the official server image:

```bash
docker run --rm -p 8182:8182 tinkerpop/gremlin-server:3.8.2
```

## Loading DDI

`write_gremlin` takes a traversal source and a file. It returns how many
vertices and edges it wrote.

```python
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal

from ddigraph.backends.gremlin import write_gremlin

connection = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
g = traversal().with_(connection)

result = write_gremlin(g, "survey.xml")
print(result.nodes, "vertices,", result.relationships, "edges")

connection.close()
```

The file can be DDI XML of any flavor, or an RDF export such as
`survey.ttl`. You can also pass chunks you already have from
`ddigraph.iter_graph()`.

## What Gets Written

- **Every vertex has a `node_key`.** It is the node's identity, as a
  string. Find a vertex by its label and key:
  `g.V().has("Variable", "node_key", "v1")`.
- **Loading is safe to repeat.** Each write is an upsert. A vertex is
  created only if no vertex with that label and key exists. An edge is
  created only if the same type does not already join the same two
  vertices. Load a file twice and nothing changes.
- **`label` and `id` are renamed** to `ddi_label` and `ddi_id`. Some
  databases treat those names as the element's own label and id. Cosmos DB
  rejects them outright.
- **Lists become strings**, joined with `|`. Databases differ too much in
  how they store lists to rely on them.

## Options

| Option | Default | Description |
| -------- | --------- | ------------- |
| `batch_size` | `50` | Vertices or edges per request |
| `cardinality` | `"single"` | Replace a value on reload. Pass `None` if your database only supports list properties |
| `flavor` | detected | Force a DDI flavor |
| `dataset_id` | file stem | Dataset id for Codebook input |

The result also has a `skipped` count. It counts edges that could not be
written because an end vertex was missing. It should be zero. If it is
not, the log names how many.

## Speed

Each request costs a round trip to the server, so writes go in batches. On
a large graph, index `node_key` first: every upsert looks a vertex up by
it. How to add an index depends on the database. JanusGraph uses its
management API. Neptune indexes every property already.

## Gremlin Queries

### Basic Traversals

```groovy
// Count vertices by label
g.V().groupCount().by(label)

// Find all QuestionItems
g.V().hasLabel('QuestionItem').valueMap(true)

// Get one node by its key
g.V().has('QuestionItem', 'node_key', 'urn:ddi:test.org:q1:1.0').valueMap(true)
```

### Relationship Traversals

```groovy
// From Instrument to all constructs
g.V().hasLabel('Instrument').out('HAS_CONSTRUCT').valueMap(true)

// Questions with their code lists
g.V().hasLabel('QuestionItem')
    .as('q')
    .out('USES_CODELIST')
    .as('cl')
    .select('q', 'cl')
    .by(valueMap('ddi_label', 'question_text'))
    .by(valueMap('ddi_label'))

// Categories in a code list
g.V().has('CodeList', 'node_key', 'urn:ddi:test.org:cl1:1.0')
    .out('HAS_CATEGORY')
    .valueMap('category_label')
```

### Path Queries

```groovy
// Full path from Instrument to Questions
g.V().hasLabel('Instrument')
    .repeat(out('HAS_CONSTRUCT'))
    .until(hasLabel('QuestionConstruct'))
    .out('REFERENCES_QUESTION')
    .path()
    .by('ddi_label')

// Conditional branches
g.V().hasLabel('IfThenElse')
    .project('then', 'else')
    .by(out('THEN').values('ddi_label').fold())
    .by(out('ELSE').values('ddi_label').fold())
```

## Database-Specific Configuration

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

With IAM authentication on, sign the WebSocket request with SigV4. The
AWS documentation shows how.

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

## See Also

- [NetworkX](networkx.md) - The same graph, in memory
- [pandas](pandas.md) - The same graph, as two tables
- [Relationship Model](../user-guide/relationships.md) - DDI relationship types
- [Apache TinkerPop Documentation](https://tinkerpop.apache.org/docs/current/)

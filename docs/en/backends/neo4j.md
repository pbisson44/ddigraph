# Neo4j Backend

Neo4j is the default and most fully-featured backend for ddigraph. It provides native graph storage
with powerful Cypher query capabilities.

## Setup

### Docker (Recommended for Development)

```bash
docker run -d --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:latest
```

### Neo4j Desktop

Download from [neo4j.com/download](https://neo4j.com/download/) and create a local database.

### Neo4j Aura (Cloud)

Create a free instance at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura/).

## Configuration

Set environment variables:

```bash
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=your-password
export DDIGRAPH_NEO4J_DATABASE=neo4j  # optional, defaults to 'neo4j'
```

Or use a `.env` file:

```ini
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=your-password
```

## Loading Data

### CLI

```bash
# Bootstrap schema (creates constraints and indexes)
ddigraph bootstrap

# Load DDI Codebook
ddigraph load survey.xml --dataset-id my-survey

# Load DDI-L FragmentInstance
ddigraph load questionnaire.xml

# Replace existing data
ddigraph load survey.xml --dataset-id my-survey --replace
```

### Python API

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

    # Bootstrap schema
    await ensure_schema(driver, include_fragments=True)

    # Load data
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

## Schema

ddigraph creates the following Neo4j schema:

### Constraints

Uniqueness constraints are created for each node type:

```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Dataset) REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:QuestionItem) REQUIRE n.fragment_id IS UNIQUE
-- etc.
```

### Indexes

Secondary indexes for common query patterns:

```cypher
CREATE INDEX IF NOT EXISTS FOR (n:Variable) ON (n.label)
CREATE INDEX IF NOT EXISTS FOR (n:QuestionItem) ON (n.question_text)
-- etc.
```

## Query Examples

### DDI Codebook Queries

```cypher
-- All variables in a dataset
MATCH (d:Dataset {id: 'demo'})<-[:IN_DATASET]-(v:Variable)
RETURN v.name, v.label, v.description

-- Variables with their concepts
MATCH (v:Variable)-[:USES_CONCEPT]->(c:Concept)
RETURN v.name, c.name

-- Questions and their variables
MATCH (v:Variable)-[:ASKED_AS]->(q:Question)
RETURN v.name, q.text

-- Variable groups
MATCH (vg:VarGroup)-[:GROUPS]->(v:Variable)
RETURN vg.label, collect(v.name) AS variables
```

### DDI-L FragmentInstance Queries

```cypher
-- Questionnaire flow from instrument
MATCH path = (i:Instrument)-[:HAS_CONSTRUCT*1..10]->(c)
RETURN path

-- Conditional branching
MATCH (ite:IfThenElse)-[:THEN]->(then_seq)
OPTIONAL MATCH (ite)-[:ELSE]->(else_seq)
RETURN ite.condition, then_seq.label, else_seq.label

-- Questions with code lists
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN q.name, q.question_text, cl.name, collect(cat.category_label) AS options

-- Find all questions in a sequence
MATCH (s:Sequence)-[:HAS_CONSTRUCT*]->(qc:QuestionConstruct)-[:ASKS_QUESTION]->(q)
RETURN s.label, q.name, q.question_text
```

### Cross-Format Queries

```cypher
-- Relationship statistics
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(*) AS count
ORDER BY count DESC

-- Node type counts
MATCH (n)
RETURN labels(n)[0] AS node_type, count(*) AS count
ORDER BY count DESC
```

## Performance Tuning

### Batch Size

Adjust batch size for large files:

```bash
export DDIGRAPH_CHUNK_SIZE=500  # default: 200
```

### Writer Concurrency

Increase concurrent writers (requires sufficient Neo4j connections):

```bash
export DDIGRAPH_WRITER_CONCURRENCY=4  # default: 1
```

### Connection Pool

For high-throughput scenarios:

```python
settings = Settings(
    max_connection_pool_size=50,
    connection_timeout=30.0,
    transaction_timeout=120.0,
)
```

## Neo4jGraphAdapter

The `Neo4jGraphAdapter` class handles Neo4j-specific operations:

```python
from ddigraph.schema.neo4j_adapter import Neo4jGraphAdapter

adapter = Neo4jGraphAdapter(driver, settings)

# Write a batch
await adapter.write_batch(graph)

# Purge a dataset
await adapter.purge_dataset("my-dataset")
```

## Troubleshooting

### Connection Issues

```python
# Test connection
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
driver.verify_connectivity()
```

### Memory Issues

For very large files, reduce batch size:

```bash
export DDIGRAPH_CHUNK_SIZE=100
```

### Transaction Timeouts

Increase transaction timeout for slow networks:

```python
settings = Settings(transaction_timeout=300.0)  # 5 minutes
```

## See Also

- [Adapter Architecture](../user-guide/adapter.md) - How adapters work
- [Performance Tuning](../advanced/tuning.md) - Optimization strategies
- [CLI Reference](../reference/cli.md) - Command-line options

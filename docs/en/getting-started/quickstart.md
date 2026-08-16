# Quick Start

This guide shows you the fastest way to load a DDI file into a graph database.
We'll start with **Neo4j** — the most common setup — then show the other options.

If you haven't installed ddigraph yet, start with [Installation](installation.md).

---

## Step 1 — Pick your database

Pick the database you want to use. If you're not sure, choose Neo4j — it's the most
fully featured option and the easiest to get started with.

=== "Neo4j"

    **What is this?** Neo4j is a graph database that stores data as nodes and relationships.
    It's the recommended choice for most users.

    ```bash
    # Start Neo4j with Docker (one-time setup)
    docker run -d --name neo4j \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/password \
        neo4j:latest

    # Tell ddigraph where Neo4j is
    export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
    export DDIGRAPH_NEO4J_USER=neo4j
    export DDIGRAPH_NEO4J_PASSWORD=password

    # Set up the database schema (run once before your first load)
    ddigraph bootstrap

    # Load your DDI file
    ddigraph load survey.xml --dataset-id demo
    ```

    After this runs, your DDI metadata is in Neo4j as a graph.
    Open `http://localhost:7474` in your browser to explore it visually.

    **What does `bootstrap` do?**
    It creates the indexes and constraints Neo4j needs to store DDI data correctly.
    It's safe to run more than once — if the schema already exists, nothing changes.

=== "RDF/SPARQL"

    **What is this?** RDF (Resource Description Framework) is a format for representing
    data as linked triples. Use this if you work with semantic web tools or triplestores
    like Virtuoso, GraphDB, or Stardog.

    ```python
    import ddigraph

    # One call. The vocabulary, the SKOS mapping and the IRIs are all
    # handled for you; see the RDF backend guide for what comes out.
    result = ddigraph.export("survey.xml", "output.ttl", format="turtle")
    print(result.triples, "triples")
    ```

=== "NetworkX"

    **What is this?** NetworkX is a Python library for analyzing graphs in memory —
    no separate database required. Use this for quick local analysis or prototyping.

    ```python
    import networkx as nx

    from ddigraph import iter_graph


    def node_id(node):
        return "|".join(str(v) for _k, v in sorted(node.identity.items()))


    G = nx.MultiDiGraph()

    for chunk in iter_graph("survey.xml"):
        for node in chunk.nodes:
            G.add_node(node_id(node), node_type=node.label, **node.properties)
        for edge in chunk.relationships:
            G.add_edge(node_id(edge.start), node_id(edge.end), key=edge.type)

    print(f"Loaded {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    ```

=== "Gremlin"

    **What is this?** Gremlin is a graph query language supported by databases like
    JanusGraph, Amazon Neptune, and Azure Cosmos DB.

    ```python
    from gremlin_python.process.anonymous_traversal import traversal
    from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
    from ddigraph import iter_graph

    connection = DriverRemoteConnection("ws://localhost:8182/gremlin", "g")
    g = traversal().withRemote(connection)

    for chunk in iter_graph("survey.xml"):
        for node in chunk.nodes:
            node_id = next(iter(node.identity.values()))
            g.addV(node.label).property("id", node_id).property(
                "name", node.properties.get("label", "")
            ).iterate()

    connection.close()
    ```

---

## Step 2 — Check the format (optional)

ddigraph automatically detects whether your file is DDI Codebook, DDI Lifecycle, or DDI-CDI.
You can check manually with:

```python
from ddigraph import detect_ddi_format

format_type = detect_ddi_format("survey.xml")
print(format_type)  # "codebook", "lifecycle", or "cdi"
```

**What do these formats mean?**

| Format | Root XML element | Use when |
|---|---|---|
| `codebook` | `<codeBook>` or `<codebook>` | Traditional survey archives |
| `lifecycle` | `<FragmentInstance>` | Questionnaire design tools (DDI-L 3.2 / 3.3) |
| `cdi` | DDI-CDI namespace | Cross-domain integration projects |

If you're not sure which format you have, run `detect_ddi_format` and it will tell you.

The format is only the first question. To see what is actually inside,
preview it. This needs no database:

<!-- runnable -->
```bash
ddigraph preview "$FIXTURE"
```

It prints a count for each node type and each relationship, so you know
what a load would produce before you run one. `--format html -o
preview.html` writes the same summary as a page you can open in a
browser. See the [CLI reference](../reference/cli.md#previewing-a-file)
for the other formats.

---

## Step 3 — Load from Python

The Python API mirrors the CLI. One call loads a file. It detects the
format, sets up the schema, and writes to your target:

```python
import ddigraph

result = ddigraph.load(
    "survey.xml",
    target="neo4j://localhost:7687",
    dataset_id="my-survey",
)
print(result.flavor, result.nodes_written, result.relationships_written)
```

`target` is a Neo4j URL (`bolt://...` or `neo4j://...`). Leave it out
to use the connection from your environment. There is also an async
form, `ddigraph.aload(...)`, with the same arguments. For the other
backends (RDF, Gremlin, NetworkX, pandas), use the parser plus an
adapter — see the [Backends](../backends/neo4j.md) pages and the
per-backend examples below.

Check a file's format without loading it:

```python
import ddigraph

print(ddigraph.detect("survey.xml"))  # 'codebook', 'lifecycle', or 'cdi'
```

### More control (advanced)

If you need to drive the loaders yourself, the lower-level classes are
still available:

```python
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph import DDILoader, DDIFragmentLoader, detect_ddi_format, iter_graph
from ddigraph.config import Settings
from ddigraph.graph.bootstrap import ensure_schema


async def load_ddi(path: str, dataset_id: str = "default"):
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    try:
        # Set up schema (safe to run every time)
        await ensure_schema(driver, include_fragments=True)

        # Pick the right loader based on format
        fmt = detect_ddi_format(path)
        if fmt == "lifecycle":
            loader = DDIFragmentLoader(driver, settings=settings)
            result = await loader.load(path)
        elif fmt == "cdi":
            # DDI-CDI has no dedicated loader class. Stream it through the
            # backend-neutral view instead, which every flavor supports.
            from ddigraph.graph.writer import GraphChunkWriter

            writer = GraphChunkWriter(driver, database=settings.neo4j_database)
            result = await writer.write(iter_graph(path))
        else:
            loader = DDILoader(driver, settings=settings)
            result = await loader.load(path, dataset_id=dataset_id)

        return result
    finally:
        await driver.close()


result = asyncio.run(load_ddi("survey.xml", "my-survey"))
print(f"Loaded: {result}")
```

---

## Step 4 — Explore your data

Now that your data is loaded, run some queries to see what's there.

### In Neo4j Browser (`http://localhost:7474`)

```cypher
-- Count all nodes by type
MATCH (n) RETURN labels(n) AS type, count(n) AS count ORDER BY count DESC

-- List all variables in a dataset
MATCH (d:Dataset {id: 'demo'})<-[:IN_DATASET]-(v:Variable)
RETURN v.name, v.label

-- Questions with their answer lists
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
RETURN q.name, q.question_text, cl.name
```

### In Python (NetworkX)

```python
import networkx as nx

# Find paths between two nodes
paths = list(nx.all_simple_paths(G, source="instrument-1", target="question-5", cutoff=5))

# Export for visualization
nx.write_graphml(G, "ddi_graph.graphml")
```

---

## What's next?

- **[Your First Queries](first-queries.md)** — step-by-step guide to exploring your data
- **[Relationship Model](../user-guide/relationships.md)** — all node and relationship types
- **[Performance Tuning](../advanced/tuning.md)** — optimize for large files
- **[CLI Reference](../reference/cli.md)** — all available commands

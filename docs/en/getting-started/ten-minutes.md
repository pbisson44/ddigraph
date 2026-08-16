# 10 Minutes to ddigraph

This tutorial covers the basics of **ddigraph** in about ten minutes. By the end, you will have loaded a DDI XML file into a graph database. You will also have run your first queries against it.

## What is DDI?

The [Data Documentation Initiative (DDI)](https://ddialliance.org/) is a global standard. It describes survey data, questionnaires, and statistical metadata (data about the data). DDI files are XML documents. They capture variables, questions, code lists, concepts, and the links among them. That kind of richly connected metadata works well in a graph database.

ddigraph reads DDI XML and turns it into a knowledge graph. It fully supports Neo4j. It also supports other backends: RDF, Gremlin, and NetworkX.

---

## Install ddigraph

```bash
pip install ddigraph
```

!!! tip "Python version"
    ddigraph requires **Python 3.12-3.14**. Verify your version with `python --version`.

The package adds all required dependencies for you. These include lxml, the neo4j driver, pydantic-settings, networkx, rdflib, gremlinpython, and more.

---

## Start Neo4j

The fastest way to get a local Neo4j instance is Docker:

```bash
docker run --rm --name neo4j-demo \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5
```

After a few seconds the database is reachable at `bolt://localhost:7687` and the browser UI is available at <http://localhost:7474>.

!!! note "Neo4j Aura"
    If you prefer a managed instance, create a free Neo4j Aura database at <https://neo4j.com/cloud/aura-free/> and use the `neo4j+s://` URI it provides.

---

## Set Environment Variables

Tell ddigraph how to reach Neo4j:

```bash
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=password
```

Alternatively, place these in a `.env` file in your working directory -- ddigraph picks it up automatically.

```ini
# .env
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=password
```

---

## Bootstrap the Schema

Before loading any data, create the uniqueness constraints and indexes that the loader relies on:

```bash
# Codebook schema only
ddigraph bootstrap

# Include DDI-L FragmentInstance schema as well
ddigraph bootstrap
```

The command is idempotent -- running it twice is harmless.

---

## Load a DDI File

### Via the CLI

The CLI auto-detects whether the file uses DDI Codebook or DDI-L FragmentInstance format:

```bash
# DDI Codebook -- a dataset-id is required
ddigraph load codebook_survey.xml --dataset-id my-survey

# DDI-L FragmentInstance -- no dataset-id needed
ddigraph load questionnaire.xml
```

A successful run prints a summary like:

```text
Ingestion complete: Category=45, CodeList=12, Instrument=1, QuestionItem=120, Sequence=30
```

!!! tip "Dry run"
    Add `--dry-run` to validate the XML without writing anything to Neo4j:
    ```bash
    ddigraph load survey.xml --dataset-id demo --dry-run
    ```

### Via the Python API

```python
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph import DDILoader, DDIFragmentLoader, detect_ddi_format, Settings


async def main():
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    path = "survey.xml"

    # Auto-detect format
    fmt = detect_ddi_format(path)
    print(f"Detected format: {fmt}")

    if fmt == "lifecycle":
        loader = DDIFragmentLoader(driver, settings=settings)
        result = await loader.load(path)
    else:
        loader = DDILoader(driver, settings=settings)
        result = loader.load(
            path,
            dataset_id="my-survey",
            dataset_name="My Survey",
        )

    print(result)
    await driver.close()


asyncio.run(main())
```

---

## Explore the Graph with Cypher

Open the Neo4j Browser at <http://localhost:7474> and try some queries.

**Count nodes by label:**

```cypher
CALL db.labels() YIELD label
RETURN label, count { MATCH (n) WHERE label IN labels(n) RETURN n } AS count
ORDER BY count DESC
```

**List all datasets:**

```cypher
MATCH (d:Dataset) RETURN d.id, d.name
```

**Find variables linked to a question:**

```cypher
MATCH (v:Variable)-[:ASKS]->(q:Question)
RETURN v.label AS variable, q.text AS question_text
LIMIT 10
```

**Explore the control flow of a DDI-L instrument:**

```cypher
MATCH path = (i:Instrument)-[:HAS_CONSTRUCT*1..3]->(n)
RETURN path
LIMIT 50
```

**Find questions that reference a specific code list:**

```cypher
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
RETURN q.name AS question, cl.name AS codelist, cl.code_count
ORDER BY cl.code_count DESC
LIMIT 10
```

---

## Auto-detecting DDI Format

ddigraph can tell you which format a file uses without loading it:

```bash
ddigraph detect survey.xml
# Format: codebook
# File: survey.xml

ddigraph detect questionnaire.xml --json
# {"path":"questionnaire.xml","format":"lifecycle"}
```

In Python:

```python
from ddigraph import detect_ddi_format

fmt = detect_ddi_format("my_file.xml")
print(fmt)  # "codebook" or "lifecycle"
```

The detection reads only the root XML element, so it is fast even on large files.

---

## Using Alternative Backends

Neo4j is the primary backend, but ddigraph can write to other graph systems through its adapter pattern. Here is a quick NetworkX example that requires no database at all:

```python
import asyncio
from pathlib import Path
import networkx as nx
from ddigraph.ingest.fragment_loader import DDIFragmentParser


async def load_to_networkx(path: str) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    parser = DDIFragmentParser(Path(path))

    for batch in parser.parse_batches():
        # Add nodes
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                props = fragment.to_dict()
                node_id = props.pop("fragment_id")
                G.add_node(node_id, node_type=element_type, **props)

        # Add edges
        for from_id, rel_type, to_id in batch.relationships:
            G.add_edge(from_id, to_id, key=rel_type, type=rel_type)

    return G


G = asyncio.run(load_to_networkx("questionnaire.xml"))
print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
```

!!! tip "More backends"
    RDF ships with the package: use `ddigraph export`. See the
    [RDF backend guide](../backends/rdf.md).

    For the others, the `demo/` directory has worked examples for
    [Gremlin](https://github.com/pbisson44/ddigraph/blob/main/demo/load_gremlin.py) and
    [pandas](https://github.com/pbisson44/ddigraph/blob/main/demo/load_pandas.py).
    Both are examples rather than shipped adapters.

---

## Next Steps

You now know the core workflow: install, connect, bootstrap, load, query. Here are some directions to explore next:

- **[Configuration Reference](../reference/configuration.md)** -- every environment variable and CLI flag in one place.
- **[CLI Reference](../reference/cli.md)** -- full command documentation including ingestion tuning and TLS options.
- **[Architecture](../user-guide/architecture.md)** -- how streaming parsing, batching, and async writes fit together.
- **[DDI-L FragmentInstance Guide](../user-guide/fragments.md)** -- deep dive into DDI Lifecycle support.
- **[Adapter Pattern](../user-guide/adapter.md)** -- writing your own backend adapter.
- **[Performance Tuning](../advanced/tuning.md)** -- chunk sizes, concurrency, and retry knobs.
- **[FAQ](../project/faq.md)** -- common questions and troubleshooting.

Happy graphing!

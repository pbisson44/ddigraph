# FAQ

Frequently asked questions about ddigraph.

---

## What DDI formats are supported?

ddigraph supports three DDI formats:

| Format | DDI Version | Root Element | Use Case |
| --- | --- | --- | --- |
| **DDI Codebook** | 2.5 / 2.6 | `<codeBook>` | Survey archives, data catalogs, variable-level metadata |
| **DDI Lifecycle** | 3.2 / 3.3 | `<FragmentInstance>` | Questionnaire flows, CAPI/CAWI instruments, complex study designs |
| **DDI-CDI** | 1.0 | `<Wrapper>` | Cross-domain integration, variable harmonisation, concept mapping |

The CLI auto-detects the format by inspecting the XML root element and namespace. You can also
force a specific format with `--format codebook` or `--format lifecycle`.

```bash
# Auto-detect (default)
ddigraph load survey.xml --dataset-id demo

# Explicit format
ddigraph load survey.xml --format codebook --dataset-id demo
ddigraph load questionnaire.xml --format lifecycle
```

---

## Do I need Neo4j to use ddigraph?

No. While Neo4j is the default and most fully supported backend, ddigraph supports a
multi-backend adapter architecture. You can load DDI data into:

- **Neo4j** -- full support with Bolt driver, schema bootstrap, UNWIND batching
- **RDF / SPARQL** -- via rdflib, with export to Turtle, N-Triples, RDF/XML, JSON-LD
- **Gremlin** -- compatible with JanusGraph, Amazon Neptune, Azure Cosmos DB
- **NetworkX** -- in-memory graph for local analysis, no external services needed
- **pandas** -- DataFrames for tabular analysis and Excel/CSV export

!!! tip "Quick start without a database"
    For exploration and prototyping, the NetworkX backend requires no external services:

    ```python
    import networkx as nx
    from ddigraph import DDIFragmentParser

    G = nx.MultiDiGraph()
    parser = DDIFragmentParser()
    for fragment in parser.parse("survey.xml"):
        G.add_node(fragment.fragment_id, label=fragment.element_type)
    print(f"Loaded {G.number_of_nodes()} nodes")
    ```

See [Graph Backends](../backends/neo4j.md) for detailed setup guides for each backend.

---

## How do I handle large files?

ddigraph is designed for large files. The streaming `iterparse`-based parser processes XML
incrementally, so memory usage stays bounded regardless of file size.

Key strategies for large files:

1. **Tune batch size**: Increase `--chunk-size` to reduce transaction overhead for large files.
   Start with 500-1000 for files with 10,000+ elements.

    ```bash
    ddigraph load large_survey.xml --dataset-id demo --chunk-size 1000
    ```

2. **Increase writer concurrency** (Codebook only): Allow multiple batches to flush in parallel.

    ```bash
    ddigraph load large_codebook.xml --dataset-id demo \
        --chunk-size 1000 --writer-concurrency 4 --queue-maxsize 4
    ```

3. **Monitor with batch metrics**: Enable per-batch timing to identify bottlenecks.

    ```bash
    ddigraph load large_survey.xml --dataset-id demo --batch-metrics
    ```

4. **Increase transaction timeout**: Large batches may exceed the default server-side timeout.

    ```bash
    export DDIGRAPH_TRANSACTION_TIMEOUT=60
    ```

See [Performance Tuning](../advanced/tuning.md) for detailed recommendations.

---

## Why is ingestion slow?

Common causes of slow ingestion and their solutions:

**1. Missing indexes or constraints**

Always run schema bootstrap before loading data:

```bash
ddigraph bootstrap
```

Without indexes, Neo4j performs full scans for every MERGE operation.

**2. Batch size too small**

The default `chunk_size` of 200 is conservative. For large files, increase it:

```bash
ddigraph load file.xml --dataset-id demo --chunk-size 1000
```

**3. Network latency to Neo4j**

For cloud instances (Neo4j Aura, remote clusters), network round-trips dominate. Use larger
batches and increase retry tolerance:

```bash
ddigraph load file.xml --dataset-id demo \
    --chunk-size 500 \
    --write-retry-attempts 5 \
    --write-retry-base-delay 2.0
```

**4. Neo4j server resources**

Check that the Neo4j instance has sufficient memory and CPU. The Neo4j browser
(`http://localhost:7474`) shows active queries and resource usage.

!!! note "DDI-L performance"
    DDI-L FragmentInstance ingestion uses UNWIND batching, reducing Neo4j queries to ~30 for a
    typical file.

---

## How do I connect to Neo4j Aura (cloud)?

Neo4j Aura uses encrypted connections. Use the `neo4j+s://` URI scheme, which enables TLS
automatically:

```bash
export DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=your-aura-password
```

Then run commands as usual:

```bash
ddigraph bootstrap
ddigraph load survey.xml --dataset-id demo
```

!!! tip "Aura tuning"
    Cloud instances have higher network latency. Consider these settings:

    ```bash
    export DDIGRAPH_CONNECTION_TIMEOUT=10
    export DDIGRAPH_CHUNK_SIZE=200
    export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
    export DDIGRAPH_WRITE_RETRY_BASE_DELAY=2.0
    ```

You do **not** need `--encrypted` or `--trusted-certificates` when using the `neo4j+s://` scheme,
as TLS is handled by the URI scheme itself.

---

## Can I use ddigraph without async?

The `GraphWriteAdapter` protocol accepts both synchronous and asynchronous implementations.
Your adapter can return `None` (sync) or `Awaitable[None]` (async):

```python
from ddigraph.schema.adapter import GraphWriteAdapter

# Synchronous adapter
class SyncAdapter:
    def write_batch(self, graph, **kwargs) -> None:
        for node in graph.nodes():
            self.backend.create_node(node["label"], node["properties"])

    def purge_dataset(self, dataset_id, **kwargs) -> None:
        self.backend.delete_by_dataset(dataset_id)
```

The CLI and built-in loaders use `asyncio.run()` internally, so you do not need to manage an
event loop yourself when using the command line. The async machinery is transparent.

---

## How do I add a custom graph backend?

Implement the `GraphWriteAdapter` protocol with two methods: `write_batch` and `purge_dataset`.

```python
from ddigraph.schema.adapter import GraphWriteAdapter
from ddigraph.schema.ddi_graph import DDIIngestGraph

class MyBackendAdapter:
    async def write_batch(
        self,
        graph: DDIIngestGraph,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> None:
        for node in graph.nodes():
            await self.backend.create(node["label"], node["properties"])
        for rel in graph.relationships():
            await self.backend.link(rel["start"], rel["end"], rel["type"])

    async def purge_dataset(
        self,
        dataset_id: str,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> None:
        await self.backend.delete_all(dataset_id)
```

Then pass your adapter to the loader:

```python
from ddigraph.ingest.loader import DDILoader

adapter = MyBackendAdapter()
loader = DDILoader(driver=None, adapter=adapter)
```

See [Adapter Architecture](../user-guide/adapter.md) for complete examples and
[Contributing](contributing.md) for guidelines on submitting new backends.

---

## What Python versions are supported?

ddigraph supports **Python 3.12-3.14**. This is specified
in `pyproject.toml`:

```toml
requires-python = ">=3.12,<3.15"
```

Python 3.12-3.14 is required for:

- Modern `type` statement syntax and `type` aliases
- `collections.abc` improvements used in protocol definitions
- Performance improvements in `asyncio`

---

## How do I migrate from neo4ddi to ddigraph?

The package was renamed from `neo4ddi` to `ddigraph` to reflect multi-backend support.

### Step 1: Update the package

```bash
pip uninstall neo4ddi
pip install ddigraph
```

### Step 2: Update imports

```python
# Before
from neo4ddi.config import Settings
from neo4ddi.ingest.loader import DDILoader

# After
from ddigraph.config import Settings
from ddigraph.ingest.loader import DDILoader
```

### Step 3: Update environment variables

The `DDIGRAPH_` prefix is now preferred, but `NEO4DDI_` is still recognized:

```bash
# Before
export NEO4DDI_NEO4J_URI=bolt://localhost:7687

# After (preferred)
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
```

### Step 4: Update CLI usage

The CLI command changed from `neo4ddi` to `ddigraph`:

```bash
# Before
neo4ddi load survey.xml --dataset-id demo

# After
ddigraph load survey.xml --dataset-id demo
```

!!! info "Backward compatibility"
    The `NEO4DDI_` environment variable prefix and bare `NEO4J_` variables are still recognized
    for backward compatibility. The `DDIGRAPH_` prefix takes precedence when multiple prefixes
    are set.

---

## Troubleshooting: Connection Errors

### "ServiceUnavailable: Unable to retrieve routing information"

This usually means ddigraph cannot reach the Neo4j server.

1. **Check that Neo4j is running**:

    ```bash
    # Docker
    docker ps | grep neo4j

    # Or try connecting directly
    curl -s http://localhost:7474
    ```

2. **Verify the URI**: Make sure `DDIGRAPH_NEO4J_URI` uses the correct protocol and port:
    - Local: `bolt://localhost:7687`
    - Aura: `neo4j+s://xxxx.databases.neo4j.io`

3. **Check credentials**: Verify username and password are correct.

4. **Firewall/network**: Ensure port 7687 (Bolt) is open and accessible.

### "AuthError: The client is unauthorized"

The username or password is incorrect. Double-check:

```bash
echo $DDIGRAPH_NEO4J_USER
echo $DDIGRAPH_NEO4J_PASSWORD
```

### "ClientError: database not found"

The specified database does not exist. Check `DDIGRAPH_NEO4J_DATABASE` (default: `neo4j`).
Neo4j Community Edition only supports the default `neo4j` database.

---

## Troubleshooting: Memory Errors

### "MemoryError" or process killed during parsing

ddigraph uses streaming XML parsing (`iterparse`), which should keep memory usage bounded. If
you still hit memory limits:

1. **Reduce batch size**:

    ```bash
    ddigraph load file.xml --dataset-id demo --chunk-size 50
    ```

2. **Reduce queue size** (Codebook format):

    ```bash
    ddigraph load file.xml --dataset-id demo --queue-maxsize 1
    ```

3. **Reduce writer concurrency**:

    ```bash
    ddigraph load file.xml --dataset-id demo --writer-concurrency 1
    ```

4. **Check for non-streaming parsing**: If you are using a custom adapter, make sure you are not
   accumulating all nodes in memory. Process and discard batches incrementally.

!!! tip "Monitoring memory"
    Use `--batch-metrics` to see per-batch statistics. If batch sizes look unexpectedly large,
    your `chunk_size` may be too high for the available memory.

---

## How is ddigraph different from other DDI tools?

ddigraph is specifically designed for **graph-based** representations of DDI metadata. Here is
how it compares to other approaches:

| Aspect | ddigraph | Colectica | NESSTAR | Custom scripts |
| --- | --- | --- | --- | --- |
| **Output** | Knowledge graph (Neo4j, RDF, etc.) | Relational database | Proprietary format | Varies |
| **DDI formats** | Codebook + Lifecycle + CDI | Lifecycle | Codebook | Usually one |
| **Graph backends** | 5 (Neo4j, RDF, Gremlin, NetworkX, pandas) | N/A | N/A | Usually one |
| **Streaming** | Yes (bounded memory) | Yes | Varies | Usually no |
| **Open source** | Yes (MIT) | No (commercial) | No (discontinued) | Varies |
| **Extensible** | Adapter protocol | Plugin API | No | By definition |

Key differentiators:

- **Graph-native**: ddigraph preserves the inherent graph structure of DDI metadata (variables
  linked to questions linked to concepts linked to code lists), making traversals and path
  queries natural.
- **Multi-backend**: A single parsing pipeline feeds any graph backend through the
  `GraphWriteAdapter` interface.
- **Streaming architecture**: Memory usage is bounded regardless of file size, making it suitable
  for large national survey archives.
- **Production-ready**: Built-in retry logic, structured logging, and configurable back-pressure
  support automated pipelines and CI/CD workflows.

---

Still have questions? Open an issue on [GitHub](https://github.com/pbisson44/ddigraph/issues).

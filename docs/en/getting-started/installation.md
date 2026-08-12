# Installation

## Requirements

- Python 3.12 to 3.14
- pip, uv, pipx, or another Python package manager

## Basic Installation

Install ddigraph from PyPI:

```bash
pip install ddigraph
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv pip install ddigraph
```

The base install is small. It pulls in only six runtime packages:
lxml, neo4j, orjson, pydantic, pydantic-settings, and xmlschema. The
Neo4j driver is included, so the Neo4j backend works out of the box.
Other backends are opt-in extras (see below).

## Backend Extras

Each non-Neo4j backend ships as an optional extra. Install only the
ones your target needs:

```bash
pip install "ddigraph[rdf]"        # RDF / SPARQL (rdflib)
pip install "ddigraph[gremlin]"    # Gremlin databases (gremlinpython)
pip install "ddigraph[networkx]"   # In-memory NetworkX graphs
pip install "ddigraph[pandas]"     # pandas / Excel export
pip install "ddigraph[sdmx]"       # SDMX interoperability
pip install "ddigraph[all]"        # every backend extra at once
```

If an extra is missing, the matching backend raises a clear error that
names the package to install. Nothing else breaks.

## Development and Documentation Extras

For tests, linting, type-checking, and packaging audits:

```bash
pip install "ddigraph[dev]"
```

For building the documentation site:

```bash
pip install "ddigraph[docs]"
```

Combine them:

```bash
pip install "ddigraph[dev,docs]"
```

## From Source

Clone the repository, then install it in editable mode:

```bash
git clone https://github.com/pbisson44/neo4ddi.git
cd neo4ddi
pip install -e ".[dev,docs]"
```

## Verifying Installation

```python
import ddigraph

print(ddigraph.__version__)
```

Or from the command line:

```bash
ddigraph version
```

## Backend Services

Some backends need a running service. Others run in memory.

### Neo4j (included)

The Neo4j driver is in the base install. You still need a Neo4j
server:

- [Neo4j Desktop](https://neo4j.com/download/) (easiest for development)
- [Neo4j Docker](https://hub.docker.com/_/neo4j) image
- Neo4j Aura (managed cloud)

### RDF / SPARQL

Install `ddigraph[rdf]`. rdflib builds the graph on your machine. A
triplestore is an RDF database for live systems. Common ones:

- Virtuoso
- GraphDB
- Stardog
- Apache Jena Fuseki

### Gremlin

Install `ddigraph[gremlin]`. It works with these databases:

- Apache TinkerPop (local testing)
- JanusGraph
- Amazon Neptune
- Azure Cosmos DB (Gremlin API)

### NetworkX

Install `ddigraph[networkx]`. It studies graphs in memory. You need no
outside service.

## Environment Configuration

ddigraph reads its settings from environment variables. Create a
`.env` file:

```bash
# Neo4j connection (for the Neo4j backend)
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=your-password

# Ingestion settings
DDIGRAPH_CHUNK_SIZE=200
DDIGRAPH_WRITER_CONCURRENCY=1
DDIGRAPH_LOG_LEVEL=INFO
```

You can also set any of these without a flag using `--tune` or a
`--config` TOML file. See the [CLI Reference](../reference/cli.md) for
the full list.

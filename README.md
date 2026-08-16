# ddigraph

[![CI](https://img.shields.io/github/actions/workflow/status/pbisson44/ddigraph/ci.yml?label=CI&logo=github)](https://github.com/pbisson44/ddigraph/actions)
[![codecov](https://codecov.io/gh/pbisson44/ddigraph/branch/main/graph/badge.svg)](https://codecov.io/gh/pbisson44/ddigraph)
[![PyPI](https://img.shields.io/pypi/v/ddigraph?logo=pypi&logoColor=white)](https://pypi.org/project/ddigraph/)
[![Downloads](https://img.shields.io/pypi/dm/ddigraph?logo=pypi&logoColor=white)](https://pypi.org/project/ddigraph/)
[![Docs](https://img.shields.io/badge/docs-EN%20%7C%20FR-blue?logo=materialformkdocs&logoColor=white)](https://pbisson44.github.io/ddigraph/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/ddigraph?logo=python&logoColor=white)](pyproject.toml)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-green?logo=neo4j)](https://neo4j.com/docs/)
[![DDI](https://img.shields.io/badge/DDI-Codebook%20%7C%20Lifecycle%20%7C%20CDI-6a4c93)](https://ddialliance.org/)
[![Code style](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/)
[![Type checking](https://img.shields.io/badge/type%20checking-mypy-1678be?logo=mypy&logoColor=white)](https://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](.pre-commit-config.yaml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/pbisson44)

A modern Python toolkit that transforms [DDI](https://ddialliance.org/) (Data Documentation
Initiative) XML metadata into knowledge graphs. Supports **DDI Codebook** and **DDI-L
FragmentInstance** formats with streaming parsing, batched writes, and full async I/O across
multiple graph backends.

[Documentation](https://pbisson44.github.io/ddigraph/) |
[Getting Started](https://pbisson44.github.io/ddigraph/getting-started/installation/) |
[PyPI](https://pypi.org/project/ddigraph/) |
[Source Code](https://github.com/pbisson44/ddigraph)

---

## Features

- **Neo4j and RDF** -- load into Neo4j, or read and write RDF with a
  documented, versioned vocabulary aligned to DISCO, SKOS and XKOS
- **File export** -- `ddigraph export` writes Turtle, JSON-LD, N-Triples,
  RDF/XML, JSON or CSV with no database involved
- **SHACL shapes** -- generated from the same schema that builds the Neo4j
  constraints, so they cannot drift
- **Preview before you load** -- `ddigraph preview` summarises a file as
  text, Mermaid, or one self-contained HTML page
- **Streaming XML processing** -- Memory-bounded `iterparse` for files of any size
- **Batched writes** -- UNWIND-based Cypher for 10-100x fewer database round trips
- **Async I/O** -- Concurrent parsing and writing with back-pressure control
- **Format auto-detection** -- identifies DDI Codebook, DDI-L and DDI-CDI input
- **Unified schema** -- Single source of truth for all node and relationship definitions
- **Adapter pattern** -- Plug in custom graph backends via `GraphWriteAdapter` protocol
- **Production-ready** -- Retry logic, observability hooks, pydantic-based configuration

## Quick Start

### Install

```bash
pip install ddigraph
```

### Load DDI metadata (CLI)

```bash
# Set Neo4j connection
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=secret

# Bootstrap schema and load data (format is auto-detected)
ddigraph bootstrap
ddigraph load survey.xml --dataset-id my-survey
```

### Load DDI metadata (Python)

```python
import ddigraph

ddigraph.bootstrap(target="bolt://localhost:7687")
result = ddigraph.load("survey.xml", target="bolt://localhost:7687")
print(result.nodes_written, "nodes,", result.relationships_written, "relationships")
```

### Export without a database

```python
import ddigraph

result = ddigraph.export("survey.xml", "survey.ttl", format="turtle")
print(result.triples, "triples")
```

## Supported Formats

| Format | Description | Use Case |
| ------ | ----------- | -------- |
| **DDI Codebook** | Traditional flat format with central Dataset node | Survey archives, data catalogs |
| **DDI-L FragmentInstance** | Lifecycle 3.x format with reusable fragments | Questionnaire design, CAPI/CAWI instruments |
| **DDI-CDI 1.0** | Cross-Domain Integration metadata | Data integration, statistical production |

### XSD Coverage

`ddigraph` ships with 100 % coverage of every concrete identifiable element
declared in the bundled XSD schemas (`schemas/`).  Coverage is enforced by the
audit script and a pytest guardrail so new schema releases surface any gaps:

| Flavor      | Scope                                                                 | Target | Covered |
| ----------- | --------------------------------------------------------------------- | -----: | ------: |
| DDI-L 3.x   | Concrete Maintainable + Versionable + Identifiable elements           |    189 |  100 %  |
| DDI-C 2.x   | Codebook elements with the `GLOBALS` attribute group (no layout tags) |     73 |  100 %  |
| DDI-CDI 1.0 | Concrete top-level entity elements (associations excluded)            |    210 |  100 %  |

Run `python scripts/xsd_coverage.py` to regenerate the audit or
`python scripts/xsd_coverage.py --json` for machine-readable output.

## Supported Backends

| Backend | Status | Install |
| ------- | ------ | ------- |
| **Neo4j** | Shipped. Read and write, all three DDI flavors | base install |
| **RDF/SPARQL** | Shipped. Read and write, SHACL shapes | `ddigraph[rdf]` |
| **JSON / CSV** | Shipped. Export only | base install |
| **Gremlin** | Example script in `demo/`, not part of the package | `ddigraph[gremlin]` |
| **NetworkX** | Example script in `demo/`, not part of the package | `ddigraph[networkx]` |
| **pandas** | Example script in `demo/`, not part of the package | `ddigraph[pandas]` |

`demo/` scripts ship in neither the wheel nor the source distribution. They
are worked examples of driving another store from the parser tier, not
supported backends. To build your own, use `ddigraph.iter_graph()`, which
yields backend-neutral nodes and relationships for any DDI flavor.

## Docker Quick Start

```bash
docker run --rm --name neo4j-demo \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5

export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=password

ddigraph bootstrap
ddigraph load your-file.xml --dataset-id demo
```

## Documentation

Full documentation is available at **[pbisson44.github.io/ddigraph](https://pbisson44.github.io/ddigraph/)** in English and French.

- [Getting Started](https://pbisson44.github.io/ddigraph/getting-started/installation/) -- Installation, quick start, 10-minute tutorial
- [User Guide](https://pbisson44.github.io/ddigraph/user-guide/architecture/) -- Architecture, DDI formats, relationships, adapters
- [Graph Backends](https://pbisson44.github.io/ddigraph/backends/neo4j/) -- Neo4j, RDF/SPARQL, Gremlin, NetworkX
- [Reference](https://pbisson44.github.io/ddigraph/reference/cli/) -- CLI commands, configuration
- [Advanced](https://pbisson44.github.io/ddigraph/advanced/tuning/) -- Performance tuning, AI readiness, standards interoperability
- [Contributing](https://pbisson44.github.io/ddigraph/project/contributing/) -- How to contribute

## Development

```bash
git clone https://github.com/pbisson44/ddigraph.git
cd ddigraph
pip install -e ".[dev,docs]"

ruff check . && ruff format .
mypy .
pytest
mkdocs serve
```

## License

MIT -- see [LICENSE](LICENSE) for details.

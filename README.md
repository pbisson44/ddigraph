# ddigraph

[![CI](https://img.shields.io/github/actions/workflow/status/pbisson44/ddigraph/ci.yml?label=CI&logo=github)](https://github.com/pbisson44/ddigraph/actions)
[![codecov](https://codecov.io/gh/pbisson44/ddigraph/branch/main/graph/badge.svg)](https://codecov.io/gh/pbisson44/ddigraph)
[![PyPI](https://img.shields.io/pypi/v/ddigraph?logo=pypi&logoColor=white)](https://pypi.org/project/ddigraph/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%E2%80%933.14-blue?logo=python)](pyproject.toml)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-green?logo=neo4j)](https://neo4j.com/docs/)
[![Code style](https://img.shields.io/badge/code%20style-ruff-000000?logo=ruff&logoColor=white)](https://docs.astral.sh/ruff/)
[![Type checking](https://img.shields.io/badge/type%20checking-mypy-1678be?logo=mypy&logoColor=white)](https://mypy-lang.org/)

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

- **Multi-backend support** -- Neo4j, RDF/SPARQL, Gremlin, NetworkX, and pandas
- **Streaming XML processing** -- Memory-bounded `iterparse` for files of any size
- **Batched writes** -- UNWIND-based Cypher for 10-100x fewer database round trips
- **Async I/O** -- Concurrent parsing and writing with back-pressure control
- **Format auto-detection** -- Automatically identifies DDI Codebook vs Lifecycle format
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
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph import DDILoader, DDIFragmentLoader, detect_ddi_format
from ddigraph.config import Settings

async def main():
    settings = Settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    path = "survey.xml"
    if detect_ddi_format(path) == "lifecycle":
        loader = DDIFragmentLoader(driver, settings=settings)
        result = await loader.load(path)
    else:
        loader = DDILoader(driver, settings=settings)
        result = await loader.load(path, dataset_id="my-survey")
    print(result)  # {'Instrument': 1, 'Sequence': 388, 'QuestionItem': 373, ...}
    await driver.close()

asyncio.run(main())
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

| Backend | Description | Use Case |
| ------- | ----------- | -------- |
| **Neo4j** | Native graph database (Bolt) | Production deployments, complex queries |
| **RDF/SPARQL** | Semantic web triplestores | Linked data, ontology integration |
| **Gremlin** | Graph traversal language | JanusGraph, Neptune, Cosmos DB |
| **NetworkX** | Python graph library | Local analysis, prototyping |
| **pandas** | DataFrame-based | Tabular analysis, Excel export |

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
# Docstring linting is currently enforced for src/ddigraph only.
pydocstyle src/ddigraph
mypy .
pytest
mkdocs serve
```

## License

MIT -- see [LICENSE](LICENSE) for details.

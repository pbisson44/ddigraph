---
hide:
  - navigation
  - toc
title: ddigraph
---

<!-- markdownlint-disable MD033 -->
<div align="center" markdown>

## **ddigraph**

### Transform DDI metadata into knowledge graphs

A Python toolkit for converting [DDI](https://ddialliance.org/) (Data Documentation Initiative) XML
metadata into queryable knowledge graphs. Read Codebook, Lifecycle, and CDI formats
as a stream, then load the results into Neo4j, RDF
triplestores, Gremlin-compatible databases, NetworkX, or pandas -- all
through a single, consistent interface.

[Get Started](getting-started/quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/pbisson44/ddigraph){ .md-button }

</div>
<!-- markdownlint-enable MD033 -->

---

## Why ddigraph?

<!-- markdownlint-disable MD033 -->
<div class="grid cards" markdown>

- **Parse once, write anywhere**

    ---

    The streaming parser tier emits typed records you can persist to
    Neo4j out of the box, or to RDF/SPARQL triplestores, Gremlin
    databases, NetworkX, or pandas through small backend-specific
    adapters. The parsing code stays the same; only the writer
    changes. See the `demo/load_*.py` scripts.

- **Streaming XML Processing**

    ---

    Memory-bounded `iterparse`-based parsing handles files of any size.
    Nodes and relationships are yielded incrementally, so RAM usage stays
    constant regardless of input volume.

- **Async I/O with Back-Pressure**

    ---

    Concurrent parsing and batched writes are coordinated through async
    queues with configurable back-pressure, keeping throughput high while
    preventing memory spikes.

- **Format Auto-Detection**

    ---

    Point ddigraph at any DDI file. It checks if the input is DDI Codebook,
    DDI Lifecycle, or DDI-CDI format. Then it picks the right parser for
    you. No manual setup is needed.

- **Unified Schema Definitions**

    ---

    Node labels, property keys, relationship types, and constraints are
    defined in a single schema module. Every backend receives the same
    canonical structure, ensuring consistency across graph targets.

- **Production-Ready**

    ---

    Built-in retry logic with exponential back-off, structured logging,
    health checks, and OpenTelemetry-compatible observability hooks make
    ddigraph suitable for automated pipelines and CI/CD workflows.

</div>
<!-- markdownlint-enable MD033 -->

---

## Installation

=== "pip"

    ```bash
    pip install ddigraph
    ```

=== "Development"

    ```bash
    pip install -e ".[dev,docs]"
    ```

!!! tip "Backend extras"
    The base install includes the Neo4j driver. For other backends, install
    the corresponding extras:

    ```bash
    pip install ddigraph[rdf]      # RDFLib + SPARQLWrapper
    pip install ddigraph[gremlin]   # Gremlin-Python
    ```

---

## Quick Example

```bash
# 1. Configure your Neo4j connection
export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
export DDIGRAPH_NEO4J_USER=neo4j
export DDIGRAPH_NEO4J_PASSWORD=secret

# 2. Create indexes and constraints
ddigraph bootstrap

# 3. Load any DDI file (format is auto-detected)
ddigraph load path/to/survey.xml --dataset-id my-survey

# 4. Verify what was loaded (use Cypher in the Neo4j Browser)
#    MATCH (n) RETURN labels(n) AS type, count(*) AS n ORDER BY n DESC
```

!!! note "Python API"
    The same workflow is available programmatically. See the
    [Quick Start guide](getting-started/quickstart.md) for a full Python example
    using `DDILoader` and `DDIFragmentLoader`.

---

## Documentation

<!-- markdownlint-disable MD033 -->
<div class="grid cards" markdown>

- **Getting Started**

    ---

    Install ddigraph, run your first load, and explore the graph in under
    ten minutes.

  - [Installation](getting-started/installation.md)
  - [Quick Start](getting-started/quickstart.md)
  - [10 Minutes to ddigraph](getting-started/ten-minutes.md)

- **User Guide**

    ---

    Understand the architecture, learn how DDI elements map to graph
    structures, and extend ddigraph with custom adapters.

  - [Architecture](user-guide/architecture.md)
  - [DDI-L FragmentInstance](user-guide/fragments.md)
  - [Relationship Model](user-guide/relationships.md)
  - [Adapter Pattern](user-guide/adapter.md)

- **Graph Backends**

    ---

    Detailed guides for each supported backend, including connection
    setup, schema bootstrapping, and query examples.

  - [Neo4j](backends/neo4j.md)
  - [RDF / SPARQL](backends/rdf.md)
  - [Gremlin](backends/gremlin.md)
  - [NetworkX](backends/networkx.md)

- **Reference**

    ---

    Complete CLI command reference and configuration option catalog.

  - [CLI Reference](reference/cli.md)
  - [Configuration](reference/configuration.md)

- **Advanced**

    ---

    Tune performance, integrate with AI/LLM pipelines, and understand how
    ddigraph fits into the broader DDI ecosystem.

  - [Performance Tuning](advanced/tuning.md)
  - [AI Readiness](advanced/ai-readiness.md)
  - [Standards Interoperability](advanced/interoperability.md)
  - [Graph vs Relational](advanced/graph-vs-relational.md)

- **Project**

    ---

    Contribute to ddigraph, review the changelog, or find answers to
    common questions.

  - [Contributing](project/contributing.md)
  - [Changelog](project/changelog.md)
  - [FAQ](project/faq.md)

</div>
<!-- markdownlint-enable MD033 -->

---

## Supported DDI Formats

| Format | Version | Root Element | Description |
| ------ | ------- | ------------ | ----------- |
| **DDI Codebook** | 2.5 / 2.6 | `<codeBook>` | Traditional flat structure with a central Dataset node linking to variables, questions, and study-level metadata. Widely used by survey archives and data catalogs. |
| **DDI Lifecycle** | 3.2 / 3.3 | `<FragmentInstance>` | Modular format built around reusable fragments. Supports questionnaire flows, CAPI/CAWI instruments, and complex study designs with fine-grained versioning. |
| **DDI-CDI** | 1.0 | `<Wrapper>` | Cross-Domain Integration model. Captures conceptual variables, represented variables, instance variables, and the relationships between them for cross-study harmonisation. |

!!! info "Format detection"
    You do not need to say which format a file uses. The `detect_ddi_format()`
    function reads the root element and namespace. It then picks the right
    parser for you.

---

## Supported Graph Backends

| Backend | Library | Best For | Protocol |
| ------- | ------- | -------- | -------- |
| **Neo4j** | `neo4j` (Bolt driver) | Production deployments, complex traversals, full-text search | Bolt |
| **RDF / SPARQL** | `rdflib`, `SPARQLWrapper` | Linked data publishing, ontology alignment, federated queries | HTTP / SPARQL 1.1 |
| **Gremlin** | `gremlinpython` | JanusGraph, Amazon Neptune, Azure Cosmos DB | WebSocket |
| **NetworkX** | `networkx` | Local analysis, prototyping, unit testing | In-process |
| **pandas** | `pandas` | Tabular analysis, CSV/Excel export, data validation | In-process |

Neo4j is wired through the `GraphWriteAdapter` protocol in
`ddigraph.schema.adapter`. The other backends listed above are not
adapter-driven; they consume the parser tier (`DDILoader`,
`DDIFragmentLoader`, `DDIFragmentParser`) and write through their own
small adapters. The `demo/load_*.py` scripts show the pattern.

---

<!-- markdownlint-disable MD033 -->
<div align="center" markdown>

**ddigraph** is released under the [MIT License](https://github.com/pbisson44/ddigraph/blob/main/LICENSE).

[GitHub](https://github.com/pbisson44/ddigraph) |
[PyPI](https://pypi.org/project/ddigraph/) |
[Issues](https://github.com/pbisson44/ddigraph/issues)

</div>
<!-- markdownlint-enable MD033 -->

# ddigraph Demo

This folder contains demo scripts and a sample DDI file for testing ddigraph with various backends.

## Setup

1. Install ddigraph:

   ```bash
   pip install -e ..
   ```

2. For Neo4j demos, start Neo4j (5.x):

   ```bash
   docker run --rm --name neo4j-demo \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     neo4j:5
   ```

3. Point ddigraph at your database, with environment variables or a
   `.env` file beside the script:

   ```bash
   export DDIGRAPH_NEO4J_URI=bolt://localhost:7687
   export DDIGRAPH_NEO4J_USER=neo4j
   export DDIGRAPH_NEO4J_PASSWORD=password
   ```

## Demo Scripts

### Neo4j (Default)

Load DDI into Neo4j graph database:

```bash
# Load included sample file
python load_ddi.py

# Load a specific file
python load_ddi.py /path/to/your/ddi-file.xml

# Audit the graph structure
python audit_graph.py

# Standalone audit (no ddigraph dependency)
python audit_graph_standalone.py \
    --uri "neo4j+s://xxx.databases.neo4j.io" \
    --user neo4j --password "secret"
```

### NetworkX, pandas and Gremlin

These ship with the package as of 0.5.1, in `ddigraph.backends`, so the
scripts that used to live here are gone. One call each:

```python
from ddigraph.backends.networkx import to_networkx
from ddigraph.backends.pandas import to_dataframes

G = to_networkx("Ireland_LabourSurvey.xml")
frames = to_dataframes("Ireland_LabourSurvey.xml")
```

See the [NetworkX](../docs/en/backends/networkx.md),
[pandas](../docs/en/backends/pandas.md) and
[Gremlin](../docs/en/backends/gremlin.md) guides.

### Preview (no database)

Before loading anything, see what is in the file. This needs no Neo4j and
no optional extra:

```bash
ddigraph preview Ireland_LabourSurvey.xml
ddigraph preview Ireland_LabourSurvey.xml --format html -o preview.html
```

Output:

- A count for every node type and every `type -[EDGE]-> type`
- `--limit N` adds example identities per type
- `--format mermaid` for a diagram, `--format html` for a self-contained page

### RDF/SPARQL (Semantic Web)

RDF is part of the package as of 0.5.0, so there is no demo script for it.
Use the command directly:

```bash
pip install "ddigraph[rdf]"

ddigraph export /path/to/ddi.xml --format turtle -o survey.ttl
ddigraph shapes -o shapes.ttl --flavor lifecycle
ddigraph load survey.ttl
```

The vocabulary, the SKOS mapping and the subject IRIs are all handled for
you. See [the RDF backend guide](../docs/en/backends/rdf.md) for what comes
out and how to query it.

## Files

| File | Description |
| ------ | ------------- |
| `load_ddi.py` | Load DDI into Neo4j (auto-detects format) |
| `audit_graph.py` | Audit Neo4j graph structure |
| `audit_graph_standalone.py` | Standalone audit (no ddigraph dependency) |
| `load_sdmx_lfs.py` | Load the SDMX companion files |
| `sdmx_from_physical_instance.py` | Derive an SDMX DSD from a DDI PhysicalInstance |
| `search_lfs_metadata.py` | Search the loaded graph from the command line |
| `Ireland_LabourSurvey.xml` | Sample DDI-L FragmentInstance (148K lines) |

The XML and TTL files here are stored in Git LFS. A plain `git clone`
without `git lfs pull` leaves them as small pointer files, which parse as
XML right up until they fail — run `git lfs pull` before the demos.

## Adapter Pattern

These demos demonstrate the adapter pattern described in the [Custom Adapters](../docs/en/user-guide/adapter.md) documentation. The same DDI parser can output to:

- **Neo4j** - production graph database, shipped in the package
- **RDF/SPARQL** - semantic web triplestores, shipped in the package
- **JSON/CSV** - file export, shipped in the package
- **NetworkX** - local graph analysis (demo script)
- **pandas** - DataFrame analysis (demo script)
- **Gremlin** - JanusGraph, Neptune, Cosmos DB (demo script)

The first three are `ddigraph load` and `ddigraph export`. The last three are
worked examples built on `iter_graph`, not shipped adapters.

To create your own adapter, implement the batch writing interface:

```python
class MyAdapter:
    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        for element_type, fragments in batch.fragments_by_type.items():
            for fragment in fragments:
                self.my_backend.store(fragment.to_dict())
        for from_id, rel_type, to_id in batch.relationships:
            self.my_backend.link(from_id, rel_type, to_id)
        return {"processed": batch.total_fragments()}
```

See the demo scripts for complete working examples.

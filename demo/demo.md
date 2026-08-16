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

### NetworkX (Local Analysis)

Load DDI into NetworkX for local graph analysis without a database:

```bash
# Requires: pip install networkx matplotlib
python load_networkx.py

# With specific file
python load_networkx.py /path/to/ddi.xml
```

Output:

- Graph statistics (nodes, edges, connectivity)
- Path analysis from entry point
- Export to GraphML format
- Optional visualization (PNG)

### pandas (DataFrame Analysis)

Load DDI into pandas DataFrames for data analysis:

```bash
# Requires: pip install pandas openpyxl
python load_pandas.py

# With specific file
python load_pandas.py /path/to/ddi.xml
```

Output:

- One DataFrame per node type (QuestionItem, CodeList, etc.)
- Relationship DataFrame
- Question text analysis
- Export to Excel workbook

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

### Gremlin (Graph Traversals)

Load DDI into Gremlin for traversal-based graph queries:

```bash
# Requires: pip install gremlinpython
python load_gremlin.py
 
# With specific file
python load_gremlin.py /path/to/ddi.xml
```

Output:

- In-memory TinkerGraph for testing
- Gremlin traversal query examples
- Path analysis and pattern matching
- Compatible with JanusGraph, Amazon Neptune, Azure Cosmos DB

### JSON/CSV Export

Also part of the package as of 0.5.0, and needing no optional extra:

```bash
ddigraph export /path/to/ddi.xml --format json -o graph.json
ddigraph export /path/to/ddi.xml --format csv -o ./my_export
```

Output:

- `graph.json` - nodes, relationships, and a summary in one document
- `nodes.csv` / `relationships.csv` - the same graph as two tables

`ddigraph export` works on Codebook, Lifecycle and CDI alike.

## Sample Output (Neo4j)

```bash
File: Ireland_LabourSurvey.xml
Format: lifecycle
Connected to: bolt://localhost:7687
Schema ready
Loading...

Results:
  Category: 1065
  CodeList: 196
  ComputationItem: 1
  IfThenElse: 357
  Instrument: 1
  QuestionConstruct: 376
  QuestionGrid: 3
  QuestionItem: 373
  Sequence: 388
  StatementItem: 2

Total parsed nodes: 2762
```

> **Note — version-aware identity.** DDI identity is agency+id+**version** (the URN). The sample contains
> two distinct `Category` fragments that share an id (`23a02ae0-…`) but differ in version — version 3 "C6"
> and version 4 "C7" — and two different code lists each reference a specific version. Fragment nodes are
> therefore keyed on a **version-aware `fragment_id` (the URN, e.g. `urn:ddi:ie.cso:23a02ae0-…:3`)**, with
> the bare DDI id preserved as `ddi_id`. Both versions are kept as separate nodes and each reference
> resolves to the correct version, so every backend agrees at **2762 nodes / Category 1065** with no
> dangling edges. (Genuine duplicates — same id *and* version — are still collapsed, with a warning.)

## Sample Output (NetworkX)

```bash
============================================================
 NETWORKX GRAPH ANALYSIS
============================================================

Basic Stats:
  Nodes: 2762
  Edges: 2904

Nodes by Label:
  Category: 1065
  Sequence: 388
  QuestionConstruct: 376
  QuestionItem: 373
  IfThenElse: 357
  CodeList: 196

Relationships by Type:
  HAS_CATEGORY: 1096
  HAS_CONSTRUCT: 767
  REFERENCES_QUESTION: 376
  THEN: 357
  USES_CODELIST: 296

Entry Point: e274cbba-78ea-4a7b-bf06-e6fef1e570e1
  Reachable nodes: 2761
  Maximum depth: 5

Connected Components: 2
```

## Sample Output (pandas)

```bash
============================================================
 PANDAS DATAFRAME ANALYSIS
============================================================

DataFrames Created:
  QuestionItem: 373 rows, 8 columns
  CodeList: 196 rows, 7 columns
  Category: 1065 rows, 6 columns
  Sequence: 388 rows, 6 columns
  _relationships: 2904 rows, 3 columns

--- QuestionItem Analysis ---
Total questions: 373

Response types:
  code       299
  numeric     42
  text        29
  datetime     3

Question text length:
  Mean: 87 chars
  Max: 412 chars
```

## Sample Output (RDF/SPARQL)

This is `ddigraph export --format turtle` on
`tests/fixtures/fragment_instance.xml`, a six-node file kept small enough to
read. The numbers scale, the shape does not change.

```text
Nodes: 6  Relationships: 5
Triples: 56
```

Every node carries two types — the published class for interoperability and
the project class for identity:

```text
disco:Instrument            1     ddigraph:Instrument         1
disco:Question              1     ddigraph:QuestionItem       1
skos:Concept                1     ddigraph:Category           1
                                  ddigraph:Sequence           1
                                  ddigraph:QuestionConstruct  1
```

`Category` becomes a `skos:Concept`, `QuestionItem` a `disco:Question`.
Predicates are published terms where one exists and `lowerCamelCase`
otherwise — never the Neo4j relationship name:

```text
rdf:type              10
owl:versionInfo        6
dcterms:publisher      6
ddigraph:ddiId         6
ddigraph:fragmentId    6
dcterms:identifier     5
rdfs:label             3
ddigraph:hasConstruct  2
```

No Neo4j relationship name reaches the output, and the DDI URN survives
intact as the subject. Those two properties are what make the file worth
sending to another system.

## Sample Output (Gremlin)

```bash
============================================================
 GREMLIN GRAPH ANALYSIS
============================================================
 
Basic Stats:
  Vertices: 2762
  Edges: 2904
 
Vertices by Label:
  Category: 1065
  Sequence: 388
  QuestionItem: 373
  IfThenElse: 357
  CodeList: 196
 
Edges by Type:
  HAS_CATEGORY: 1096
  HAS_CONSTRUCT: 767
  REFERENCES_QUESTION: 376
  THEN: 357
 
============================================================
 GREMLIN TRAVERSAL EXAMPLES
============================================================
 
--- Query 4: Reachability from Instrument ---
  1 hop from Instrument: 1 vertices
  2 hops from Instrument: 388 vertices
  3 hops from Instrument: 765 vertices
```

## Files

| File | Description |
| ------ | ------------- |
| `load_ddi.py` | Load DDI into Neo4j (auto-detects format) |
| `audit_graph.py` | Audit Neo4j graph structure |
| `audit_graph_standalone.py` | Standalone audit (no ddigraph dependency) |
| `load_networkx.py` | Load DDI into NetworkX for local analysis |
| `load_pandas.py` | Load DDI into pandas DataFrames |
| `load_gremlin.py` | Load DDI into Gremlin for traversal queries |
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

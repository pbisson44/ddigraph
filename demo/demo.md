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

3. Create a `.env` file with your credentials:

   ```bash
   cp .env.example .env
   # Edit .env with your Neo4j password
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

### RDF/SPARQL (Semantic Web)

Load DDI into RDF for semantic web applications and SPARQL queries:

```bash
# Requires: pip install rdflib
python load_rdf.py
 
# With specific file
python load_rdf.py /path/to/ddi.xml
```

Output:

- RDF graph with DDI ontology mapping
- Export to Turtle, N-Triples, RDF/XML, JSON-LD
- SPARQL query examples
- Compatible with triplestores (Virtuoso, GraphDB, Stardog)

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

Export DDI to JSON and CSV files for use in other tools:

```bash
python export_files.py

# With output directory
python export_files.py /path/to/ddi.xml --output-dir ./my_export
```

Output:

- `nodes.json` / `nodes.csv` - All nodes with properties
- `relationships.json` / `relationships.csv` - All relationships
- `summary.json` - Graph statistics

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
  IfThenElse: 357
  Instrument: 1
  QuestionConstruct: 376
  QuestionItem: 373
  Sequence: 388
  StatementItem: 6

Total nodes in database: 2762
```

## Sample Output (NetworkX)

```bash
============================================================
 NETWORKX GRAPH ANALYSIS
============================================================

Basic Stats:
  Nodes: 2762
  Edges: 2892

Nodes by Label:
  Category: 1064
  Sequence: 388
  QuestionConstruct: 376
  QuestionItem: 373
  IfThenElse: 357
  CodeList: 196

Relationships by Type:
  HAS_CATEGORY: 1096
  HAS_CONSTRUCT: 767
  ASKS_QUESTION: 376
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
  Category: 1064 rows, 6 columns
  Sequence: 388 rows, 6 columns
  _relationships: 2892 rows, 3 columns

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

```bash
============================================================
 RDF GRAPH ANALYSIS
============================================================
 
Basic Stats:
  Total triples: 8652
  Unique resources: 2762
 
Resources by Type:
  ddi:Category: 1064
  ddi:Sequence: 388
  ddi:QuestionItem: 373
  ddi:IfThenElse: 357
  ddi:CodeList: 196
 
Top Relationships:
  ddi:HAS_CATEGORY: 1096
  ddi:HAS_CONSTRUCT: 767
  ddi:ASKS_QUESTION: 376
  ddi:USES_CODELIST: 296
 
============================================================
 SPARQL QUERY EXAMPLES
============================================================
 
--- Query 1: Find Instruments ---
Found 1 instrument(s)
 
--- Query 3: Questions with CodeLists ---
Found 296 question-codelist pairs
```

## Sample Output (Gremlin)

```bash
============================================================
 GREMLIN GRAPH ANALYSIS
============================================================
 
Basic Stats:
  Vertices: 2762
  Edges: 2892
 
Vertices by Label:
  Category: 1064
  Sequence: 388
  QuestionItem: 373
  IfThenElse: 357
  CodeList: 196
 
Edges by Type:
  HAS_CATEGORY: 1096
  HAS_CONSTRUCT: 767
  ASKS_QUESTION: 376
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
| `load_rdf.py` | Load DDI into RDF for SPARQL queries |
| `load_gremlin.py` | Load DDI into Gremlin for traversal queries |
| `export_files.py` | Export DDI to JSON/CSV files |
| `Ireland_LabourSurvey.xml` | Sample DDI-L FragmentInstance (148K lines) |
| `.env.example` | Example environment configuration |

## Adapter Pattern

These demos demonstrate the adapter pattern described in the [Adapter Architecture](../docs/adapter.md) documentation. The same DDI parser can output to:

- **Neo4j** - Production graph database
- **NetworkX** - Local graph analysis
- **pandas** - DataFrame analysis
 **RDF/SPARQL** - Semantic web triplestores
- **Gremlin** - JanusGraph, Neptune, Cosmos DB
- **JSON/CSV** - File export

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

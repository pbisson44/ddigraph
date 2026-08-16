# Graph vs Relational Databases for DDI Metadata

ddigraph uses a graph database (Neo4j), not a relational one. This page
explains why. It covers the benefits for DDI metadata. It also lists points
to weigh if your team is evaluating this approach.

## The Challenge: DDI's Inherent Complexity

DDI (Data Documentation Initiative) metadata describes survey instruments,
questionnaires, and variables. It also describes how they relate. The result
is a highly connected structure:

- Questions reference code lists and categories
- Variables link to questions, concepts, and universes
- Control flow constructs (sequences, conditionals, loops) form execution paths
- Instruments contain nested hierarchies of constructs

### A Typical DDI Query

Consider answering: *"Which questions use a particular code list, and what variables are derived from those questions?"*

This requires traversing:

```text
CodeList → QuestionItem → QuestionConstruct → Variable
```

## Relational Database Approach

### Relational Schema Design

In a relational database, you might model this with normalized tables:

```sql
CREATE TABLE code_lists (
    id VARCHAR PRIMARY KEY,
    agency VARCHAR,
    version VARCHAR,
    label TEXT
);

CREATE TABLE question_items (
    id VARCHAR PRIMARY KEY,
    agency VARCHAR,
    version VARCHAR,
    label TEXT,
    question_text TEXT,
    code_list_id VARCHAR REFERENCES code_lists(id)
);

CREATE TABLE question_constructs (
    id VARCHAR PRIMARY KEY,
    question_item_id VARCHAR REFERENCES question_items(id)
);

CREATE TABLE variables (
    id VARCHAR PRIMARY KEY,
    label TEXT,
    question_construct_id VARCHAR REFERENCES question_constructs(id)
);
```

### The Query Problem

Finding all variables using a specific code list requires multiple JOINs:

```sql
SELECT v.*
FROM variables v
JOIN question_constructs qc ON v.question_construct_id = qc.id
JOIN question_items qi ON qc.question_item_id = qi.id
WHERE qi.code_list_id = 'cl-age-groups';
```

This seems manageable, but DDI complexity grows quickly:

1. **Variable-depth paths**: Survey flow can nest arbitrarily deep (Sequence → Sequence → IfThenElse → Sequence → QuestionConstruct)
2. **Multiple relationship types**: A single entity may have many different relationships
3. **Polymorphic references**: ControlConstructReference can point to Sequence, QuestionConstruct, IfThenElse, Loop, etc.
4. **Cross-cutting concerns**: Finding all constructs affected by a code list change requires traversing multiple paths

### Relational Limitations

| Challenge | Relational Impact |
| ----------- | ------------------- |
| Variable-depth traversal | Requires recursive CTEs or multiple queries |
| Path finding | Complex self-joins, hard to optimize |
| Schema evolution | Adding relationship types requires ALTER TABLE |
| Polymorphic references | Requires type columns or multiple foreign keys |
| Impact analysis | Expensive multi-table scans |

#### Example: Variable-Depth Query in SQL

Finding all constructs reachable from an instrument:

```sql
WITH RECURSIVE reachable AS (
    -- Base case: start from instrument
    SELECT child_id, child_type, 1 as depth
    FROM control_construct_refs
    WHERE parent_id = 'instrument-1'
    
    UNION ALL
    
    -- Recursive case: follow references
    SELECT ccr.child_id, ccr.child_type, r.depth + 1
    FROM control_construct_refs ccr
    JOIN reachable r ON ccr.parent_id = r.child_id
    WHERE r.depth < 20  -- Safety limit
)
SELECT * FROM reachable;
```

This query:

- Becomes slow as depth increases
- Requires careful index tuning
- May hit database recursion limits
- Doesn't easily filter by relationship type

## Graph Database Approach

### Graph Schema Design

In Neo4j, the same structure is expressed as nodes and relationships:

```cypher
// Nodes
(:CodeList {fragment_id: "cl-1", label: "Age Groups"})
(:QuestionItem {fragment_id: "q-1", question_text: "What is your age?"})
(:QuestionConstruct {fragment_id: "qc-1"})
(:Variable {fragment_id: "v-1", label: "Age"})

// Relationships
(q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
(qc:QuestionConstruct)-[:ASKS_QUESTION]->(q:QuestionItem)
(v:Variable)-[:DERIVED_FROM]->(qc:QuestionConstruct)
```

### The Same Query, Simplified

Finding all variables using a specific code list:

```cypher
MATCH (cl:CodeList {fragment_id: 'cl-age-groups'})
      <-[:USES_CODELIST]-(q:QuestionItem)
      <-[:ASKS_QUESTION]-(qc:QuestionConstruct)
      <-[:DERIVED_FROM]-(v:Variable)
RETURN v
```

### Variable-Depth Traversal

Finding all constructs reachable from an instrument:

```cypher
MATCH (inst:Instrument {fragment_id: 'instrument-1'})
      -[:HAS_CONSTRUCT*]->(construct)
RETURN construct
```

The `*` operator handles arbitrary depth naturally, without recursion limits or complex CTEs.

## Benefits of Graph Databases for DDI

### 1. Natural Data Model

DDI metadata *is* a graph. A fragment is a self-contained DDI object. A
reference is a pointer from one object to another. The XML defines nodes
(fragments) and edges (references) directly:

```xml
<QuestionConstruct>
    <QuestionReference>           <!-- This IS an edge -->
        <ID>question-1</ID>
    </QuestionReference>
</QuestionConstruct>
```

A graph database stores this shape as is. A relational database must encode
it in an indirect way.

### 2. Query Performance for Traversals

| Operation | Relational | Graph |
| ----------- | ------------ | ------- |
| Single JOIN | Fast | Fast |
| 3-4 JOINs | Moderate | Fast |
| Variable-depth traversal | Slow/Complex | Fast |
| Path finding | Very slow | Optimized |
| Pattern matching | Manual coding | Native support |

Graph databases use index-free adjacency. Each node points straight to its
neighbors. So traversal time scales with the result size, not the total
data size.

### 3. Schema Flexibility

Adding a new relationship type in a relational database:

```sql
ALTER TABLE question_items 
ADD COLUMN instruction_id VARCHAR REFERENCES instructions(id);
-- Plus migration scripts, ORM updates, etc.
```

Adding a new relationship type in Neo4j:

```cypher
MATCH (q:QuestionItem {fragment_id: 'q-1'})
MATCH (i:Instruction {fragment_id: 'inst-1'})
CREATE (q)-[:HAS_INSTRUCTION]->(i)
```

No schema migration required. New relationship types can coexist with existing data.

### 4. Expressive Query Language

Cypher expresses graph patterns directly:

```cypher
// Find questions with conditional branching that use a specific code list
MATCH (cl:CodeList {fragment_id: 'cl-yes-no'})
      <-[:USES_CODELIST]-(q:QuestionItem)
      <-[:ASKS_QUESTION]-(qc:QuestionConstruct)
      <-[:HAS_CONSTRUCT]-(seq:Sequence)
      <-[:THEN|ELSE]-(ite:IfThenElse)
RETURN q.fragment_id, q.question_text, ite.condition
```

### 5. Impact Analysis

Understanding what's affected by a change:

```cypher
// Find everything that depends on a code list
MATCH (cl:CodeList {fragment_id: 'cl-occupation'})
MATCH path = (cl)<-[*1..5]-(dependent)
RETURN DISTINCT labels(dependent)[0] as type, 
       dependent.fragment_id as id,
       length(path) as distance
ORDER BY distance
```

## Potential Drawbacks and Considerations

### 1. Learning Curve

**Challenge**: Teams familiar with SQL must learn Cypher and graph thinking.

**Mitigation**:

- Cypher syntax is intuitive for pattern matching
- ddigraph provides pre-built queries in the audit scripts
- Documentation includes common query patterns

### 2. Operational Complexity

**Challenge**: Running Neo4j requires additional infrastructure.

**Mitigation**:

- Neo4j Aura provides managed cloud hosting
- Docker makes local deployment simple
- Neo4j Community Edition is free for single-instance use

### 3. Tooling Ecosystem

**Challenge**: Fewer BI tools natively support graph databases.

**Mitigation**:

- Neo4j has JDBC/ODBC connectors for BI tools
- ddigraph's adapter pattern allows export to pandas, JSON, CSV
- Graph results can be flattened for traditional reporting

### 4. Transaction Semantics

**Challenge**: Graph databases optimize for reads; write-heavy workloads may differ.

**Mitigation**:

- DDI metadata is read-heavy (load once, query many times)
- ddigraph uses batched writes with UNWIND for efficient ingestion
- Neo4j supports ACID transactions

### 5. Aggregate Queries

**Challenge**: Some aggregate operations are more natural in SQL.

**Example**: Counting variables per dataset is simpler in SQL:

```sql
SELECT dataset_id, COUNT(*) FROM variables GROUP BY dataset_id;
```

**Cypher equivalent**:

```cypher
MATCH (d:Dataset)<-[:IN_DATASET]-(v:Variable)
RETURN d.id, count(v)
```

Both work, but SQL's GROUP BY may feel more familiar.

### 6. Data Volume Considerations

**Challenge**: Very large datasets (millions of nodes) require tuning.

**Mitigation**:

- ddigraph creates indexes on key fields
- Batch sizes are configurable
- Neo4j Enterprise offers clustering for scale

## When to Use Each Approach

### Graph Database (Neo4j) is Better When

- Queries frequently traverse relationships
- Path analysis is important (reachability, impact)
- Schema evolves with new relationship types
- You need to visualize metadata structure
- Integration with other graph data (SDMX, ontologies)

### Relational Database May Be Better When

- Queries are primarily aggregations and counts
- Team has no graph database experience and limited learning time
- Existing infrastructure is purely relational
- Data volume is small and queries are simple
- Compliance requires specific database technologies

## Hybrid Approaches

You don't have to choose exclusively. Common patterns include:

### 1. Graph for Navigation, Relational for Reporting

Use Neo4j for structural queries and path analysis, but sync summaries to a relational data warehouse for BI dashboards.

### 2. Graph as Metadata Layer

Keep survey response data in a relational database. Use Neo4j for the
metadata that describes that data. Link the two by dataset and variable IDs.

### 3. Export for Analysis

Use ddigraph's adapter pattern to export graph data to pandas DataFrames or CSV files for teams more comfortable with those tools:

```bash
ddigraph export survey.xml --format json -o survey.json
ddigraph export survey.xml --format csv -o out-dir/   # nodes.csv + relationships.csv
python demo/load_pandas.py                            # DataFrames (demo script)
```

## Query Comparison Reference

| Task | SQL | Cypher |
| ------ | ----- | -------- |
| Find by ID | `SELECT * FROM questions WHERE id = 'q1'` | `MATCH (q:QuestionItem {fragment_id: 'q1'}) RETURN q` |
| Simple JOIN | `SELECT * FROM questions q JOIN code_lists cl ON q.code_list_id = cl.id` | `MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl) RETURN q, cl` |
| Variable depth | Recursive CTE (complex) | `MATCH path = (a)-[*1..5]->(b) RETURN path` |
| Shortest path | Not native | `MATCH p = shortestPath((a)-[*]-(b)) RETURN p` |
| All paths | Very complex | `MATCH p = allShortestPaths((a)-[*]-(b)) RETURN p` |
| Pattern match | Multiple JOINs + conditions | `MATCH (a)-[:R1]->(b)-[:R2]->(c) WHERE ...` |

## Conclusion

For DDI metadata, graph databases win on three fronts. Queries are easier to
write. Traversals run faster. The schema is more flexible. The trade-offs are
a learning curve and more setup. Both stay manageable, especially given:

1. DDI's inherently graph-like structure
2. The importance of relationship traversal in metadata use cases
3. Neo4j's mature tooling and cloud options
4. ddigraph's adapter pattern for integration flexibility

Teams should evaluate based on their specific query patterns, existing infrastructure, and willingness to invest in graph database skills.

## Further Reading

- [Neo4j Graph Database Concepts](https://neo4j.com/docs/getting-started/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/)
- [DDI Lifecycle Specification](https://ddialliance.org/Specification/DDI-Lifecycle/)
- [ddigraph Architecture](../user-guide/architecture.md)
- [Standards Interoperability](interoperability.md)

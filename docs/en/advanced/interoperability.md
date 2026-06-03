# Standards Interoperability with Graph Databases

!!! note "Who is this page for?"
    This page is for teams that use **both DDI metadata and SDMX data structures** and want
    to link them together in the same graph. If you're not working with SDMX, you can skip
    this page.

    **SDMX** (Statistical Data and Metadata eXchange) is an international standard for sharing
    statistics between organizations like central banks, government agencies, and Eurostat.
    It describes *data structures* — what columns exist in a dataset, what values are allowed,
    and how they relate to each other.

    **DDI** describes survey *metadata* — what questions were asked, what variables were
    collected, and what the answers mean. These two standards describe the same data from
    different angles, and a graph makes it easy to link them.

---

## Why Graphs for Interoperability?

Traditional approaches to standards mapping rely on transformation scripts, XSLT stylesheets, or rigid relational schemas. These approaches struggle with:

- **Schema evolution**: Adding new mappings requires code changes
- **Many-to-many relationships**: A single DDI concept may map to multiple SDMX components
- **Contextual mappings**: The same element may map differently depending on context
- **Traceability**: Difficult to audit why a mapping was made

Graph databases address these challenges through their flexible schema and explicit relationship modeling.

### Graph Advantages

| Challenge | Relational Approach | Graph Approach |
| ----------- | -------------------- | -------------------- |
| Schema changes | ALTER TABLE, migrations | Add new node/relationship types dynamically |
| Many-to-many | Junction tables | Direct relationships with properties |
| Context | Complex JOINs | Traverse specific paths |
| Traceability | Audit tables | Relationship properties capture provenance |

## DDI-SDMX Integration Pattern

The main task is linking DDI variables to SDMX data structure components.

In SDMX, every variable in a dataset plays one of two roles:

- **Dimension** — a column that *identifies* a data point (e.g., country, year, age group).
  Dimensions tell you *what* a value refers to.
- **Measure** — the actual number being reported (e.g., unemployment rate, population count).

A DDI variable maps to whichever role it plays in the SDMX structure.

Each variable also has a **value domain** — the set of allowed values (e.g., a list of country
codes, or a numeric range). In SDMX this is represented by a **codelist** (for categorical
values) or a **data type** (for numbers/text).

### ID Matching

The simplest way to link DDI and SDMX is **ID matching** — when a DDI variable and an SDMX
component share the same identifier, we can link them automatically. This works for most
structured datasets where IDs were assigned consistently.

```uml
DDI Variable ──────────────────────> SDMX Component
     │                                      │
     ├── ID attribute ◄──── matches ────► ID attribute
     ├── User ID      ◄──── matches ────► User ID
     │                                      │
     └── Value Domain ─────────────────> Dimension Codelist
                       ─────────────────> Measure Data Type
```

In Neo4j, this link becomes an explicit relationship:

```cypher
// Variable as Dimension
(v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
(v)-[:HAS_VALUE_DOMAIN]->(vd:ValueDomain)-[:ALIGNED_WITH]->(cl:Codelist)

// Variable as Measure  
(v:Variable)-[:MAPS_TO_MEASURE]->(m:Measure)
(v)-[:HAS_VALUE_DOMAIN]->(vd:ValueDomain)-[:ALIGNED_WITH]->(dt:DataType)
```

### Graph Schema for Integration

```cypher
// DDI nodes (from ddigraph)
(:Variable {id, name, label, user_id})
(:ValueDomain {id, type})
(:CodeList {id, name})
(:Category {id, label, code_value})

// SDMX nodes
(:DataStructureDefinition {id, agency, version})
(:Dimension {id, position, concept_identity})
(:Measure {id, concept_identity})
(:Codelist {id, agency, version})  // SDMX codelist
(:Code {id, value, name})

// Integration relationships
(:Variable)-[:MAPS_TO_DIMENSION {match_type, confidence}]->(:Dimension)
(:Variable)-[:MAPS_TO_MEASURE {match_type, confidence}]->(:Measure)
(:CodeList)-[:ALIGNED_WITH {mapping_date, method}]->(:Codelist)
(:Category)-[:CORRESPONDS_TO]->(:Code)
```

### Creating Mappings

Run these Cypher queries to create the links. The first query matches by `user_id` (the
most reliable match); the second falls back to matching by the raw `id` field:

```cypher
// Match DDI variables to SDMX dimensions by user_id
MATCH (v:Variable)
WHERE v.user_id IS NOT NULL
MATCH (d:Dimension)
WHERE d.id = v.user_id OR d.concept_identity = v.user_id
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'user_id',
    m.matched_on = datetime(),
    m.confidence = 1.0
RETURN v.name, d.id, m.match_type
```

```cypher
// Match by ID attribute
MATCH (v:Variable)
MATCH (d:Dimension)
WHERE d.id = v.id
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'id',
    m.matched_on = datetime(),
    m.confidence = 0.9
RETURN v.name, d.id, m.match_type
```

### Aligning Value Domains

Once variables are mapped to dimensions, their value domains should align with SDMX codelists:

```cypher
// Find DDI CodeLists that should align with SDMX Codelists
MATCH (v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
MATCH (v)-[:HAS_VALUE_DOMAIN]->(:ValueDomain)-[:USES_CODELIST]->(ddi_cl:CodeList)
MATCH (d)-[:HAS_LOCAL_REPRESENTATION]->(sdmx_cl:Codelist)
MERGE (ddi_cl)-[a:ALIGNED_WITH]->(sdmx_cl)
SET a.alignment_date = datetime()
RETURN ddi_cl.name, sdmx_cl.id
```

```cypher
// Map individual categories to codes
MATCH (ddi_cl:CodeList)-[:ALIGNED_WITH]->(sdmx_cl:Codelist)
MATCH (ddi_cl)-[:HAS_CATEGORY]->(cat:Category)
MATCH (sdmx_cl)-[:HAS_CODE]->(code:Code)
WHERE cat.code_value = code.value
MERGE (cat)-[:CORRESPONDS_TO]->(code)
RETURN cat.label, code.name
```

## Querying Integrated Data

### Find All Mapped Variables

```cypher
MATCH (v:Variable)-[m:MAPS_TO_DIMENSION|MAPS_TO_MEASURE]->(component)
RETURN v.name AS variable,
       type(m) AS mapping_type,
       labels(component)[0] AS component_type,
       component.id AS component_id,
       m.confidence AS confidence
ORDER BY m.confidence DESC
```

### Trace Full Lineage

```cypher
// From DDI question to SDMX dimension
MATCH path = (q:QuestionItem)<-[:ASKS_QUESTION]-(:QuestionConstruct)
             <-[:HAS_CONSTRUCT*]-(seq:Sequence),
      (v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
WHERE v.question_id = q.fragment_id
RETURN q.name AS question,
       v.name AS variable,
       d.id AS sdmx_dimension,
       length(path) AS depth
```

### Find Unmapped Variables

```cypher
MATCH (v:Variable)
WHERE NOT (v)-[:MAPS_TO_DIMENSION|MAPS_TO_MEASURE]->()
RETURN v.id, v.name, v.user_id
ORDER BY v.name
```

### Codelist Alignment Report

```cypher
MATCH (ddi_cl:CodeList)-[:ALIGNED_WITH]->(sdmx_cl:Codelist)
OPTIONAL MATCH (ddi_cl)-[:HAS_CATEGORY]->(cat:Category)
OPTIONAL MATCH (cat)-[:CORRESPONDS_TO]->(code:Code)
WITH ddi_cl, sdmx_cl,
     count(DISTINCT cat) AS ddi_categories,
     count(DISTINCT code) AS mapped_codes
RETURN ddi_cl.name AS ddi_codelist,
       sdmx_cl.id AS sdmx_codelist,
       ddi_categories,
       mapped_codes,
       round(100.0 * mapped_codes / ddi_categories) AS pct_mapped
```

## Benefits of the Graph Approach

### 1. Flexible Mapping Cardinality

A single DDI variable can map to multiple SDMX components (or vice versa) without schema changes:

```cypher
// Variable maps to both dimension and attribute
(v:Variable)-[:MAPS_TO_DIMENSION]->(d:Dimension)
(v:Variable)-[:MAPS_TO_ATTRIBUTE]->(a:Attribute)
```

### 2. Rich Mapping Metadata

Relationships carry properties that document the mapping:

```cypher
[:MAPS_TO_DIMENSION {
  match_type: 'user_id',      // How the match was made
  confidence: 0.95,           // Confidence score
  matched_on: datetime(),     // When
  matched_by: 'auto',         // Who/what
  notes: 'Verified by SME'    // Documentation
}]
```

### 3. Incremental Enhancement

Add new mapping types without changing existing data:

```cypher
// Later: add semantic similarity mappings
MATCH (v:Variable), (d:Dimension)
WHERE gds.similarity.cosine(v.embedding, d.embedding) > 0.8
MERGE (v)-[m:MAPS_TO_DIMENSION]->(d)
SET m.match_type = 'semantic',
    m.confidence = gds.similarity.cosine(v.embedding, d.embedding)
```

### 4. Bidirectional Navigation

Query from either standard's perspective:

```cypher
// DDI-first: What SDMX components does this variable map to?
MATCH (v:Variable {name: 'AGE'})-[:MAPS_TO_DIMENSION|MAPS_TO_MEASURE]->(c)
RETURN c

// SDMX-first: What DDI variables feed this dimension?
MATCH (d:Dimension {id: 'AGE'})<-[:MAPS_TO_DIMENSION]-(v:Variable)
RETURN v
```

### 5. Impact Analysis

Understand downstream effects of changes:

```cypher
// If we change this CodeList, what SDMX structures are affected?
MATCH (cl:CodeList {id: 'CL_SEX'})-[:ALIGNED_WITH]->(sdmx_cl:Codelist)
      <-[:HAS_LOCAL_REPRESENTATION]-(d:Dimension)
      <-[:HAS_DIMENSION]-(dsd:DataStructureDefinition)
RETURN dsd.id AS affected_structure, d.id AS via_dimension
```

## Implementation with ddigraph

### Step 1: Load DDI Data

```bash
ddigraph load survey.xml --format lifecycle
```

### Step 2: Load SDMX Structure

Create SDMX nodes (example using Cypher):

```cypher
// Load DSD
CREATE (dsd:DataStructureDefinition {
  id: 'DSD_LFS',
  agency: 'EUROSTAT',
  version: '1.0'
})

// Load Dimensions
CREATE (d:Dimension {id: 'FREQ', position: 1, concept_identity: 'FREQ'})
CREATE (d:Dimension {id: 'GEO', position: 2, concept_identity: 'GEO'})
// ... etc
```

### Step 3: Execute Mapping Queries

Run the handshake queries to create integration relationships.

### Step 4: Validate and Report

```cypher
// Summary statistics
MATCH (v:Variable)
OPTIONAL MATCH (v)-[m:MAPS_TO_DIMENSION]->(d)
OPTIONAL MATCH (v)-[m2:MAPS_TO_MEASURE]->(measure)
RETURN count(v) AS total_variables,
       count(d) AS mapped_to_dimension,
       count(measure) AS mapped_to_measure,
       count(v) - count(d) - count(measure) AS unmapped
```

## Conclusion

Graph databases transform standards interoperability from a brittle, code-heavy process into a flexible, queryable data model. The explicit representation of mappings as relationships enables:

- Self-documenting integration logic
- Easy extension to new mapping types
- Powerful lineage and impact queries
- Incremental refinement of mappings over time

For DDI-SDMX integration specifically, the graph model naturally represents the "handshake" between variable IDs and component IDs, while preserving the full context needed to understand and maintain the mappings.

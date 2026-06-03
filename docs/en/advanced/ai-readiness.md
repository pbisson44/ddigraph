# AI Readiness: DDI-L in Neo4j

DDI-L (Data Documentation Initiative Lifecycle) metadata starts as a static XML archive.
Load it into Neo4j and it becomes a knowledge graph you can query. That shift unlocks
strong AI and machine learning use cases.

## Why Graph Structure Matters for AI

Traditional DDI-L files are deeply nested XML documents. They are thorough, but the format
is hard for AI systems to use:

| XML Format | Graph Format |
| ------------ | -------------- |
| Sequential parsing required | Direct relationship traversal |
| Implicit connections via IDs | Explicit typed relationships |
| Difficult to query patterns | Native pattern matching |
| Context buried in hierarchy | Context visible in structure |

Survey instruments already have a graph shape. Load DDI-L into Neo4j and that shape
becomes explicit. You can then walk it directly.

## Key AI-Ready Capabilities

### 1. Retrieval-Augmented Generation (RAG)

Neo4j lets you run meaning-based search over survey metadata for RAG pipelines.
RAG means the model fetches real data first, then writes its answer from it:

```cypher
// Find questions related to a concept
MATCH (q:QuestionItem)-[:USES_CODELIST]->(cl:CodeList)
WHERE q.question_text CONTAINS 'employment'
RETURN q.name, q.question_text, cl.name
```

This lets LLMs base answers on the real survey structure. They no longer have to guess at
question text or response options.

### 2. Context-Aware Question Answering

A flat file loses survey flow context. The graph keeps it:

```cypher
// Get full context for a question: what comes before, after, and why
MATCH path = (prev)-[:HAS_CONSTRUCT]->(seq:Sequence)-[:HAS_CONSTRUCT]->(qc:QuestionConstruct)
WHERE qc.fragment_id = $question_id
MATCH (qc)-[:ASKS_QUESTION]->(q:QuestionItem)
OPTIONAL MATCH (q)-[:USES_CODELIST]->(cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN path, q, collect(cat.category_label) AS response_options
```

An AI assistant can now do more than say what a question asks. It can also explain where the
question sits in the flow and what answers are allowed.

### 3. Survey Instrument Understanding

LLMs can reason about survey logic by running graph queries:

```cypher
// Analyze conditional branching
MATCH (ite:IfThenElse)-[:THEN]->(then_seq:Sequence)
MATCH (ite)-[:ELSE]->(else_seq:Sequence)
RETURN ite.condition,
       size((then_seq)-[:HAS_CONSTRUCT]->()) AS then_path_length,
       size((else_seq)-[:HAS_CONSTRUCT]->()) AS else_path_length
```

This lets AI follow skip patterns, filter logic, and how respondents are routed.

### 4. Knowledge Graph Embeddings

Graph structure helps you build embeddings for:

- **Question similarity**: Find questions with close meaning across surveys
- **Instrument comparison**: Spot structural differences between survey versions
- **Concept clustering**: Group questions by the concepts behind them

```python
# Example: Generate embeddings from graph structure
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

with driver.session() as session:
    questions = session.run("""
        MATCH (q:QuestionItem)
        RETURN q.fragment_id AS id, q.question_text AS text
    """)
    for q in questions:
        embedding = model.encode(q["text"])
        session.run("""
            MATCH (q:QuestionItem {fragment_id: $id})
            SET q.embedding = $embedding
        """, id=q["id"], embedding=embedding.tolist())
```

### 5. Agentic Workflows

AI agents can walk the survey graph to do hard tasks:

- **Survey documentation**: Write plain descriptions of instrument flow
- **Quality assurance**: Find orphaned questions or branches you cannot reach
- **Translation assistance**: Find every text element that needs localization
- **Harmonization**: Map questions across surveys to shared concepts

## Graph-Native AI Patterns

### Vector + Graph Search

Mix meaning-based similarity with structural limits:

```cypher
// Find similar questions within the same survey section
MATCH (target:QuestionItem {fragment_id: $id})
MATCH (target)<-[:ASKS_QUESTION]-(qc:QuestionConstruct)<-[:HAS_CONSTRUCT]-(seq:Sequence)
MATCH (seq)-[:HAS_CONSTRUCT]->(other_qc:QuestionConstruct)-[:ASKS_QUESTION]->(similar:QuestionItem)
WHERE similar <> target
RETURN similar.name, similar.question_text,
       gds.similarity.cosine(target.embedding, similar.embedding) AS similarity
ORDER BY similarity DESC
LIMIT 5
```

### Graph Context Windows

Pull out subgraphs as context for LLM prompts:

```cypher
// Get 2-hop neighborhood for context
MATCH (q:QuestionItem {fragment_id: $id})
MATCH path = (q)-[*1..2]-(related)
RETURN path
```

You can serialize this subgraph and add it to prompts. It gives LLMs a sense of structure
that flat document retrieval cannot.

### Reasoning Chains

Graph paths support step-by-step reasoning:

```cypher
// Trace how a respondent reaches a specific question
MATCH path = (entry:EntryPoint)-[:HAS_CONSTRUCT*]->(qc:QuestionConstruct)
WHERE (qc)-[:ASKS_QUESTION]->(:QuestionItem {fragment_id: $target})
RETURN [node IN nodes(path) | labels(node)[0]] AS node_types,
       length(path) AS steps
```

## Practical Applications

### Survey Chatbots

Build chat interfaces that know the survey structure:

```bash
User: "What questions come after the employment section?"
Bot: [Queries graph for sequences following employment-related constructs]
     "After the employment questions, respondents answer 5 questions about
      job satisfaction, then branch based on employment status..."
```

### Automated Documentation

Generate documentation from graph structure:

```python
def describe_instrument(instrument_id: str) -> str:
    """Generate natural language description of survey instrument."""
    with driver.session() as session:
        structure = session.run("""
            MATCH (i:Instrument {fragment_id: $id})-[:HAS_CONSTRUCT]->(seq:Sequence)
            MATCH (seq)-[:HAS_CONSTRUCT]->(c)
            RETURN seq.name AS section, labels(c)[0] AS type, count(*) AS count
            ORDER BY section
        """, id=instrument_id)
        # Feed to LLM for natural language generation
        return llm.generate(structure.data())
```

### Quality Validation

AI-powered validation of survey instruments:

```cypher
// Find questions without response options
MATCH (q:QuestionItem)
WHERE NOT (q)-[:USES_CODELIST]->()
RETURN q.name, q.question_text AS potentially_missing_codelist

// Find unreachable constructs
MATCH (c)
WHERE c:Sequence OR c:QuestionConstruct
AND NOT ()-[:HAS_CONSTRUCT|THEN|ELSE]->(c)
AND NOT c:EntryPoint
RETURN labels(c)[0] AS type, c.fragment_id AS orphaned
```

## From Archive to AI Asset

Moving from DDI-L XML to a Neo4j graph is a basic shift:

| Archive Perspective | AI-Ready Perspective |
| -------------------- | --------------------- |
| Storage format | Knowledge representation |
| Documentation | Queryable structure |
| Metadata catalog | Reasoning substrate |
| Static reference | Dynamic context source |

Load DDI-L into Neo4j and survey metadata becomes a first-class part of AI pipelines. It is
no longer just data to fetch. It is structure the model can reason over.

## Getting Started

1. Load your DDI-L files:

   ```bash
   ddigraph bootstrap
   ddigraph load instrument.xml
   ```

2. Add embeddings for semantic search (optional):

   ```cypher
   // After generating embeddings externally
   CALL db.index.vector.createNodeIndex(
     'question_embeddings', 'QuestionItem', 'embedding', 384, 'cosine'
   )
   ```

3. Query for AI applications:

   ```cypher
   // RAG context retrieval
   MATCH (q:QuestionItem)
   WHERE q.question_text CONTAINS $search_term
   MATCH path = (q)<-[:ASKS_QUESTION]-(:QuestionConstruct)<-[:HAS_CONSTRUCT]-(s:Sequence)
   RETURN q, s, path
   ```

## Further Reading

- [Neo4j Graph Data Science](https://neo4j.com/docs/graph-data-science/current/)
- [DDI Lifecycle Specification](https://ddialliance.org/Specification/DDI-Lifecycle/3.3/)
- [LangChain Neo4j Integration](https://python.langchain.com/docs/integrations/graphs/neo4j_cypher)
- [Architecture](../user-guide/architecture.md) - ddigraph design and components
- [Relationships](../user-guide/relationships.md) - Graph schema and relationship types

# Your First Queries

You just loaded a DDI file into Neo4j. Now what?

This page shows you how to explore the data you just loaded. You will run your first Cypher
queries, see the results, and understand what each query does — step by step. No prior database
experience required.

---

## What Happened When You Loaded the Data?

When ddigraph loaded your DDI XML file, it turned it into a **graph** — a set of
**nodes** (things) connected by **relationships** (links between things).

Think of it like this:

- A **node** is like a row in a spreadsheet. It represents one thing, such as a question, a
  variable, or a concept.
- A **relationship** is an arrow connecting two nodes. It tells you how they are related
  (e.g., "Question A *belongs to* Instrument B").

For a DDI Codebook file, ddigraph creates nodes like:

| Node type | What it represents |
|---|---|
| `Dataset` | Your overall survey or study |
| `Variable` | A column in your data (e.g., age, income) |
| `QuestionItem` | A survey question |
| `ConceptScheme` | A group of related concepts |
| `Concept` | A single topic or idea |
| `CodeList` | A list of answer choices |
| `Category` | One answer choice in a list |

---

## Open Neo4j Browser

Neo4j Browser is a web interface where you can run Cypher queries and see the results as
tables or visual graphs.

1. Open your browser and go to: `http://localhost:7474`
2. Log in with your Neo4j username and password (default: `neo4j` / `password`).
3. You will see a text box at the top. This is where you type your queries.
4. Press **Ctrl+Enter** (or **Cmd+Enter** on Mac) to run a query.

---

## Your First 8 Queries

### 1. How many nodes are in the graph?

```cypher
MATCH (n) RETURN count(n) AS total_nodes
```

**What this does:**

- `MATCH (n)` — find every node in the database. The letter `n` is just a variable name
  (you can use any letter).
- `RETURN count(n)` — count them and return the number.
- `AS total_nodes` — give the result column a friendly name.

**What you see:** A single number — the total count of all nodes.

---

### 2. What types of nodes exist?

```cypher
MATCH (n) RETURN labels(n) AS type, count(n) AS count
ORDER BY count DESC
```

**What this does:**

- `labels(n)` — get the "type" of each node (e.g., Variable, Question).
- `ORDER BY count DESC` — sort with the largest groups first.

**What you see:** A table listing each node type and how many of each exist.

---

### 3. List your variables

```cypher
MATCH (v:Variable)
RETURN v.name AS name, v.label AS label
LIMIT 20
```

**What this does:**

- `(v:Variable)` — find only nodes that are of type `Variable`. The `:Variable` part
  is the filter.
- `v.name` and `v.label` — read specific properties (like columns) from each node.
- `LIMIT 20` — only return the first 20 results (useful for large datasets).

**What you see:** A table of variable names and their labels.

---

### 4. Find a question by keyword

```cypher
MATCH (q:QuestionItem)
WHERE toLower(q.question_text) CONTAINS 'age'
RETURN q.question_text AS question
```

**What this does:**

- `WHERE` — filters results, like a search condition.
- `toLower(...)` — converts the text to lowercase so the search works regardless of
  capitalization.
- `CONTAINS 'age'` — only keep questions that include the word "age".

**What you see:** All questions whose text includes the word "age".

---

### 5. See what a variable connects to

```cypher
MATCH (v:Variable {name: 'AGE'})-[r]->(other)
RETURN type(r) AS relationship, labels(other) AS connected_to, other.name AS name
```

**What this does:**

- `{name: 'AGE'}` — find the specific variable named AGE. Change this to any variable name
  from your data.
- `-[r]->` — follow any outgoing relationship from that variable. `r` captures the
  relationship.
- `type(r)` — get the name of the relationship (e.g., `HAS_QUESTION`, `BELONGS_TO`).

**What you see:** Everything that the AGE variable is connected to, and how it's connected.

---

### 6. Show the dataset and its top-level structure

```cypher
MATCH (d:Dataset)-[r]->(child)
RETURN d.id AS dataset, type(r) AS link, labels(child) AS child_type, child.name AS child_name
LIMIT 30
```

**What this does:**

- Starts from the `Dataset` node (the root of your data).
- Follows one step outward to show everything directly connected to it.

**What you see:** The immediate children of your dataset — what it contains at the top level.

---

### 7. Count answer choices in code lists

```cypher
MATCH (cl:CodeList)-[:HAS_CATEGORY]->(cat:Category)
RETURN cl.name AS code_list, count(cat) AS num_choices
ORDER BY num_choices DESC
LIMIT 10
```

**What this does:**

- `[:HAS_CATEGORY]` — follow only relationships of type `HAS_CATEGORY` (not all relationships).
- Groups the results by code list and counts how many categories each one has.

**What you see:** Your longest code lists (most answer choices) at the top.

---

### 8. Find all questions linked to a concept

```cypher
MATCH (c:Concept {label: 'Age'})<-[:ABOUT_CONCEPT]-(q:QuestionItem)
RETURN c.label AS concept, q.question_text AS question
```

**What this does:**

- Starts from a `Concept` node labelled "Age".
- Follows `ABOUT_CONCEPT` relationships *backwards* (the arrow `<-` points left) to find
  questions that reference this concept.
- Change `'Age'` to any concept label in your data.

**What you see:** All questions that are tagged with a given concept.

---

## What's Next?

Now that you can explore your data, here are some good next steps:

- **[Relationship Model](../user-guide/relationships.md)** — see the full list of node types
  and relationship types in your graph.
- **[Neo4j Backend](../backends/neo4j.md)** — learn more about connecting and querying Neo4j.
- **[CLI Reference](../reference/cli.md)** — all available commands for loading, purging, and
  managing your data.
- **[Glossary](../reference/glossary.md)** — plain-language definitions of every term used
  in these docs.

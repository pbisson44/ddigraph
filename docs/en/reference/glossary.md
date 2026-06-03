# Glossary

Plain-language definitions of every technical term used in the ddigraph documentation.
If you see a word in these docs that you don't understand, look it up here.

---

## A

### Adapter / Adapter Pattern

An **adapter** is a piece of code that connects two things that don't speak the same language.
In ddigraph, an adapter takes the data that the DDI parser produces and translates it into the
format that a specific database understands. For example, the `Neo4jGraphAdapter` writes data
to Neo4j, while the `NetworkXAdapter` writes it to a NetworkX graph in memory.

The **adapter pattern** is the design approach that makes this work: the parser doesn't care
which database you use — it just produces data, and the adapter handles the rest.

### Asynchronous (async)

**Asynchronous** means "doing multiple things at once without waiting for each one to finish
before starting the next."

In ddigraph, the parser reads XML and the adapter writes to the database at the same time.
This is much faster than waiting for the database to confirm each write before reading the
next piece of XML. Python's `async`/`await` keywords control this behavior.

---

## B

### Back-pressure

**Back-pressure** is a throttle that slows down one part of a system when another part
can't keep up.

In ddigraph, if the database is writing slowly, back-pressure slows down the XML reader
so the queue between them doesn't grow until the program runs out of memory.
Think of it like a water flow regulator: if the pipe is blocked downstream, it reduces
the flow upstream.

### Batch writing

**Batch writing** means sending many records to the database in a single trip instead of
one record at a time.

Imagine mailing 100 letters: you could make 100 trips to the post office, or put them all
in one box and make 1 trip. Batch writing is the second approach. ddigraph uses Cypher's
`UNWIND` clause to batch writes, which can be 10–100 times faster than writing one record
at a time.

---

## C

### Codebook (DDI Codebook)

**DDI Codebook** is one of the two main DDI XML formats. It is the older, simpler format.
It describes a survey dataset with a central `Dataset` node connected to variables, questions,
and code lists.

Use DDI Codebook if your XML file has a root element like `<codeBook>` or `<codebook>`.

### Cypher

**Cypher** is the query language used by Neo4j — similar to SQL, but designed for graphs
instead of tables.

In SQL you write `SELECT * FROM users WHERE id = 1`. In Cypher you write
`MATCH (u:User {id: 1}) RETURN u`. Cypher uses visual patterns like `(node)-[:RELATIONSHIP]->(other)`
to express how data is connected. You don't need to know Cypher to use ddigraph's CLI,
but it helps when you want to explore your data in Neo4j Browser.

---

## D

### DDI

**DDI** stands for *Data Documentation Initiative*. It is an international standard for
describing social science survey data — things like questionnaires, variables, and code lists.
DDI files are XML files that contain the metadata (descriptions) for a dataset, not the data
itself.

### DDI-CDI

**DDI-CDI** (DDI Cross-Domain Integration) is the newest version of the DDI standard.
It can describe a wider range of data types, including administrative data and linked data.
ddigraph loads DDI-CDI files using the `CDILoader` class.

### DDI-L (DDI Lifecycle)

**DDI-L** (DDI Lifecycle, version 3.x) is a more complex DDI format that supports reusable
components called *fragments*. Each fragment is an independent piece of metadata that can
be referenced by other fragments.

Use DDI-L if your XML file has a root element like `<DDIInstance>` or contains `<Fragment>`
elements.

---

## F

### Fragment / FragmentInstance

A **fragment** in DDI-L is a single reusable unit of metadata — for example, one question,
one variable, or one concept. Fragments can reference other fragments by their ID.

A **FragmentInstance** is a DDI-L XML file that packages many fragments together.
ddigraph loads these with the `DDIFragmentLoader` class.

---

## G

### Graph database

A **graph database** stores data as nodes (things) and relationships (connections between
things), instead of tables and rows.

A relational database says: "A survey has many variables" using a foreign key.
A graph database says: "The `Survey` node is connected to a `Variable` node via a
`HAS_VARIABLE` arrow." Graph databases make complex queries — like "find all questions
linked to this concept through three hops" — much faster and simpler.

ddigraph supports Neo4j (a graph database), but also RDF, Gremlin, and NetworkX.

---

## I

### iterparse

**iterparse** is a streaming XML parser. Instead of loading an entire XML file into
memory at once, iterparse reads one element at a time, processes it, and throws it away.

This is important for large files. A 5 GB DDI file would crash a program that loads it
all at once. With iterparse, ddigraph can process a file of any size using only a small,
constant amount of memory. lxml's `iterparse` is what ddigraph uses internally.

---

## K

### Knowledge graph

A **knowledge graph** is a graph database that represents facts about a domain — who is
connected to what, and why. In ddigraph, your DDI metadata becomes a knowledge graph:
you can ask questions like "what concepts are covered by this instrument?" or "which
variables share the same code list?" by traversing the graph.

---

## M

### MERGE (Neo4j)

**MERGE** is a Cypher operation that means "find this node/relationship if it exists,
or create it if it doesn't." It is like an *upsert* in SQL.

ddigraph uses MERGE so that running `ddigraph load` twice on the same file doesn't
create duplicate nodes. The second run finds the existing nodes and updates them instead
of creating new ones.

---

## N

### Node

In a graph, a **node** is a single item or entity — like a row in a table.
In ddigraph, examples of nodes include `Variable`, `QuestionItem`, `Concept`, and `Dataset`.
Each node has properties (like `name`, `label`, `id`) that describe it.

### Relationship

In a graph, a **relationship** is a named, directed connection between two nodes —
like a foreign key, but with a direction and a name.
For example: `(Question)-[:BELONGS_TO]->(Instrument)` means "this question belongs to
this instrument."

---

## P

### Protocol (Python)

In Python, a **Protocol** is a way to define what methods a class must have, without
making that class inherit from anything.

Think of it as a job description: "To be a graph adapter, your class must have a
`write_batch()` method." Any class that has this method qualifies — it doesn't need to be
a subclass of anything. This is sometimes called *structural subtyping* or *duck typing*.

In ddigraph, `GraphWriteAdapter` is a Protocol that defines the interface every adapter
must implement.

---

## S

### Schema / Schema bootstrap

A **schema** in Neo4j is the set of indexes and constraints that make queries fast and
data consistent. For example, a constraint might say "every `Variable` node must have a
unique `id`."

**Schema bootstrap** is the process of creating these indexes and constraints before
you start loading data. In ddigraph, you run `ddigraph bootstrap` to do this.
It is safe to run multiple times — if the schema already exists, nothing changes.

### Streaming parser

A **streaming parser** processes a file piece by piece, rather than loading the whole
file into memory at once. See also: **iterparse**.

---

## U

### UNWIND (Cypher)

**UNWIND** is a Cypher clause that takes a list of items and processes each one as a
separate row. ddigraph uses UNWIND to send many records to Neo4j in a single query
("here are 500 variables, create all of them at once") instead of sending one query
per record.

This is the main reason ddigraph's batch writing is fast. Instead of 500 round trips
to the database, there is 1.

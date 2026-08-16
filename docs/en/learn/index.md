# Learning ddigraph

A course in eight lessons. It teaches two things at once: the ideas behind
survey metadata as a graph, and the tool that does it.

You do not need to know DDI, Neo4j, or RDF. You do need to read Python and
use a terminal.

## Why a course and not just the guides

The rest of this site answers "how do I do X?" This section answers
"what is going on, and why is it built this way?" The order matters: each
lesson uses what the last one built.

If you only want to load a file and move on, use the
[Quick Start](../getting-started/quickstart.md) instead. Come back when
something surprises you.

## The eight lessons

| # | Lesson | You will be able to | Time |
| --- | -------- | --------------------- | ------ |
| 1 | [Metadata is already a graph](01-metadata-as-a-graph.md) | Say what DDI is and why a graph fits it | 15 min |
| 2 | [Look before you load](02-first-look.md) | Inspect any DDI file without a database | 15 min |
| 3 | [Nodes, edges, identity](03-the-graph-model.md) | Stream any DDI file as nodes and edges | 25 min |
| 4 | [Joining the wider world](04-linked-data.md) | Export RDF that other systems can read | 30 min |
| 5 | [Proving it is right](05-validation.md) | Validate an export against SHACL shapes | 20 min |
| 6 | [Build your own pipeline](06-your-own-pipeline.md) | Send DDI to any store you like | 25 min |
| 7 | [Grounding a model in the graph](07-grounding-an-llm.md) | Stop a language model inventing your survey | 25 min |
| 8 | [Let the model query the graph](08-tools-over-the-graph.md) | Give a model a tool over your metadata | 25 min |

About three hours end to end. Lessons 1 to 6 stand on their own; 7 and 8
build on lesson 3 and can be read straight after it if that is what brought
you here.

## Setup

Lessons 1 to 3 need only the base install. Lessons 4 and 5 need the RDF
extras. No lesson needs a database.

Lessons 7 and 8 build everything locally, so all their exercises run
without an API key. The two examples that call a model are marked as such
and are the only code in the course the test suite does not execute.

```bash
pip install "ddigraph[shacl]"
```

Every lesson works on files that ship with the source repository, so
nothing has to be downloaded:

```bash
git clone https://github.com/pbisson44/ddigraph
cd ddigraph
```

The files are in `tests/fixtures/`. They are small on purpose — small
enough to open in an editor and read, which is the point when you are
learning what the shape of the data is.

| File | Flavor |
| ------ | -------- |
| `codebook_sample.xml` | DDI Codebook |
| `fragment_instance.xml` | DDI Lifecycle 3.3 |
| `cdi_sample.xml` | DDI-CDI 1.0 |

!!! tip "The examples here are tested"
    Every command and script in these lessons runs in the test suite on
    every commit. If one of them breaks, the build fails. They are not
    illustrations — they are the real output of real runs.

## How to use the exercises

Each lesson ends with an exercise and a hidden solution. Try it before you
open the solution; the answer is much less useful than the attempt.

## Where to go next

After lesson 8 you will have seen every part of the package. The
[RDF case study](../advanced/rdf-case-study.md) then takes one code list
all the way from DDI to validated linked data, which is the whole course
applied to a single realistic problem, and
[AI readiness](../advanced/ai-readiness.md) goes further into retrieval and
agentic patterns over a loaded graph.

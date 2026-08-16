# Lesson 7 — Grounding a model in the graph

!!! abstract "What you will learn"
    - Why a language model gets survey structure wrong
    - Build a grounding pack from a DDI file
    - Retrieve only the part of the graph a question needs

## What a model does not know

Ask a language model what answer options a survey question had, and it will
give you a plausible list. Plausible is the problem. It has read a great
many surveys, so it knows what an age band usually looks like — and that is
exactly why it will produce one that reads correctly and is not yours.

Nothing in the model knows that *your* instrument put `Under 18` first, or
that a question was only asked of a subset of respondents. That lives in
your metadata.

So the job is not to make the model smarter. It is to put the facts in
front of it and make clear they are the facts.

## A grounding pack

The simplest useful thing is a compact, factual description of the graph
that goes into the request alongside the question. Lesson 3 already gave
you everything needed to build it:

<!-- runnable -->
```python
import os

from ddigraph import iter_graph


def node_key(node):
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


def name_of(node):
    return node.properties.get("label") or node.properties.get("name") or node_key(node)


nodes, edges = {}, []
for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        nodes[node_key(node)] = node
    for edge in chunk.relationships:
        edges.append((node_key(edge.start), edge.type, node_key(edge.end)))

lines = ["The survey contains these items. Do not invent items that are not listed."]
for key, node in sorted(nodes.items(), key=lambda item: item[1].label):
    text = node.properties.get("question_text")
    lines.append(f"- {node.label}: {name_of(node)}" + (f' — asks "{text}"' if text else ""))

lines.append("")
lines.append("Links between them:")
for start, rel_type, end in edges:
    lines.append(f"- {name_of(nodes[start])} --{rel_type}--> {name_of(nodes[end])}")

pack = "\n".join(lines)
print(pack)
```

```text
The survey contains these items. Do not invent items that are not listed.
- Category: Under 18
- CodeList: Age Groups
- Instrument: Test Instrument
- QuestionConstruct: fragment_id=urn:ddi:test.org:qc1:1.0
- QuestionItem: Question 1 — asks "What is your age?"
- Sequence: Main Sequence

Links between them:
- Test Instrument --HAS_CONSTRUCT--> Main Sequence
- Main Sequence --HAS_CONSTRUCT--> fragment_id=urn:ddi:test.org:qc1:1.0
- fragment_id=urn:ddi:test.org:qc1:1.0 --REFERENCES_QUESTION--> Question 1
- Question 1 --USES_CODELIST--> Age Groups
- Age Groups --HAS_CATEGORY--> Under 18
```

Under 600 characters, and it answers questions the model would otherwise
guess at. Note the links are included, not just the items — "which code
list does the age question use?" is a question about an edge.

## Using it

Put the pack in the system prompt and ask the question normally. This
example is not run by the test suite, because it needs an API key:

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    system=(
        "Answer questions about this survey using only the structure below. "
        "If the answer is not there, say so rather than guessing.\n\n" + pack
    ),
    messages=[{"role": "user", "content": "What could a respondent answer for age?"}],
)

for block in response.content:
    if block.type == "text":
        print(block.text)
```

Model names change. The
[model list](https://docs.claude.com/en/docs/about-claude/models) has the
current ones.

Two details are easy to get wrong.

**`response.content` is a list of blocks, not a string.** Check `block.type`
before reading `block.text` — a response can contain other kinds of block,
and indexing `content[0].text` breaks the first time it does.

**Tell it what to do when the answer is absent.** Without that sentence, a
model asked something the pack does not cover will often produce a
reasonable-sounding answer anyway. With it, you get "the metadata does not
say", which is the answer you actually wanted.

## When the graph is too big

Six nodes fit in a prompt. Sixty thousand do not, and stuffing them in
would be wasteful even if they did — most of the graph is irrelevant to
any one question.

So retrieve first. You do not need a vector database to start; matching on
the text already in the graph gets you a long way:

<!-- runnable -->
```python
import os

from ddigraph import iter_graph


def relevant(path, question, limit=5):
    """Return nodes whose text overlaps the question."""
    words = {word.lower().strip("?.,") for word in question.split() if len(word) > 3}
    hits = []

    for chunk in iter_graph(path):
        for node in chunk.nodes:
            haystack = " ".join(
                str(value) for value in node.properties.values() if isinstance(value, str)
            ).lower()
            score = sum(1 for word in words if word in haystack)
            if score:
                hits.append((score, node))

    hits.sort(key=lambda item: -item[0])
    return [node for _score, node in hits[:limit]]


for node in relevant(os.environ["FIXTURE"], "What are the age groups?"):
    print(node.label, "-", node.properties.get("label"))
```

```text
QuestionItem - Question 1
CodeList - Age Groups
```

Two nodes instead of six. On a real file it is two hundred instead of sixty
thousand, and that is what makes the request affordable.

Both hits score 1 here — `Question 1` matches "what", `Age Groups` matches
"groups" — and Python's sort is stable, so a tie keeps parse order. That is
fine for a first pass and is also the first thing you would improve: score
a match in `question_text` above a match in an internal field, and the
ranking starts meaning something.

!!! tip "Retrieve the neighbours too"
    A node on its own is half an answer. Once you have your matches, follow
    their edges one hop and include what you find — the `CodeList` above is
    only useful with its categories attached. Lesson 8 does exactly that,
    and hands the job to the model instead of guessing at it up front.

## Exercise

The grounding pack above uses `label` for a node's name and falls back to
its identity key. Look at the `QuestionConstruct` line in the output. Why
is it ugly, and what would you do about it?

??? success "Solution"
    `QuestionConstruct` has no `label` or `name` property, so `name_of`
    falls through to the identity key and prints a URN. It is noise: the
    construct is a wiring element in the questionnaire flow, and the model
    does not need it named.

    Two reasonable fixes. Give it a better fallback — `Question 1` is
    reachable one hop away via `REFERENCES_QUESTION`. Or leave structural
    node types out of the pack entirely and collapse the chain, so
    `Instrument → Sequence → Question 1` replaces four lines with one.

    The second is usually better. Every line in the pack costs money on
    every request, and a node the reader never asks about is a line that
    never earns it.

## Check yourself

- Why does a plausible answer from an ungrounded model make things worse?
- Why include the edges and not just the nodes?
- What breaks if you read `response.content[0].text` directly?

---

Next: [Let the model query the graph](08-tools-over-the-graph.md) — giving
it a tool instead of a wall of text.

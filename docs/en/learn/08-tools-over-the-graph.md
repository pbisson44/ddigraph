# Lesson 8 — Let the model query the graph

!!! abstract "What you will learn"
    - Give a model a tool instead of a wall of context
    - Write a tool that answers a real DDI question
    - Know which of the two approaches fits your problem

## The limit of stuffing context

Lesson 7 put facts in the prompt. That works, and it stops working for the
same reason every time: you have to decide what to include *before* you know
what will be asked.

Retrieve too little and the answer is not there. Retrieve too much and you
pay for it on every request. And some questions need a traversal you cannot
anticipate — "which variables come from questions that used this code
list?" is three hops, and no keyword match finds it.

The alternative is to stop guessing. Give the model a tool and let it ask.

## A tool is a function plus a description

A tool has three parts: a name, a description telling the model when to
call it, and a schema for its inputs.

The description is the part people underinvest in. It is how the model
decides whether this tool is relevant, so it should say *when to call it*,
not just what it does:

<!-- runnable -->
```python
ANSWER_OPTIONS_TOOL = {
    "name": "get_answer_options",
    "description": (
        "Return the answer options a respondent could choose for a survey "
        "question. Call this whenever the user asks what someone could answer, "
        "what a variable's values mean, or which categories a question uses. "
        "Matches on question text, case-insensitively."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question text, or any distinctive part of it.",
            }
        },
        "required": ["question"],
    },
}

print(ANSWER_OPTIONS_TOOL["name"], "->", sorted(ANSWER_OPTIONS_TOOL["input_schema"]["properties"]))
```

## Implementing it over the graph

Now the function. This is the traversal from lesson 3, wrapped so it takes
a question and returns options:

<!-- runnable -->
```python
import json
import os

from ddigraph import iter_graph


def node_key(node):
    return "|".join(f"{k}={v}" for k, v in sorted(node.identity.items()))


nodes, edges = {}, []
for chunk in iter_graph(os.environ["FIXTURE"]):
    for node in chunk.nodes:
        nodes[node_key(node)] = node
    for edge in chunk.relationships:
        edges.append((node_key(edge.start), edge.type, node_key(edge.end)))


def follow(start, rel_type):
    """Every node reachable from `start` by one `rel_type` edge."""
    return [end for s, t, end in edges if s == start and t == rel_type]


def get_answer_options(question: str) -> dict:
    """The tool's implementation. Its return value goes back to the model."""
    for key, node in nodes.items():
        if node.label != "QuestionItem":
            continue
        text = node.properties.get("question_text", "")
        if question.lower() not in text.lower():
            continue

        options = []
        for code_list in follow(key, "USES_CODELIST"):
            for category in follow(code_list, "HAS_CATEGORY"):
                found = nodes[category]
                options.append(found.properties.get("label"))
        return {"question": text, "options": options}

    return {"error": f"No question matching {question!r}"}


print(json.dumps(get_answer_options("age"), indent=2))
print(json.dumps(get_answer_options("income"), indent=2))
```

```text
{
  "question": "What is your age?",
  "options": [
    "Under 18"
  ]
}
{
  "error": "No question matching 'income'"
}
```

That second call matters as much as the first. **Return a clear error, not
an empty result.** `{"options": []}` reads to a model as "this question has
no answer options", which is false and which it will report as fact. `error`
tells it the lookup failed, and it will say so.

## Wiring it up

The API call. Not run by the test suite — it needs a key:

```python
import anthropic

client = anthropic.Anthropic()

messages = [{"role": "user", "content": "What could someone answer for the age question?"}]

response = client.messages.create(
    model="claude-opus-5",
    max_tokens=1024,
    tools=[ANSWER_OPTIONS_TOOL],
    messages=messages,
)

if response.stop_reason == "tool_use":
    tool_call = next(block for block in response.content if block.type == "tool_use")
    result = get_answer_options(**tool_call.input)

    messages.append({"role": "assistant", "content": response.content})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": json.dumps(result),
                }
            ],
        }
    )

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        tools=[ANSWER_OPTIONS_TOOL],
        messages=messages,
    )

for block in response.content:
    if block.type == "text":
        print(block.text)
```

Model names change. The
[model list](https://docs.claude.com/en/docs/about-claude/models) has the
current ones.

Three things that are easy to get wrong:

**Append the whole `response.content`**, not just the text. It contains the
`tool_use` block, and the next request needs it to match your result to the
call.

**`tool_use_id` must match.** It is how the API pairs a result with its
call, and it is not optional.

**One round is not the loop.** A model may call a tool, read the result, and
call another. Real code loops until `stop_reason` is no longer `tool_use`.
The Anthropic SDK ships a tool runner that does this for you.

## Which approach when

| | Grounding pack (lesson 7) | Tools (this lesson) |
| --- | --- | --- |
| Graph size | Small, or narrow after retrieval | Any |
| Question shape | Known in advance | Open-ended |
| Round trips | One | Two or more |
| Fails by | Omitting what was needed | Calling the wrong tool |

They combine well. A small pack orients the model — what this survey is,
which types exist — and tools let it go get specifics. The pack is cheap
because it no longer has to be complete.

## Exercise

Write a second tool, `find_questions_about(concept)`, that returns the
questions linked to a concept. Then decide: should it be a separate tool,
or another parameter on the first one?

??? success "Solution"
    ```python
    CONCEPT_TOOL = {
        "name": "find_questions_about",
        "description": (
            "Find survey questions that measure a given concept. Call this when "
            "the user asks which questions cover a topic or concept."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"concept": {"type": "string", "description": "The concept name."}},
            "required": ["concept"],
        },
    }
    ```

    Keep it separate. Two tools with clear boundaries beat one tool with a
    mode flag, because the model chooses by reading descriptions — and
    "returns answer options *or* questions, depending on which argument you
    pass" describes nothing well.

    The signal that you have gone too far the other way is a tool set where
    several descriptions could plausibly match the same request. At that
    point the model is guessing, and the fix is to merge them or sharpen the
    boundary in the descriptions.

## Check yourself

- Why is the description the most important part of a tool definition?
- Why return an error rather than an empty list?
- When is a grounding pack the better choice than a tool?

---

That is the course. The [RDF case study](../advanced/rdf-case-study.md)
applies it end to end, and [AI readiness](../advanced/ai-readiness.md) goes
further into retrieval and agentic patterns over a loaded graph.

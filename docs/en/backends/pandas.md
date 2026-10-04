# pandas Backend

pandas puts the graph in two tables: one row per node, one row per
relationship. Use it when the next step is a spreadsheet, a report or a
join with other data.

## Dependencies

pandas is an optional extra:

```bash
pip install "ddigraph[pandas]"
```

## Basic Usage

<!-- runnable -->
```python
import os

from ddigraph.backends.pandas import to_dataframes

frames = to_dataframes(os.environ["FIXTURE"])

print(len(frames.nodes), "nodes,", len(frames.relationships), "relationships")
print(frames.nodes["node_label"].value_counts())
```

The source can be DDI XML of any flavor, or an RDF export such as
`survey.ttl`. You can also pass chunks you already have from
`ddigraph.iter_graph()`.

## The Two Tables

`frames.nodes` has one row per node:

- `node_label` is the node's type, such as `Variable`.
- `node_id` is its key. It is unique within its type.
- Every other column is a field. Different types have different fields,
  so the table has the union of them all, and most cells in a row are
  empty.

`frames.relationships` has one row per relationship, with five columns:
`start_label`, `start_id`, `type`, `end_label` and `end_id`.

The columns match `ddigraph export --format csv`, so the files and the
tables are interchangeable.

## One Type at a Time

`frames.of(label)` returns the nodes of one type, with only the columns
that type uses:

<!-- runnable -->
```python
import os

from ddigraph.backends.pandas import to_dataframes

frames = to_dataframes(os.environ["FIXTURE"])

questions = frames.of("QuestionItem")
print(questions.columns.tolist())
```

## Joining the Tables

A relationship names its two ends by type and key. Join on both to bring
in what you need about each end:

<!-- runnable -->
```python
import os

from ddigraph.backends.pandas import to_dataframes

frames = to_dataframes(os.environ["FIXTURE"])
ends = frames.nodes[["node_label", "node_id", "label"]]

linked = frames.relationships.merge(
    ends,
    left_on=["start_label", "start_id"],
    right_on=["node_label", "node_id"],
).merge(
    ends,
    left_on=["end_label", "end_id"],
    right_on=["node_label", "node_id"],
    suffixes=("_start", "_end"),
)
print(linked[["label_start", "type", "label_end"]])
```

## Saving

```python
import pandas as pd

frames.nodes.to_csv("nodes.csv", index=False)
frames.relationships.to_csv("relationships.csv", index=False)

with pd.ExcelWriter("survey.xlsx") as writer:  # needs openpyxl, in the extra
    frames.nodes.to_excel(writer, sheet_name="nodes", index=False)
    frames.relationships.to_excel(writer, sheet_name="relationships", index=False)
```

## See Also

- [NetworkX](networkx.md) - The same graph, for graph algorithms
- [Gremlin](gremlin.md) - The same graph, in a database
- [CLI export](../reference/cli.md) - The same tables, as CSV files

# Codebook composition DSL — design

This page is the design reference for the Codebook composition
refactor: collapsing the hand-written DDI-Codebook handlers in
`src/ddigraph/ingest/loader.py` onto a declarative,
override-file-driven extractor. Read this before the runtime lands;
the syntax choices here are the part worth reviewing.

## Why

`loader.py` is ~4,300 lines. About 40 of its ~44 `ingest_*` methods
are near-identical: resolve an id, dedup it, pull a handful of fields
out of child elements, build a record, append it. The repetition is
the bulk of the file. Earlier refactors already moved every node and
relationship *name* into the XSD-derived generator plus
`schema_overrides.toml`; this refactor does the same for the
*extraction recipe* so the XSDs (plus a small declarative override)
become the single source of truth for what each codebook element
contributes to the graph.

## Honest scope

Not every handler can — or should — become declarative.

- **~33 flat handlers** (`ingest_organization`, `ingest_series`,
  `ingest_group`, `ingest_methodology`, `ingest_software`,
  `ingest_funding`, `ingest_coverage`, …) only do id + dedup +
  shallow field extraction + append. These collapse fully into the
  DSL. This is where the line-count win is.
- **~7 recursive handlers** — `ingest_variable` (115 lines),
  `ingest_contributor_role` (94), `ingest_question_item` (65),
  `ingest_question` (55), `ingest_study` (48), plus
  `ingest_var_group` and `ingest_category_group` — create *child*
  records from nested elements (a `var` spawns `Question`,
  `Universe`, `Category`, and `Concept` records, each with its own
  dedup set and "raise on duplicate variable" semantics). Forcing
  that recursion into TOML would produce a config language more
  complex than the Python it replaces, which would defeat the
  simplicity goal. **These stay as Python**, but rewritten to call the
  same shared selector primitives the DSL runtime uses, so the
  extraction logic is defined once.

Net effect: `loader.py` drops from ~4,300 to roughly 1,400–1,700
lines (not the original ~900 estimate). The remaining mass is the
seven recursive handlers expressed as short, primitive-composed
Python plus the dispatch glue. The ~900 figure assumed the recursive
handlers could be fully declarative; this design consciously trades
that for readability.

## Selector primitives

A single module, `src/ddigraph/ingest/_compose.py`, exposes pure
functions that take an `lxml` element and return a scalar / list /
sub-element. They replace the ad-hoc helpers scattered through
`loader.py` (`_first_text`, `_first_text_any`, `_common_metadata`,
`_textual_metadata`, `_reference_values_by_suffix`, …). Each is
individually unit-tested on synthetic fixtures.

| Primitive | Signature | Replaces |
|---|---|---|
| `text` | `text(elem, path) -> str \| None` | `_first_text(elem, path)` |
| `text_any` | `text_any(elem, *paths) -> str \| None` | `_first_text_any` |
| `nested_text` | `nested_text(elem, *path) -> str \| None` | `get_nested_text` (utils.parsing) |
| `attr` | `attr(elem, child, name) -> str \| None` | `location.get("fileid")` patterns |
| `count` | `count(elem, child_tag) -> int` | manual `len(findall())` |
| `metadata` | `metadata(elem) -> dict[str, str \| None]` | `_common_metadata` (agency/version/urn) |
| `textual` | `textual(elem) -> dict[str, str \| None]` | `_textual_metadata` (name/label/description/rationale/language) |
| `refs_by_suffix` | `refs_by_suffix(elem, suffix) -> list[str]` | `_reference_values_by_suffix` |
| `lookup` | `lookup(elem, table, child_tag) -> str \| None` | `RESPONSE_DOMAIN_TYPES.get(...)` |
| `truncate` | `truncate(value, n) -> str \| None` | `text[:n]` |
| `coerce` | `coerce(value, xsd_type) -> object` | scattered date/int parsing |

`coerce` is keyed by the XSD simple type the generator already records
per property (the generator emits this into
`src/ddigraph/schema/_generated/codebook.py`). Lives in a sibling
`src/ddigraph/ingest/_coerce.py` so it is independently testable.

All primitives are private (`_compose`, `_coerce` modules) — they do
not widen the public surface, so `tests/test_public_api.py` stays
green.

## Flat-handler registry — typed Python, not a string DSL

**Design revision (recorded during implementation).** The first
cut of this doc specified a string-expression grammar in
`schema_overrides.toml` (`name = "text('name')"`). Surveying the real
flat handlers (`ingest_file`, `ingest_series`, `ingest_group`,
`ingest_data_collection_event`, …) showed the grammar would have to
grow `or`-chains (`text('.//fileURI') or attr('URI')`), field
aliases (`label = name`), `metadata(label=...)` parameter passing,
and the *textual-with-label-override* idiom
(`t = textual(elem); if t['label'] is None: t['label'] = <expr>`).
A string mini-language that handles all of that stops being "tiny"
and starts being an interpreter — which contradicts the simplicity
goal and is exactly the kind of bespoke machinery this work is meant
to delete.

Instead, each flat handler is one `CompositionSpec` entry in a
**typed Python registry** at
`src/ddigraph/ingest/_composition_specs.py`. It is just as
declarative (one place, data-driven, zero per-handler control flow),
but it is mypy-checked, needs no parser, and composes the `_compose`
primitives directly as callables. The override TOML stays the home
for *node/relationship* metadata (handled by the earlier
schema-generation refactors); the extraction recipe, being
code-shaped, lives in code.

```python
from ddigraph.ingest import _compose as c
from ddigraph.ingest._composition_specs import CompositionSpec, Field

SPECS = {
    "filedscr": CompositionSpec(
        collection="data_files",
        record="DataFileRecord",  # resolved by name against loader
        id_field="file_id",
        # No slug -> if the element has no id, skip it (matches the
        # current ``if not file_id ... return``). A slug enables the
        # ``<dataset>:<slug>_<counter>`` synthesised fallback instead.
        id_slug=None,
        dedup="seen_files",
        fields=(
            Field("name", lambda e: c.text(e, ".//fileName")),
            Field("uri", lambda e: c.text(e, ".//fileURI") or c.attr(e, "URI")),
            Field("label", alias="name"),  # reuse another field's value
        ),
        splat_metadata=True,  # **_common_metadata(elem)
    ),
}
```

`Field` is one of: a `select=` callable `(elem) -> value`, an
`alias=` reference to another field already computed in the same
spec, or a `const=` literal. `splat_metadata` / `splat_textual`
booleans cover the `**_common_metadata` / `**_textual_metadata`
idioms; `textual_label_fallback=<Field>` covers the override idiom in
one declarative slot. That is the entire surface — no conditionals,
no loops, no recursion. Anything beyond it is a recursive handler and
stays in Python (next section).

The walker, `BatchBuilder._run_composition(tag, elem)` in
`loader.py`, is ~40 lines: resolve id (slug fallback or skip), claim
dedup, evaluate fields in order (so `alias` can see earlier results),
splat metadata/textual, construct the record by name, append. The
~33 flat handler method bodies collapse to a single
`self._run_composition("<tag>", elem)` call (or are removed entirely
once the dispatch table routes flat tags straight to the walker in
the dispatch-collapse stage).

This keeps the registry reviewable, the runtime tiny, and every line
mypy-checked — and the snapshot test proves the output is
byte-identical to the hand-written handlers.

## Recursive handlers (stay Python, reuse primitives)

`ingest_variable` after the migration is illustrative — it shrinks
from 115 lines to ~40 by delegating every extraction to a primitive
and every sub-record to a small typed helper, while keeping the
explicit control flow (and the "raise on duplicate variable ID"
contract) in Python where a reader can see it:

```python
def ingest_variable(self, elem: etree._Element) -> None:
    variable_id = self._resolve_id(elem, slug="var")
    if not self._claim_id(self.seen_variable_ids, variable_id, strict=True):
        raise ValueError(f"Duplicate variable ID {variable_id!r}")

    self._spawn_question(elem.find("qstn"), parent_id=variable_id)
    universe_id = self._spawn_universe(elem.find("universe"), parent_id=variable_id)
    self._spawn_categories(elem.findall("catgry"))
    self._spawn_concept(elem.find("concept"))

    self._append_and_count(
        self.variables,
        VariableRecord(
            dataset_id=self.dataset_id,
            dataset_name=self.dataset_name,
            variable_id=variable_id,
            file_id=compose.attr(elem.find("location"), None, "fileid"),
            universe_id=universe_id,
            **compose.textual(elem),
            **compose.metadata(elem),
        ),
        "variables",
    )
```

The `_spawn_*` helpers are the only new Python; each is ~10 lines and
itself uses the primitives. `_claim_id` gains an optional
`strict=True` to preserve the duplicate-variable exception.

## Migration sequence

Every commit keeps the per-commit quality gate green (ruff format/check,
mypy, `generate_schema_definitions --check`, `xsd_coverage
--structural --structural-threshold 100`, full pytest including the
new snapshot test) and the snapshot test byte-identical.

1. **`_compose.py` + unit tests** — primitives only, no loader
   change. Snapshot unaffected. (`_coerce.py` deferred until the
   generator emits per-property XSD simple types.)
2. **`_composition_specs.py` registry + `_run_composition` walker** —
   add `CompositionSpec` entries for the flat handlers (in batches,
   validating the walker on a representative subset first) and the
   `_run_composition(tag, elem)` walker. Replace those handlers'
   bodies with a single call into the walker. Snapshot must stay
   byte-identical at every commit.
3. **Recursive handler rewrites** — one commit per handler
   (`ingest_variable`, `ingest_study`, `ingest_question_item`,
   `ingest_question`, `ingest_contributor_role`, `ingest_var_group`,
   `ingest_category_group`), each rewriting the body to primitive +
   `_spawn_*` form. Snapshot byte-identical per commit.
4. **Dispatch collapse** — the `_build_handlers` table at
   `loader.py:1836` becomes `tag -> _run_composition` for flat tags;
   only the seven recursive tags keep explicit method entries.
5. **CHANGELOG** under `## [0.4.0]`.

## Verification

The snapshot harness at `tests/test_codebook_loader_snapshot.py`
(already committed) captures every batch the loader produces for
`tests/fixtures/codebook_sample.xml`. It is the byte-equality gate
for every commit in the registry and dispatch-collapse work.
Intentional schema changes regenerate
the snapshot via `REGEN=1 pytest
tests/test_codebook_loader_snapshot.py` with the JSON diff reviewed in
the same commit. `test_snapshot_covers_the_bespoke_handlers` keeps the
fixture meaningful (it must keep producing variables, studies,
questions, question_items, organizations, data_files).

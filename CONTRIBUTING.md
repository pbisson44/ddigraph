# Contributing to ddigraph

Thanks for taking the time to look at the project. This file is the
short version; the deeper guide lives at
`docs/en/project/contributing.md` (and `docs/fr/project/contributing.md`).

## Quick start

```bash
git clone https://github.com/pbisson44/ddigraph
cd ddigraph

# uv is the recommended tooling, but ``pip install -e .[dev,docs]`` works too.
uv sync --extra dev --extra docs

# Run every gate the CI uses.
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy .
.venv/bin/python -m pytest
.venv/bin/python scripts/xsd_coverage.py --structural --structural-threshold 100
.venv/bin/python scripts/generate_schema_definitions.py --check
.venv/bin/python scripts/generate_vocabulary.py --check
npx --yes markdownlint-cli2@0.18.1 "**/*.md" "!**/site-packages/**" "!**/.venv/**"
```

The same gates are wrapped as Makefile targets: `make lint`,
`make typecheck`, `make test`, `make lint-md`, `make check-schemas`,
`make check-schema-definitions`, `make check-vocabulary`, and
`make check-readability` (the last one needs the `docs` extra).

## Documented examples are executed

A fenced code block in `docs/` opts into being run by carrying a
`<!-- runnable -->` comment on the line before it. `tests/test_docs_examples.py`
then executes it, in both languages, against the fixtures in `tests/fixtures/`.

Prefer making an example runnable over leaving it illustrative. Three
documented examples in this repository could not run for months --
`nx.info(G)` was removed in NetworkX 3.x, and the RDF page described a
parser API that has never existed -- because nothing executed them.

Examples needing a live database cannot be marked runnable. The same test
file still checks that every `from ddigraph... import X` in the docs
resolves, which covers those blocks.

## Mutation testing

Scoped, not global, and not a CI gate:

```bash
make mutation          # a few minutes
make mutation-results  # list the survivors
```

`[tool.mutmut]` in `pyproject.toml` restricts it to the RDF vocabulary and
the graph tier, where the tests are the only thing standing between a
subtle mapping error and silently wrong output. The parsers are excluded
deliberately: they run to thousands of lines, and they are already pinned
by byte-equality snapshots and a blocking 100 % XSD coverage gate.

Read the survivors with judgement rather than chasing the number. Two
categories are not worth killing:

- Mutations of docstrings, log messages and error text.
- Mutations inside functions whose result is computed once at import into
  a module-level constant, such as `_LIFECYCLE_TERMS`. The constant is
  already built by the time a test runs, so the mutant is unreachable.

What is worth acting on is a mutation that changes behaviour and no test
notices. That is how `to_lower_camel("_")` was found to raise `ValueError`:
the emptiness guard sat after the unpack that raises.

## Where things live

- `src/ddigraph/` -- the Python package. The public CRUD entry
  points (`load`, `aload`, `detect`, `bootstrap`, `LoadResult`) live
  in `ddigraph.api`; the loaders sit under `ddigraph.ingest/`.
- `src/ddigraph/graph/view.py` -- `iter_graph`, the backend-neutral
  seam. All three DDI flavors project to the same `GraphChunk`, and
  every exporter, previewer and validator consumes that rather than a
  parser. Reach for it before writing anything flavor-specific.
- `src/ddigraph/rdf/` -- the vocabulary, writer, reader and SHACL
  emitter. `vocabulary.py` holds plain strings and must never import
  `rdflib`; `tests/test_extras_lazy_imports.py` fails the build if any
  module here top-level-imports an optional extra.
  `docs/{en,fr}/ns/vocabulary.ttl` is *generated* from these tables --
  re-run `python scripts/generate_vocabulary.py` after touching them.
- `src/ddigraph/exporter.py` and `previewer.py` -- the file-writing
  verbs (`export`, `preview`). Neither opens a database. The module is
  `previewer`, not `preview`, so the re-exported `ddigraph.preview`
  function does not shadow it.
- `src/ddigraph/schema/_generated/` -- *generated* node and
  relationship metadata. Do not edit by hand; re-run
  `python scripts/generate_schema_definitions.py` after a schema
  change. The override file at
  `src/ddigraph/schema/_overrides/schema_overrides.toml` is the
  human-edited bridge between the XSDs and the runtime tables.
- `schemas/` -- bundled DDI XSDs (Codebook 2.6, DDI-L 3.x, DDI-CDI 1.0).
  The structural-coverage audit blocks PRs if any concrete
  identifiable element drops below 100% relationship coverage.
- `tests/` -- pytest tree. New tests follow the existing pattern;
  the `tests/test_public_api.py` guard enforces the public/private
  naming convention.
- `docs/en/` and `docs/fr/` -- mkdocs-material sources in two
  languages.

## Pull requests

1. Branch from `main`.
2. Run the gates above and `pre-commit run --all-files` if you have
   pre-commit installed.
3. Open the PR; explain *why* the change is needed in the
   description, not just *what* it does.
4. CI runs the same gates plus a TestPyPI dry-run for the publish
   workflow. The structural-coverage and markdownlint gates are
   blocking.

## Releasing

Releases are fully automatic. There is one manual act: bumping
`version` in `pyproject.toml` and dating the matching `CHANGELOG.md`
heading. Merging that to `main` does the rest in a single workflow run:

1. `detect-release` compares the version to the existing tags.
2. `publish` uploads to PyPI via OIDC Trusted Publishing, pushes the
   `vX.Y.Z` tag, and creates the GitHub Release with the notes taken
   from that version's CHANGELOG section.
3. `docs` deploys the site with `mkdocs gh-deploy`.

Two things about that sequence are easy to get wrong, so they are
worth stating:

- **The docs job depends on `publish`, not on the `release` event.**
  GitHub does not fire workflow events for anything created with the
  default `GITHUB_TOKEN` -- a recursion guard -- so the Release the
  workflow creates would never trigger a `release`-gated job. Keying
  the deploy off the job instead keeps it in the same run. A Release
  published by hand through the web UI still deploys the docs, because
  that one *does* fire the event.
- **Every step is idempotent.** PyPI accepts a version exactly once,
  so the upload passes `skip-existing`, and the release step edits an
  existing Release rather than failing to create it. Re-running the
  workflow is safe.

Nothing publishes without a version bump: a push to `main` that leaves
the version alone skips `publish`, and therefore skips `docs` too.

## Security

Please report security issues per `SECURITY.md` (do not file a
public issue).

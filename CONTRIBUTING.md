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
npx --yes markdownlint-cli2@0.18.1 "**/*.md" "!**/site-packages/**" "!**/.venv/**"
```

The same gates are wrapped as Makefile targets: `make lint`,
`make typecheck`, `make test`, `make lint-md`, `make check-schemas`,
`make check-schema-definitions`, and `make check-readability` (the
last one needs the `docs` extra).

## Where things live

- `src/ddigraph/` -- the Python package. The public CRUD entry
  points (`load`, `aload`, `detect`, `bootstrap`, `LoadResult`) live
  in `ddigraph.api`; the loaders sit under `ddigraph.ingest/`.
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

## Security

Please report security issues per `SECURITY.md` (do not file a
public issue).

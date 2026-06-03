# Contributing to ddigraph

Thank you for your interest in contributing to ddigraph. This guide covers everything you need
to get started, from setting up a development environment to submitting pull requests.

## Development Setup

### Prerequisites

- Python 3.12, 3.13, or 3.14
- Git
- A running Neo4j instance (for integration tests)

### Clone and Install

```bash
git clone https://github.com/pbisson44/ddigraph.git
cd ddigraph
pip install -e ".[dev,docs]"
```

This installs ddigraph in editable mode with all development and documentation dependencies:

- **dev**: mypy, ruff, pytest, pytest-asyncio, psutil, types-lxml
- **docs**: mkdocs, mkdocs-material, mkdocs-static-i18n, pymdown-extensions

### Verify Installation

```bash
# Check that the CLI works
ddigraph --help

# Check that the package imports correctly
python -c "import ddigraph; print(ddigraph.__version__)"
```

---

## Running Tests

The test suite uses [pytest](https://docs.pytest.org/) with async support via
[pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio):

```bash
# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_config.py

# Run tests matching a pattern
pytest -k "test_fragment"
```

Tests are configured with `asyncio_mode = "auto"` in `pyproject.toml`, so async test functions
are detected automatically without needing the `@pytest.mark.asyncio` decorator.

!!! tip "Neo4j for integration tests"
    Some tests require a running Neo4j instance. Start one locally with Docker:

    ```bash
    docker run -d --name neo4j-test \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/password \
        neo4j:latest
    ```

---

## Linting and Formatting

ddigraph uses [ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
# Check for lint errors
ruff check .

# Check Google-style docstrings for public API modules
ruff check src/ddigraph --select D --ignore D1,D202

# Auto-fix lint errors where possible
ruff check . --fix

# Format code
ruff format .

# Check formatting without modifying files
ruff format . --check
```

### Ruff Configuration

The project is configured in `pyproject.toml`:

- **Line length**: 100 characters
- **Target version**: Python 3.12
- **Quote style**: double quotes
- **Indent style**: spaces
- **Line ending**: LF
- **Lint rules**: E, F, I, B, UP, RUF (plus a dedicated docstring lint command for `src/ddigraph`)
- **Docstring convention**: Google (via Ruff pydocstyle rules)

---

## Type Checking

ddigraph uses strict [mypy](https://mypy-lang.org/) type checking:

```bash
mypy .
```

The mypy configuration in `pyproject.toml` enables:

- `strict = true` -- all optional strictness flags
- `warn_unreachable = true` -- flag dead code
- `plugins = ["pydantic.mypy"]` -- pydantic model validation
- `namespace_packages = true` -- support for the `src/` layout

All new code must pass strict mypy. Use `TYPE_CHECKING` imports and `from __future__ import
annotations` for forward references.

---

## Documentation

The documentation site is built with [mkdocs-material](https://squidfunk.github.io/mkdocs-material/)
and supports bilingual content (English and French) via
[mkdocs-static-i18n](https://github.com/ultrabug/mkdocs-static-i18n).

### Local Preview

```bash
mkdocs serve
```

This starts a local server at `http://127.0.0.1:8000` with live reload.

### Documentation Structure

```text
docs/
  en/                     # English documentation
    index.md
    getting-started/
    user-guide/
    backends/
    reference/
    advanced/
    project/
  fr/                     # French documentation
    ...
```

### Writing Guidelines

- Use [admonition blocks](https://squidfunk.github.io/mkdocs-material/reference/admonitions/)
  (`!!! tip`, `!!! warning`, etc.) for callouts
- Use [content tabs](https://squidfunk.github.io/mkdocs-material/reference/content-tabs/)
  (`=== "Tab Name"`) for multi-option examples
- Use [Mermaid diagrams](https://squidfunk.github.io/mkdocs-material/reference/diagrams/) for
  architecture and flow illustrations
- Keep code examples copy-pasteable and tested
- Cross-link related pages using relative markdown links

---

## Release Packaging Checklist

Before tagging a release, verify that source distribution contents are complete:

```bash
python -m build --sdist
python - <<'PY'
import glob
import tarfile

sdist = glob.glob('dist/*.tar.gz')[0]
required = [
    'src/ddigraph/__init__.py',
    'src/ddigraph/cli.py',
    'src/ddigraph/config.py',
    'src/ddigraph/schema/ddi_graph.py',
]

with tarfile.open(sdist, 'r:gz') as archive:
    names = archive.getnames()

missing = [suffix for suffix in required if not any(name.endswith(suffix) for name in names)]
if missing:
    raise SystemExit(f'Missing required source files in sdist: {missing}')

print('sdist content check passed')
PY
```

CI also runs this check on Python 3.12 to guard against regressions in `pyproject.toml` packaging rules.

---

## Pull Request Process

### Before You Start

1. Check the [issue tracker](https://github.com/pbisson44/ddigraph/issues) for existing issues
   or discussions related to your change.
2. For large changes or new features, open an issue first to discuss the approach.

### Creating a Pull Request

1. **Fork and branch**: Create a feature branch from `main`:

    ```bash
    git checkout -b feature/my-improvement
    ```

2. **Make your changes**: Write code, tests, and documentation.

3. **Run the full check suite**:

    ```bash
    ruff check .
    ruff check src/ddigraph --select D --ignore D1,D202
    ruff format .
    mypy .
    pytest
    ```

4. **Commit with clear messages**: Use descriptive commit messages that explain the *why*, not
   just the *what*.

5. **Push and open a PR**: Push your branch and open a pull request against `main`. Include:
    - A summary of the change and its motivation
    - How you tested the change
    - Any breaking changes or migration notes

### Review Checklist

All pull requests should satisfy:

- [ ] All tests pass (`pytest`)
- [ ] No lint errors (`ruff check .`)
- [ ] Code is formatted (`ruff format .`)
- [ ] Type checking passes (`mypy .`)
- [ ] New features include tests
- [ ] Documentation is updated if behavior changes
- [ ] No secrets or credentials in committed files

---

## Code Conventions

### Style

- **Formatter**: ruff with double quotes, 100-character line length, space indentation
- **Imports**: sorted by ruff (isort-compatible), with `ddigraph` as a known first-party package
- **Type annotations**: required on all public functions and methods (strict mypy)
- **Docstrings**: use Google-style docstrings for public APIs

### Async Patterns

ddigraph uses async/await for I/O-bound operations. Follow these patterns:

```python
from __future__ import annotations
from collections.abc import Awaitable
from typing import Protocol

# Protocols that support both sync and async
class MyProtocol(Protocol):
    def do_work(self) -> None | Awaitable[None]: ...

# Async functions for I/O operations
async def load_data(driver, path: str) -> dict[str, int]:
    async with driver.session() as session:
        result = await session.run(query, params)
        return await result.data()
```

### Error Handling

- Raise `ValueError` for invalid user input (file paths, dataset IDs, configuration)
- Raise `RuntimeError` for infrastructure failures after retries are exhausted
- Use structured logging (`get_logger(__name__)`) for operational messages
- Never swallow exceptions silently

---

## Adding New DDI Entity Types

To add support for a new DDI element type:

1. **Define the node** in `src/ddigraph/schema/definitions.py`:

    ```python
    NodeDefinition(
        label="MyNewEntity",
        id_field="entity_id",
        properties=("entity_id", "name", "label", "description"),
        indexes=("name",),
        is_fragment=True,  # True for DDI-L types
    )
    ```

2. **Add it to the schema tuple**: Include the new `NodeDefinition` in `CODEBOOK_NODES` or
   `FRAGMENT_NODES` in the `DDISchema` class.

3. **Add parsing logic**: Update the appropriate parser in `src/ddigraph/ingest/` to extract
   the new element from DDI XML.

4. **Add relationship definitions**: If the new entity connects to existing types, add
   `RelationshipDefinition` entries.

5. **Write tests**: Add test cases covering parsing, schema generation, and round-trip ingestion.

6. **Update documentation**: Document the new entity in the relationship model and schema
   reference pages.

---

## Adding New Graph Backends

To add a new graph backend, implement the `GraphWriteAdapter` protocol:

```python
from ddigraph.schema.adapter import GraphWriteAdapter
from ddigraph.schema.ddi_graph import DDIIngestGraph


class MyBackendAdapter:
    """Adapter for MyBackend graph database."""

    async def write_batch(
        self,
        graph: DDIIngestGraph,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> None:
        for node in graph.nodes():
            await self.backend.create_node(node["label"], node["properties"])
        for rel in graph.relationships():
            await self.backend.create_edge(
                rel["start"], rel["end"], rel["type"], rel["properties"]
            )

    async def purge_dataset(
        self,
        dataset_id: str,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> None:
        await self.backend.delete_by_dataset(dataset_id)
```

### Implementation Guidelines

1. **Batch operations**: Accumulate writes and flush in batches for performance.
2. **Idempotent writes**: Use upsert/MERGE semantics so retries are safe.
3. **Async or sync**: The protocol accepts both `None` and `Awaitable[None]` return types.
4. **Add a demo script**: Create a `demo/load_mybackend.py` showing end-to-end usage.
5. **Add a documentation page**: Create `docs/en/backends/mybackend.md` with setup and usage
   instructions.

See [Adapter Architecture](../user-guide/adapter.md) for detailed examples including NetworkX,
Gremlin, and RDF adapters.

---

## Issue Reporting Guidelines

When opening a new issue, please include:

- **ddigraph version**: output of `ddigraph --version` or `python -c "import ddigraph; print(ddigraph.__version__)"`
- **Python version**: output of `python --version`
- **Operating system**: e.g., Ubuntu 22.04, macOS 14, Windows 11
- **Neo4j version** (if applicable): e.g., Neo4j 5.x Community/Enterprise
- **Steps to reproduce**: minimal commands or code to trigger the issue
- **Expected vs. actual behavior**: what you expected and what happened instead
- **Full error traceback**: the complete stack trace, not just the final line
- **DDI file details** (if applicable): format (Codebook/Lifecycle), approximate size, and
  whether you can share the file or a reduced sample

!!! tip "Minimal reproducible example"
    If your issue involves a specific DDI file, try to reduce it to the smallest XML snippet that
    still triggers the problem. This significantly speeds up debugging.

---

## License

ddigraph is released under the [MIT License](https://github.com/pbisson44/ddigraph/blob/main/LICENSE).
By contributing, you agree that your contributions will be licensed under the same terms.

---

See the [FAQ](faq.md) for common questions and the [Changelog](changelog.md) for release history.

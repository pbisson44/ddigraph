"""Validate the optional-extras split documented in ``pyproject.toml``.

Step J of the simplification plan moved ``rdflib``, ``gremlinpython``,
``networkx``, ``pandas``, ``openpyxl``, and ``sdmx1`` from the core
runtime ``dependencies`` array into named extras
(``[rdf]``, ``[gremlin]``, ``[networkx]``, ``[pandas]``, ``[sdmx]``).
For that split to actually shrink the base install footprint, no module
under ``src/ddigraph/`` may import any of those packages at the top
level: a stray ``import rdflib`` would silently re-introduce the
dependency.

These tests pin the invariant. They run regardless of whether the
optional packages happen to be installed in the test environment.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src" / "ddigraph"

# Packages that must never be imported at module top level by any file
# under ``src/ddigraph/``. Lazy imports inside functions / methods are
# allowed -- detected by walking only the module-level ``Import`` and
# ``ImportFrom`` nodes.
_OPTIONAL_DEPS = frozenset(
    {
        "rdflib",
        "gremlin_python",
        "networkx",
        "pandas",
        "openpyxl",
        "sdmx1",
        "sdmx",
    }
)


def _module_level_imports(path: Path) -> set[str]:
    """Return every package name imported at module top level in ``path``."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize(
    "path",
    sorted(_SRC.rglob("*.py")),
    ids=lambda path: str(path.relative_to(_SRC.parent)),
)
def test_no_top_level_optional_dep_imports(path: Path) -> None:
    """No ``src/ddigraph/`` module top-level-imports an optional extra.

    A failure means a module gained a hard dependency that
    ``pip install ddigraph`` (without extras) cannot satisfy. Either
    push the import down inside a function so it stays lazy, or update
    ``pyproject.toml`` to promote the package back into the core
    ``dependencies`` array.
    """
    leaked = _module_level_imports(path) & _OPTIONAL_DEPS
    assert not leaked, (
        f"{path.relative_to(_SRC.parent)} top-level imports optional extras: {sorted(leaked)}"
    )


def test_top_level_package_exposes_crud_entry_points() -> None:
    """``import ddigraph`` must expose the documented CRUD entry points.

    Combined with ``test_no_top_level_optional_dep_imports`` above this
    proves the base install can drive the 90% workflow without any
    optional extra. We do not re-import to avoid polluting other tests'
    cached module objects; a clean-process check belongs in a separate
    end-to-end harness.
    """
    ddigraph = importlib.import_module("ddigraph")
    for attr in ("load", "aload", "detect", "bootstrap", "LoadResult"):
        assert hasattr(ddigraph, attr), f"ddigraph.{attr} missing from public API"

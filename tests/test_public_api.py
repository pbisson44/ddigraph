"""Naming-convention guard: enforce public/private boundary across the package.

Step H.1 of the simplification plan promises that ``ddigraph``'s public
surface is unambiguous: every public module declares ``__all__``, no name
in any ``__all__`` starts with ``_``, and no private module (``_*.py``)
is referenced from documentation or demo code. These tests pin those
invariants so a future refactor cannot silently expand the public surface.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src" / "ddigraph"


def _iter_public_modules() -> list[str]:
    """Return importable dotted names for every public ``ddigraph`` module.

    A module is "public" when no path segment starts with ``_`` (other than
    ``__init__.py``). ``__pycache__`` directories are skipped.
    """
    public: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC.parent)
        parts = rel.parts
        if any(part.startswith("__pycache__") for part in parts):
            continue
        if any(
            part.startswith("_") and part != "__init__.py" and not part.startswith("__")
            for part in parts
        ):
            continue
        # Trim trailing ``__init__.py`` to recover the package import path.
        if parts[-1] == "__init__.py":
            mod = ".".join(parts[:-1])
        else:
            mod = ".".join((*parts[:-1], parts[-1].removesuffix(".py")))
        public.append(mod)
    return public


@pytest.mark.parametrize("module_name", _iter_public_modules())
def test_public_module_declares_dunder_all(module_name: str) -> None:
    """Every public module must declare ``__all__``.

    Implicit module surfaces (no ``__all__``) make every imported name
    public by accident. Naming the surface keeps refactors honest.
    """
    module = importlib.import_module(module_name)
    assert hasattr(module, "__all__"), (
        f"public module {module_name!r} is missing an ``__all__`` declaration"
    )
    assert isinstance(module.__all__, (list, tuple)), (
        f"{module_name}.__all__ must be a list or tuple, got {type(module.__all__).__name__}"
    )


@pytest.mark.parametrize("module_name", _iter_public_modules())
def test_no_private_names_in_dunder_all(module_name: str) -> None:
    """Items in ``__all__`` may not start with ``_``.

    A leading underscore signals "internal"; exporting it via ``__all__``
    contradicts that convention.
    """
    module = importlib.import_module(module_name)
    # Dunder names (e.g. ``__version__``) are intentionally exposed and
    # convey package metadata; only single-underscore private names are
    # disallowed in ``__all__``.
    private = [
        name for name in module.__all__ if name.startswith("_") and not name.startswith("__")
    ]
    assert not private, f"{module_name}.__all__ exports private name(s): {private}"


def test_private_modules_are_not_referenced_from_docs_or_demos() -> None:
    """User-facing documentation and demos must not import private modules.

    ``ddigraph.schema._generated`` and ``ddigraph.schema._overrides`` exist
    as internal seams between the XSD generator and the runtime tables;
    external code (docs examples, demo scripts) should consume the public
    re-exports under ``ddigraph.schema.definitions`` instead.

    The ``docs/<lang>/project/`` subtree is exempt: those are
    maintainer-facing design / contributor documents (e.g.
    ``dsl-design.md``) whose whole purpose is to describe the private
    internals by name. The guard targets *user-facing* guides
    (getting-started, user-guide, backends, advanced) where naming a
    private module would mislead an end user into importing it.
    """
    forbidden_substrings = (
        "ddigraph.schema._generated",
        "ddigraph.schema._overrides",
        "ddigraph.ingest._",
    )
    offenders: list[str] = []
    for tree in (_REPO_ROOT / "docs", _REPO_ROOT / "demo"):
        if not tree.exists():
            continue
        for path in tree.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".md"):
                continue
            # Maintainer/project docs may discuss internals by name.
            if "project" in path.relative_to(_REPO_ROOT).parts:
                continue
            text = path.read_text(errors="ignore")
            for needle in forbidden_substrings:
                if needle in text:
                    offenders.append(f"{path.relative_to(_REPO_ROOT)}: imports {needle}")
    assert not offenders, "docs/demo reference private modules: " + "; ".join(offenders)


def test_top_level_dunder_all_includes_crud_surface() -> None:
    """``ddigraph.__all__`` must keep exposing the CRUD API entry points."""
    import ddigraph

    crud = {"load", "aload", "detect", "bootstrap", "abootstrap", "LoadResult"}
    missing = crud - set(ddigraph.__all__)
    assert not missing, f"top-level __all__ dropped CRUD entry points: {missing}"

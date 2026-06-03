"""Helpers for accessing bundled schema and maintenance assets."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_first_existing(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No schema resources found in packaged data or repository checkout.")


def schemas_root() -> Path:
    """Return the directory containing bundled DDI schemas.

    The schemas are force-included in wheels at ``ddigraph/schemas/ddi`` so consumers
    can validate XML against the official XSDs directly from an installed distribution.
    Falls back to the repository checkout when running from source.
    """
    return _find_first_existing(
        PACKAGE_ROOT / "schemas" / "ddi",
        PROJECT_ROOT / "schemas" / "ddi",
    )


def manifest_path() -> Path:
    """Return the path to the bundled schema manifest."""
    return _find_first_existing(
        PACKAGE_ROOT / "schemas" / "manifest.json",
        PROJECT_ROOT / "schemas" / "manifest.json",
    )


def update_schemas_script() -> Path:
    """Return the path to the bundled schema refresh helper script."""
    return _find_first_existing(
        PACKAGE_ROOT / "scripts" / "update_schemas.py",
        PROJECT_ROOT / "scripts" / "update_schemas.py",
    )


__all__ = ["manifest_path", "schemas_root", "update_schemas_script"]

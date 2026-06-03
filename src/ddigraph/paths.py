"""Path utilities shared across CLI and library entrypoints."""

from __future__ import annotations

import os
from pathlib import Path


def validate_readable_xml_path(raw_path: Path | str) -> Path:
    """Ensure a user-supplied path points to a readable XML file.

    Args:
        raw_path: Path-like value supplied by a caller or CLI argument.

    Returns:
        The resolved absolute path for the validated XML file.

    Raises:
        ValueError: If the path does not reference a readable file.
    """
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise ValueError(f"DDI XML path must reference a readable file: {path}")

    has_access = os.access(path, os.R_OK)

    if not has_access:
        raise ValueError(f"DDI XML path must reference a readable file: {path}")

    try:
        with path.open("rb") as file_obj:
            file_obj.read(1)
    except PermissionError as exc:
        raise ValueError(f"DDI XML path must reference a readable file: {path}") from exc
    except OSError as exc:
        raise ValueError(f"DDI XML path must reference a readable file: {path}") from exc

    return Path(os.path.realpath(path))


__all__ = ["validate_readable_xml_path"]

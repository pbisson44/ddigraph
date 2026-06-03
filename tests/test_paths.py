import os
from pathlib import Path

import pytest

from ddigraph.paths import validate_readable_xml_path


def test_validate_readable_xml_path_rejects_unreadable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Paths without user read permission should be rejected."""

    xml_file = tmp_path / "data.xml"
    xml_file.write_text("<root />")
    xml_file.chmod(0)

    monkeypatch.setattr(os, "access", lambda path, mode: False)

    with pytest.raises(ValueError):
        validate_readable_xml_path(xml_file)


def test_validate_readable_xml_path_accepts_windows_readonly_when_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows readonly attribute should still be accepted when file is readable."""

    xml_file = tmp_path / "data.xml"
    xml_file.write_text("<root />")
    expected_path = xml_file.resolve()

    monkeypatch.setattr(os, "access", lambda path, mode: True)

    assert validate_readable_xml_path(xml_file) == expected_path

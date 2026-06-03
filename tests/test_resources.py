from pathlib import Path

import orjson
import pytest

from ddigraph import resources


def test_schema_resources_are_packaged() -> None:
    root = resources.schemas_root()
    assert root.name == "ddi"
    assert (root / "v3_3" / "instance_3_3.xsd").is_file()
    assert resources.manifest_path().is_file()


def test_manifest_path_prefers_packaged_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_manifest = tmp_path / "installed" / "schemas" / "manifest.json"
    package_manifest.parent.mkdir(parents=True)
    package_manifest.write_bytes(orjson.dumps({"source": "installed"}))

    source_manifest = tmp_path / "checkout" / "schemas" / "manifest.json"
    source_manifest.parent.mkdir(parents=True)
    source_manifest.write_bytes(orjson.dumps({"source": "editable"}))

    monkeypatch.setattr(resources, "PACKAGE_ROOT", tmp_path / "installed")
    monkeypatch.setattr(resources, "PROJECT_ROOT", tmp_path / "checkout")

    assert resources.manifest_path() == package_manifest


def test_manifest_path_falls_back_to_project_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_manifest = tmp_path / "checkout" / "schemas" / "manifest.json"
    source_manifest.parent.mkdir(parents=True)
    source_manifest.write_bytes(orjson.dumps({"source": "editable"}))

    monkeypatch.setattr(resources, "PACKAGE_ROOT", tmp_path / "installed")
    monkeypatch.setattr(resources, "PROJECT_ROOT", tmp_path / "checkout")

    assert resources.manifest_path() == source_manifest


def test_update_schemas_script_packaged() -> None:
    script_path = resources.update_schemas_script()
    assert script_path.name == "update_schemas.py"
    assert script_path.is_file()

"""Tests for the CRUD-simple ``ddigraph`` public API.

These tests cover the new top-level entry points added in plan step G:
``ddigraph.load`` / ``ddigraph.aload`` / ``ddigraph.detect`` /
``ddigraph.bootstrap``. The underlying loaders / driver factories are
exercised by their own test modules; here we verify the public surface
shape, the env-driven settings resolution, and the dispatch logic
without touching a real Neo4j instance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import ddigraph
from ddigraph.api import LoadResult, _default_dataset_id, _resolve_settings
from ddigraph.config import Settings

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_public_surface_is_importable() -> None:
    """The CRUD entry points are accessible directly from ``ddigraph``."""
    assert callable(ddigraph.load)
    assert callable(ddigraph.aload)
    assert callable(ddigraph.detect)
    assert callable(ddigraph.bootstrap)
    assert callable(ddigraph.abootstrap)
    assert ddigraph.LoadResult is LoadResult


def test_load_result_dataclass_fields() -> None:
    """``LoadResult`` carries the documented summary fields."""
    result = LoadResult(
        flavor="codebook",
        target="bolt://localhost:7687",
        dataset_id="demo",
        nodes_written=10,
        relationships_written=4,
        duration_s=0.42,
        dry_run=False,
        totals={"Dataset": 1, "Variable": 9, "AccessRelationship": 4},
    )
    assert result.flavor == "codebook"
    assert result.nodes_written == 10
    assert result.relationships_written == 4
    assert result.totals["Variable"] == 9


def test_default_dataset_id_uses_file_stem() -> None:
    """A missing ``dataset_id`` is synthesised from the file stem."""
    assert _default_dataset_id("survey.xml") == "survey"
    assert _default_dataset_id("/path/to/Labour Force Survey.xml") == "Labour_Force_Survey"
    assert _default_dataset_id("/path/to/.xml") == "default"


def test_resolve_settings_honors_target_override() -> None:
    """A non-None ``target`` overrides the settings' ``neo4j_uri``."""
    base = Settings(neo4j_uri="bolt://default:7687")
    resolved, uri = _resolve_settings("bolt://override:7687", base)
    assert uri == "bolt://override:7687"
    assert resolved.neo4j_uri == "bolt://override:7687"
    # The original Settings is left untouched (model_copy is non-mutating).
    assert base.neo4j_uri == "bolt://default:7687"


def test_resolve_settings_falls_back_to_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no target and no settings, env vars drive the URI."""
    monkeypatch.setenv("DDIGRAPH_NEO4J_URI", "bolt://from-env:7687")
    monkeypatch.setenv("DDIGRAPH_NEO4J_USER", "envuser")
    monkeypatch.setenv("DDIGRAPH_NEO4J_PASSWORD", "envpass")
    resolved, uri = _resolve_settings(None, None)
    assert uri == "bolt://from-env:7687"
    assert resolved.neo4j_user == "envuser"


def test_detect_returns_typed_literal() -> None:
    """``detect`` narrows the raw string to a typed ``FlavorName``."""
    codebook_fixture = _FIXTURES / "ddi_codebook_v25.xml"
    if codebook_fixture.exists():
        assert ddigraph.detect(codebook_fixture) == "codebook"

    fragment_fixture = _FIXTURES / "fragment_instance.xml"
    if fragment_fixture.exists():
        assert ddigraph.detect(fragment_fixture) == "lifecycle"


def test_aload_rejects_cdi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CDI documents raise ``NotImplementedError`` from ``aload``.

    DDI-CDI ingestion exists as ``parse_cdi_batches`` but does not yet
    have a Neo4j persistence path the CRUD API can dispatch to.
    """
    cdi_path = tmp_path / "wrapper.xml"
    cdi_path.write_text(
        '<?xml version="1.0"?><Wrapper xmlns="http://ddialliance.org/'
        'Specification/DDI-CDI/1.0/XMLSchema/"></Wrapper>'
    )
    import asyncio

    with pytest.raises(NotImplementedError, match="DDI-CDI"):
        asyncio.run(ddigraph.aload(cdi_path, target="bolt://localhost:7687"))

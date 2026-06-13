"""Tests for entry-point labelling in the DDI-L fragment writer.

A FragmentInstance declares a single TopLevelReference, but a file -- or a graph
accumulated from several files -- can contain many survey roots. The writer marks
every Instrument and StudyUnit as ``EntryPoint`` so all roots are discoverable,
in addition to the file's declared top level.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from neo4j import Driver

from ddigraph.config import Settings
from ddigraph.ingest.fragment_loader import AsyncFragmentGraphWriter, DDIFragmentLoader

# A FragmentInstance that declares a top level (an Instrument survey root) plus
# the matching fragment, so the loader has something to label as an EntryPoint.
_WITH_TOP_LEVEL = """<?xml version="1.0" encoding="UTF-8"?>
<FragmentInstance xmlns="ddi:instance:3_3"
                  xmlns:r="ddi:reusable:3_3"
                  xmlns:d="ddi:datacollection:3_3">
    <TopLevelReference>
        <r:Agency>test.org</r:Agency>
        <r:ID>inst1</r:ID>
        <r:Version>1.0</r:Version>
        <r:TypeOfObject>Instrument</r:TypeOfObject>
    </TopLevelReference>
    <Fragment>
        <d:Instrument id="inst1" agency="test.org" version="1.0">
            <r:Agency>test.org</r:Agency>
            <r:ID>inst1</r:ID>
            <r:Version>1.0</r:Version>
            <r:Label><r:Content>Survey</r:Content></r:Label>
        </d:Instrument>
    </Fragment>
</FragmentInstance>
"""


class _Result:
    def consume(self) -> None:  # pragma: no cover - trivial
        return None


class _RecordingSession:
    def __init__(self, log: list[tuple[str, dict[str, Any]]]) -> None:
        self._log = log

    def __enter__(self) -> _RecordingSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> _Result:
        self._log.append((query, parameters or {}))
        return _Result()


class _RecordingDriver:
    """Minimal sync driver that records the Cypher the writer executes."""

    def __init__(self) -> None:
        self.log: list[tuple[str, dict[str, Any]]] = []

    def session(self, database: str | None = None, **config: Any) -> _RecordingSession:
        return _RecordingSession(self.log)


async def test_mark_entry_points_labels_every_survey_root() -> None:
    driver = _RecordingDriver()
    writer = AsyncFragmentGraphWriter(cast(Driver, driver))

    await writer.mark_entry_points("neo4j")

    queries = [q for q, _ in driver.log]
    assert "MATCH (n:Instrument) SET n:EntryPoint" in queries
    assert "MATCH (n:StudyUnit) SET n:EntryPoint" in queries


async def test_mark_entry_point_matches_by_fragment_id() -> None:
    driver = _RecordingDriver()
    writer = AsyncFragmentGraphWriter(cast(Driver, driver))

    await writer.mark_entry_point("urn:ddi:test.org:abc:1", "neo4j")

    assert driver.log == [
        (
            "MATCH (n {fragment_id: $entry_id}) SET n:EntryPoint",
            {"entry_id": "urn:ddi:test.org:abc:1"},
        )
    ]


async def test_loader_marks_declared_top_level_and_survey_roots(tmp_path: Path) -> None:
    xml_path = tmp_path / "frag.xml"
    xml_path.write_text(_WITH_TOP_LEVEL, encoding="utf-8")

    driver = _RecordingDriver()
    loader = DDIFragmentLoader(cast(Driver, driver), settings=Settings())

    await loader.load(xml_path)

    queries = [q for q, _ in driver.log]
    # The file's declared top level is marked by its version-aware node key...
    assert (
        "MATCH (n {fragment_id: $entry_id}) SET n:EntryPoint",
        {"entry_id": "urn:ddi:test.org:inst1:1.0"},
    ) in driver.log
    # ...and every survey root is labelled too.
    assert "MATCH (n:Instrument) SET n:EntryPoint" in queries
    assert "MATCH (n:StudyUnit) SET n:EntryPoint" in queries

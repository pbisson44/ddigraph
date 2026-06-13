"""Tests for entry-point labelling in the DDI-L fragment writer.

A FragmentInstance declares a single TopLevelReference, but a file -- or a graph
accumulated from several files -- can contain many survey roots. The writer marks
every Instrument and StudyUnit as ``EntryPoint`` so all roots are discoverable,
in addition to the file's declared top level.
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import Driver

from ddigraph.ingest.fragment_loader import AsyncFragmentGraphWriter


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

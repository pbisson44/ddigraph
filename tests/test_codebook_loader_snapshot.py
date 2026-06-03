"""Byte-equality snapshot of the DDI-Codebook loader output.

This test is the safety net for plan step K (the declarative
composition DSL). Before any bespoke ``ingest_*`` handler in
``src/ddigraph/ingest/loader.py`` is migrated to the
``schema_overrides.toml``-driven walker, this test pins the exact
batch records the loader produces for the comprehensive fixture at
``tests/fixtures/codebook_sample.xml``.

Each handler-migration commit must keep this test green: the records
produced after the migration have to be byte-identical to the
committed snapshot in ``tests/fixtures/codebook_loader_snapshot.json``.
Any intended schema change is made by regenerating the snapshot
(``REGEN=1 pytest tests/test_codebook_loader_snapshot.py``) and
reviewing the JSON diff in the same PR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ddigraph.ingest.loader import parse_ddi_batches

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_SAMPLE_XML = _FIXTURES / "codebook_sample.xml"
_SNAPSHOT = _FIXTURES / "codebook_loader_snapshot.json"

# A small chunk size so the fixture produces several batches; this
# exercises the chunk-flush path in addition to the per-handler
# extraction, widening the surface the snapshot pins.
_CHUNK_SIZE = 5


def _capture() -> list[dict[str, object]]:
    """Return every batch the codebook loader produces for the fixture.

    The batches are converted via ``DDIBatch.as_dict`` (the same
    serialisation the graph adapter consumes) so the snapshot reflects
    exactly what downstream code sees.
    """
    batches = list(
        parse_ddi_batches(
            _SAMPLE_XML,
            "snapshot-ds",
            "Snapshot Dataset",
            chunk_size=_CHUNK_SIZE,
        )
    )
    return [batch.as_dict() for batch in batches]


def _normalise(payload: list[dict[str, object]]) -> str:
    """Stable JSON serialisation: sorted keys, fixed indentation."""
    return json.dumps(payload, sort_keys=True, indent=2, default=str)


def test_codebook_loader_output_matches_snapshot() -> None:
    """Loader batches are byte-identical to the committed snapshot.

    Set ``REGEN=1`` in the environment to rewrite the snapshot after an
    intentional schema change; review the resulting JSON diff before
    committing.
    """
    actual = _normalise(_capture())

    if os.environ.get("REGEN") == "1" or not _SNAPSHOT.exists():
        _SNAPSHOT.write_text(actual + "\n", encoding="utf-8")
        if os.environ.get("REGEN") == "1":
            return

    expected = _SNAPSHOT.read_text(encoding="utf-8").rstrip("\n")
    assert actual == expected, (
        "DDI-Codebook loader output drifted from "
        "tests/fixtures/codebook_loader_snapshot.json. If the change is "
        "intentional, regenerate with "
        "``REGEN=1 pytest tests/test_codebook_loader_snapshot.py`` and "
        "review the JSON diff in the same commit."
    )


def test_snapshot_covers_the_bespoke_handlers() -> None:
    """Sanity-check that the fixture actually exercises the Step K handlers.

    If the fixture stops producing variables / studies / questions the
    snapshot would still pass trivially while covering nothing; this
    guard keeps the safety net meaningful.
    """
    batches = _capture()
    merged: dict[str, int] = {}
    for batch in batches:
        for key, value in batch.items():
            if isinstance(value, list):
                merged[key] = merged.get(key, 0) + len(value)

    # The bespoke handlers Step K migrates: variables, studies,
    # questions, question_items, organizations, data_files.
    for collection in (
        "variables",
        "studies",
        "questions",
        "question_items",
        "organizations",
        "data_files",
    ):
        assert merged.get(collection, 0) > 0, (
            f"fixture no longer exercises {collection!r}; the Step K "
            f"snapshot would be vacuous -- extend codebook_sample.xml"
        )

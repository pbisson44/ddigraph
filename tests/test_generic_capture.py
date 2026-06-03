"""Tests for the generic identifiable/entity capture paths.

These paths cover the long-tail of XSD elements that lack a bespoke
record class but still must round-trip through the loader so that every
concrete, non-abstract schema element is retained.

Covered behaviours:

* ``BatchBuilder.ingest_generic_identifiable`` populates
  :class:`ddigraph.ingest.loader.GenericIdentifiableRecord` from DDI-C
  elements carrying the ``GLOBALS`` attribute group.
* ``DDIBatchStream`` skips the in-place ``elem.clear()`` when a generic
  handler fires, so enclosing bespoke handlers (e.g. ``stdyDscr``) can
  still read nested children.
* ``BatchBuilder._count_records`` excludes ``generic_identifiables`` from
  the flush-threshold, keeping chunking semantics stable.
* ``CDIBatchStream`` only processes the XML root element and its direct
  children, preventing nested reusable CDI types (``Identifier``,
  ``ObjectName``, ...) from being ingested / cleared before their
  enclosing entity finishes parsing.
* ``CDIGenericRecord`` captures every DDI-CDI entity beyond the
  hand-tuned record classes via the ``generic_entities`` collection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ddigraph.ingest.cdi_loader import (
    CDIGenericRecord,
    parse_cdi_batches,
)
from ddigraph.ingest.loader import (
    BatchBuilder,
    GenericIdentifiableRecord,
    parse_ddi_batches,
)
from ddigraph.schema.ddi_graph import DDIIngestGraph

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ddi_c_with_generics(tmp_path: Path) -> Path:
    """Codebook document that exercises generic identifiable handlers.

    ``stdyDscr`` is a bespoke handler; ``titlStmt``/``prodStmt``/
    ``rspStmt`` are generic identifiable captures that appear *inside*
    the bespoke parent.  The bespoke handler reads nested text
    (``.//titl``) on its end-event, so the generic captures must not
    wipe the subtree.
    """

    xml = tmp_path / "codebook_generic.xml"
    xml.write_text(
        """
        <codeBook>
            <stdyDscr ID="s1">
                <citation>
                    <titlStmt ID="ts1">
                        <titl>Example Study</titl>
                    </titlStmt>
                    <prodStmt ID="ps1">
                        <producer>Statistics Canada</producer>
                    </prodStmt>
                    <rspStmt ID="rs1">
                        <AuthEnty>Jane Doe</AuthEnty>
                    </rspStmt>
                </citation>
                <stdyInfo ID="si1">
                    <subject ID="subj1">
                        <keyword>economics</keyword>
                    </subject>
                    <sumDscr ID="sd1">
                        <timePrd>2020</timePrd>
                    </sumDscr>
                </stdyInfo>
            </stdyDscr>
        </codeBook>
        """,
        encoding="utf-8",
    )
    return xml


@pytest.fixture
def cdi_with_nested_reusable(tmp_path: Path) -> Path:
    """CDI document with nested ``Identifier``/``ObjectName`` inside an entity.

    If the stream processed nested elements it would ingest the inner
    ``Identifier`` and clear the subtree before ``<Concept>`` finished
    parsing.  Only root-level entities (direct children of ``<Wrapper>``)
    should produce records.
    """

    xml = tmp_path / "cdi_nested.xml"
    xml.write_text(
        """
        <Wrapper xmlns="http://ddi-cdi/1.0">
            <Concept>
                <Identifier><StringValue>concept-001</StringValue></Identifier>
                <ObjectName>Sex</ObjectName>
                <LabelForDisplay>Sex</LabelForDisplay>
            </Concept>
            <Unit>
                <Identifier><StringValue>unit-001</StringValue></Identifier>
                <ObjectName>Person</ObjectName>
            </Unit>
        </Wrapper>
        """,
        encoding="utf-8",
    )
    return xml


# ---------------------------------------------------------------------------
# GenericIdentifiableRecord + DDIBatchStream
# ---------------------------------------------------------------------------


class TestGenericIdentifiableCapture:
    """Generic DDI-Codebook identifiable capture behaviour."""

    def test_generic_elements_produce_records(self, ddi_c_with_generics: Path) -> None:
        """Each generic handler tag yields a GenericIdentifiableRecord."""

        batches = list(parse_ddi_batches(ddi_c_with_generics, "ds1", "Dataset", 500))
        assert len(batches) == 1
        records = batches[0].generic_identifiables
        by_tag: dict[str, GenericIdentifiableRecord] = {r.element_tag: r for r in records}
        assert set(by_tag) >= {
            "titlstmt",
            "prodstmt",
            "rspstmt",
            "stdyinfo",
            "subject",
            "sumdscr",
        }
        assert by_tag["titlstmt"].identifiable_id == "ts1"
        assert by_tag["titlstmt"].dataset_id == "ds1"
        assert by_tag["titlstmt"].dataset_name == "Dataset"

    def test_generic_capture_does_not_block_parent_handler(
        self,
        ddi_c_with_generics: Path,
    ) -> None:
        """Bespoke ``stdyDscr`` handler still reads ``titlStmt/titl`` text.

        If ``DDIBatchStream`` cleared the subtree when the generic
        ``titlStmt`` handler fired, the enclosing Study record's title
        would be lost by the time ``stdyDscr``'s end-event arrives.
        """

        batches = list(parse_ddi_batches(ddi_c_with_generics, "ds1", "Dataset", 500))
        assert len(batches[0].studies) == 1
        assert batches[0].studies[0].title == "Example Study"

    def test_duplicate_generic_elements_are_deduped_by_id(self, tmp_path: Path) -> None:
        """Same element with the same ID yields a single record."""

        xml = tmp_path / "dup.xml"
        xml.write_text(
            """
            <codeBook>
                <titlStmt ID="ts1"><titl>Alpha</titl></titlStmt>
                <titlStmt ID="ts1"><titl>Alpha</titl></titlStmt>
                <titlStmt ID="ts2"><titl>Beta</titl></titlStmt>
            </codeBook>
            """,
            encoding="utf-8",
        )
        batches = list(parse_ddi_batches(xml, "ds1", None, 500))
        tags = [r.identifiable_id for r in batches[0].generic_identifiables]
        assert sorted(tags) == ["ts1", "ts2"]

    def test_generic_elements_get_synthetic_id_when_absent(self, tmp_path: Path) -> None:
        """Element without an ``ID`` still produces a record with a synthetic id."""

        xml = tmp_path / "noid.xml"
        xml.write_text(
            """
            <codeBook>
                <subject><keyword>a</keyword></subject>
                <subject><keyword>b</keyword></subject>
            </codeBook>
            """,
            encoding="utf-8",
        )
        batches = list(parse_ddi_batches(xml, "ds1", None, 500))
        recs = [r for r in batches[0].generic_identifiables if r.element_tag == "subject"]
        assert len(recs) == 2
        assert all(r.identifiable_id.startswith("ds1:subject_") for r in recs)
        # synthetic ids must be unique
        assert len({r.identifiable_id for r in recs}) == 2


# ---------------------------------------------------------------------------
# BatchBuilder._count_records flush semantics
# ---------------------------------------------------------------------------


class TestChunkFlushIgnoresGenerics:
    """Generic identifiables must not drive chunk-flushing.

    Adding broader XSD coverage introduced many auxiliary records per
    document; counting them toward the flush threshold would shrink the
    effective chunk size for existing callers.  This test pins the
    current behaviour: a builder stuffed with only generic records does
    not flush, even well past ``chunk_size``.
    """

    def test_generic_records_alone_never_flush(self) -> None:
        builder = BatchBuilder("ds1", "Dataset", chunk_size=3)
        for i in range(20):
            builder.generic_identifiables.append(
                GenericIdentifiableRecord(
                    dataset_id="ds1",
                    dataset_name="Dataset",
                    identifiable_id=f"id-{i}",
                    element_tag="subject",
                )
            )
        assert builder.flush_if_ready() is None
        # Still flushable at finalize-time so the data isn't lost.
        batch = builder.finalize()
        assert batch is not None
        assert len(batch.generic_identifiables) == 20


# ---------------------------------------------------------------------------
# CDIBatchStream root-only iteration + CDIGenericRecord
# ---------------------------------------------------------------------------


class TestCDIRootOnlyIteration:
    """Nested reusable CDI types must not be ingested as standalone entities."""

    def test_nested_identifier_not_captured_as_separate_entity(
        self,
        cdi_with_nested_reusable: Path,
    ) -> None:
        """Identifiers inside a Concept/Unit are not separately ingested."""

        batches = list(parse_cdi_batches(cdi_with_nested_reusable, chunk_size=500))
        assert len(batches) == 1
        generic_types = {r.entity_type for r in batches[0].generic_entities}
        # ``Unit`` is a generic-entity at root level and must be present;
        # nested ``Identifier`` / ``ObjectName`` / ``LabelForDisplay``
        # inside Concept and Unit must NOT appear as standalone records.
        assert "Unit" in generic_types
        for nested in ("Identifier", "ObjectName", "LabelForDisplay"):
            assert nested not in generic_types, (
                f"{nested} captured as standalone entity; "
                "CDIBatchStream should only process root-level elements"
            )

    def test_top_level_generic_entity_captured(self, cdi_with_nested_reusable: Path) -> None:
        """Root-level generic entities produce CDIGenericRecord instances."""

        batches = list(parse_cdi_batches(cdi_with_nested_reusable, chunk_size=500))
        units = [r for r in batches[0].generic_entities if r.entity_type == "Unit"]
        assert len(units) == 1
        assert isinstance(units[0], CDIGenericRecord)
        assert units[0].cdi_id == "unit-001"

    def test_single_entity_root_preserves_own_identifier(self, tmp_path: Path) -> None:
        """A CDI document whose root is itself an entity ingests the root.

        The root is a single ``<Concept>`` (not a container like
        ``<Wrapper>`` / ``<DDICDIModels>``).  Its children must NOT be
        dispatched — otherwise the nested ``<Identifier>`` would be
        processed and the subtree cleared before the root parser reads
        its own identifier and textual fields.
        """

        xml = tmp_path / "cdi_single_entity_root.xml"
        xml.write_text(
            """
            <Concept xmlns="http://ddi-cdi/1.0">
                <Identifier><StringValue>concept-root-001</StringValue></Identifier>
                <ObjectName>Single Root Concept</ObjectName>
                <LabelForDisplay>Root Concept</LabelForDisplay>
                <Description>Root-level entity document</Description>
            </Concept>
            """,
            encoding="utf-8",
        )
        batches = list(parse_cdi_batches(xml, chunk_size=500))
        assert len(batches) == 1
        concepts = batches[0].concepts
        assert len(concepts) == 1
        assert concepts[0].cdi_id == "concept-root-001"
        assert concepts[0].name == "Single Root Concept"
        # Nested reusable types inside the single-entity root must not
        # be ingested as standalone generic entities.
        generic_types = {r.entity_type for r in batches[0].generic_entities}
        for nested in ("Identifier", "ObjectName", "LabelForDisplay"):
            assert nested not in generic_types


# ---------------------------------------------------------------------------
# DDIIngestGraph mapping for GenericIdentifiableRecord
# ---------------------------------------------------------------------------


class TestGenericIdentifiableGraphMapping:
    """Generic identifiables become first-class graph nodes.

    Without the mapping, ``DDIBatch.generic_identifiables`` would be
    silently dropped when the batch is translated to a graph, because no
    field would exist on :class:`DDIIngestGraph` to receive them.
    """

    def test_generic_identifiable_produces_graph_node(
        self,
        ddi_c_with_generics: Path,
    ) -> None:
        batches = list(parse_ddi_batches(ddi_c_with_generics, "ds1", "Dataset", 500))
        graph = DDIIngestGraph.from_ddi_batch(batches[0])
        generic_nodes = [n for n in graph.nodes() if n.label == "DDIGenericIdentifiable"]
        assert generic_nodes, "No DDIGenericIdentifiable nodes emitted"
        tags = {n.identity["element_tag"] for n in generic_nodes}
        assert {"titlstmt", "prodstmt", "rspstmt", "subject"} <= tags
        for node in generic_nodes:
            assert node.identity["dataset_id"] == "ds1"
            assert "identifiable_id" in node.identity

    def test_generic_identifiable_has_in_dataset_edge(
        self,
        ddi_c_with_generics: Path,
    ) -> None:
        batches = list(parse_ddi_batches(ddi_c_with_generics, "ds1", "Dataset", 500))
        graph = DDIIngestGraph.from_ddi_batch(batches[0])
        generic_edges = [
            r
            for r in graph.relationships()
            if r.type == "IN_DATASET" and r.start.label == "DDIGenericIdentifiable"
        ]
        assert generic_edges, "No IN_DATASET edges for generic identifiables"
        for rel in generic_edges:
            assert rel.end.label == "Dataset"
            assert rel.end.identity["id"] == "ds1"

    def test_generic_identifiables_roundtrip_through_as_dict(
        self,
        ddi_c_with_generics: Path,
    ) -> None:
        batches = list(parse_ddi_batches(ddi_c_with_generics, "ds1", "Dataset", 500))
        graph = DDIIngestGraph.from_ddi_batch(batches[0])
        payload = graph.as_dict()
        assert "generic_identifiables" in payload
        items = payload["generic_identifiables"]
        assert isinstance(items, list) and items

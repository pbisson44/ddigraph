"""Tests for the backend-neutral graph view (``ddigraph.graph.view``).

The view is the single seam every non-Neo4j consumer targets, so these
tests care about two things: that each of the three DDI flavors projects
at all, and that the projection agrees with the parser tier it wraps
rather than quietly dropping records.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ddigraph.graph.view import (
    _CDI_COLLECTION_LABELS,
    _CDI_GENERIC_LABEL,
    GraphChunk,
    _normalise_cdi_label,
    iter_graph,
)
from ddigraph.ingest import loader
from ddigraph.ingest.cdi_loader import _CDI_RELATIONSHIP_MAP
from ddigraph.ingest.fragment_loader import DDIFragmentParser
from ddigraph.ingest.loader import parse_ddi_batches
from ddigraph.schema.ddi_graph import _NODE_MAPPINGS, DDIIngestGraph
from ddigraph.schema.definitions import DDISchema

FIXTURES = Path(__file__).parent / "fixtures"
CODEBOOK = FIXTURES / "codebook_sample.xml"
LIFECYCLE = FIXTURES / "fragment_instance.xml"
REUSABLE = FIXTURES / "reusable_fragments.xml"
CDI = FIXTURES / "cdi_sample.xml"


def _drain(path: Path, **kwargs: object) -> GraphChunk:
    """Collapse the streamed chunks into one for easy assertions."""
    merged = GraphChunk()
    for chunk in iter_graph(path, **kwargs):  # type: ignore[arg-type]
        merged.nodes.extend(chunk.nodes)
        merged.relationships.extend(chunk.relationships)
    return merged


@pytest.mark.parametrize("fixture", [CODEBOOK, LIFECYCLE, REUSABLE, CDI])
def test_every_fixture_projects_nodes_and_relationships(fixture: Path) -> None:
    """All three flavors reach the same Node/Relationship shape."""
    merged = _drain(fixture)

    assert merged.nodes, f"{fixture.name} produced no nodes"
    assert merged.relationships, f"{fixture.name} produced no relationships"
    assert all(node.label for node in merged.nodes)
    assert all(node.identity for node in merged.nodes)


def test_chunks_are_never_empty() -> None:
    """``iter_graph`` filters empty chunks so consumers need no guard."""
    assert all(bool(chunk) for chunk in iter_graph(LIFECYCLE))


def test_lifecycle_relationship_endpoints_carry_real_labels() -> None:
    """Edge endpoints must be labelled, not left as bare keys.

    ``FragmentBatch.relationships`` is ``(from_key, rel_type, to_key)`` with
    no labels attached. The view recovers them from the node-only phase; if
    that bookkeeping breaks, endpoints silently fall back to ``DDIFragment``.
    """
    merged = _drain(LIFECYCLE)
    node_labels = {node.label for node in merged.nodes}

    endpoints = {rel.start.label for rel in merged.relationships}
    endpoints |= {rel.end.label for rel in merged.relationships}

    assert "DDIFragment" not in endpoints
    assert endpoints <= node_labels


def test_lifecycle_node_count_matches_the_parser() -> None:
    """The projection must not add or drop fragments."""
    expected = sum(
        batch.total_fragments() for batch in DDIFragmentParser(LIFECYCLE).parse_batches()
    )

    assert len(_drain(LIFECYCLE).nodes) == expected


def test_codebook_node_count_matches_the_ingest_graph() -> None:
    """The codebook path is a pass-through over ``DDIIngestGraph``."""
    expected = sum(
        len(list(DDIIngestGraph.from_ddi_batch(batch).nodes()))
        for batch in parse_ddi_batches(CODEBOOK, "codebook_sample", None, 200)
    )

    assert len(_drain(CODEBOOK).nodes) == expected


def test_codebook_dataset_id_defaults_to_the_file_stem() -> None:
    """Matches ``ddigraph.load``, which derives the same default."""
    dataset_nodes = [n for n in _drain(CODEBOOK).nodes if n.label == "Dataset"]

    assert dataset_nodes
    assert {n.identity["id"] for n in dataset_nodes} == {"codebook_sample"}


def test_explicit_dataset_id_is_honoured() -> None:
    """An explicit id overrides the stem-derived default."""
    dataset_nodes = [n for n in _drain(CODEBOOK, dataset_id="custom").nodes if n.label == "Dataset"]

    assert {n.identity["id"] for n in dataset_nodes} == {"custom"}


def test_unknown_flavor_is_rejected() -> None:
    """A forced-but-unknown flavor fails loudly rather than yielding nothing."""
    with pytest.raises(ValueError, match="unrecognised DDI flavor"):
        list(iter_graph(LIFECYCLE, flavor="sdmx"))


def test_missing_path_is_rejected(tmp_path: Path) -> None:
    """Path validation happens before any parsing work."""
    with pytest.raises(ValueError, match="readable file"):
        list(iter_graph(tmp_path / "nope.xml"))


def test_cdi_projects_curated_labels_and_association_edges() -> None:
    """DDI-CDI reaches the graph tier for the first time.

    CDI was parse-only: ``api.aload`` raises ``NotImplementedError`` for it
    and no adapter writes it, so nothing downstream could consume a parsed
    CDI file. The view gives it the same Node/Relationship shape as the
    other two flavors.
    """
    merged = _drain(CDI)
    labels = {node.label for node in merged.nodes}
    edges = {(r.start.label, r.type, r.end.label) for r in merged.relationships}

    assert {"CDIConcept", "CDIConceptSystem", "CDICodeList", "CDICode"} <= labels
    assert ("CDIConceptSystem", "HAS_CONCEPT", "CDIConcept") in edges
    assert ("CDICodeList", "HAS_CODE", "CDICode") in edges


def test_cdi_nodes_omit_unset_optional_fields() -> None:
    """``CDIRecord`` carries 13 optional extras; unset ones stay out."""
    concept = next(n for n in _drain(CDI).nodes if n.label == "CDIConcept")

    assert concept.properties["name"] == "Employment Status"
    assert "agent_type" not in concept.properties
    assert None not in concept.properties.values()


def test_every_cdi_endpoint_label_is_one_a_node_can_have() -> None:
    """CDI edge endpoints must name labels ``_cdi_nodes`` actually emits.

    ``_CDI_RELATIONSHIP_MAP`` takes endpoint labels straight from the
    association tag, but the parser collapses many concrete tags into shared
    collections: ``Activity_has_Step`` records ``CDIStep`` while a ``Step``
    entity is emitted as ``CDIActivity``, and tags with no bespoke entry
    become ``CDIGenericEntity``. Without normalisation 102 of the 134
    endpoint labels name nothing that can exist, so a consumer joining on
    ``(label, identity)`` would fabricate a node next to the real one.
    """
    emittable = set(_CDI_COLLECTION_LABELS.values()) | {_CDI_GENERIC_LABEL}

    normalised = set()
    for _rel_type, source, target in _CDI_RELATIONSHIP_MAP.values():
        normalised.add(_normalise_cdi_label(source))
        normalised.add(_normalise_cdi_label(target))

    assert normalised <= emittable, f"unreachable labels: {sorted(normalised - emittable)}"


def test_cdi_label_normalisation_handles_collapsed_and_generic_tags() -> None:
    """The two collapse shapes, pinned by example."""
    # Bespoke tag folded into a shared collection.
    assert _normalise_cdi_label("CDIStep") == "CDIActivity"
    assert _normalise_cdi_label("CDIDescriptorVariable") == "CDIInstanceVariable"
    # No bespoke entry at all -> the generic bucket.
    assert _normalise_cdi_label("CDIParameter") == _CDI_GENERIC_LABEL
    # Already-correct labels survive unchanged.
    assert _normalise_cdi_label("CDIConcept") == "CDIConcept"


def test_cdi_collection_labels_cover_every_curated_cdi_node() -> None:
    """The CDI collection -> label map must stay exhaustive.

    ``CDI_NODES`` is generated from ``schema_overrides.toml``. If a curated
    CDI node type is added there but not here, its records would never reach
    the graph view, and nothing else in the suite would notice.
    """
    assert set(_CDI_COLLECTION_LABELS.values()) == {n.label for n in DDISchema.CDI_NODES}


@pytest.mark.parametrize(
    ("attr", "label", "id_field", "properties"),
    [(m[0], m[1], m[2], m[3]) for m in _NODE_MAPPINGS],
    ids=[m[1] for m in _NODE_MAPPINGS],
)
def test_node_mapping_fields_exist_on_the_record(
    attr: str, label: str, id_field: str, properties: tuple[str, ...]
) -> None:
    """Every ``_NODE_MAPPINGS`` field must exist on its record dataclass.

    ``DDIIngestGraph.nodes()`` reads these names with ``getattr``, so a typo
    is an ``AttributeError`` at parse time rather than a startup failure.
    ``ProcessingEvent`` carried exactly that bug -- an identity field of
    ``event_id`` against a record whose attribute is ``processing_event_id``
    -- and it went unseen because the Neo4j adapter writes through
    ``as_dict()`` and never touches this projection.
    """
    annotation = DDIIngestGraph.__annotations__[attr]
    record_cls = getattr(loader, annotation[annotation.index("[") + 1 : -1])
    names = {f.name for f in dataclasses.fields(record_cls)}

    missing = sorted({id_field, *properties} - names)

    assert not missing, f"{label} maps fields absent from {record_cls.__name__}: {missing}"

"""Round-trip tests: DDI XML -> RDF -> graph view.

These are the tests that make "RDF as an input format" a claim rather than
an aspiration. The strong assertion is triple-level identity: re-exporting
what the reader produced must reproduce the original graph exactly, for
every flavor. Anything weaker -- matching counts, matching labels -- would
pass while silently moving every subject to a different IRI.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ddigraph.exporter import EXTENSIONS, export
from ddigraph.graph.view import iter_graph
from ddigraph.rdf import vocabulary as v
from ddigraph.rdf.reader import EXTENSION_FORMATS, read_graph
from ddigraph.rdf.writer import build_graph

rdflib = pytest.importorskip("rdflib")

FIXTURES = Path(__file__).parent / "fixtures"
ALL_FIXTURES = [
    FIXTURES / "fragment_instance.xml",
    FIXTURES / "codebook_sample.xml",
    FIXTURES / "cdi_sample.xml",
    FIXTURES / "reusable_fragments.xml",
]


def _roundtrip(fixture: Path, tmp_path: Path, fmt: str = "turtle") -> tuple[object, object]:
    """Export, read back, and re-export. Returns both graphs.

    Uses the exporter's own extension for the format, so the reader
    infers the serialisation the same way a user's filename would.
    """
    out = tmp_path / f"out{EXTENSIONS[fmt]}"
    export(fixture, out, format=fmt)
    return build_graph(iter_graph(fixture)), build_graph(read_graph(out))


@pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=lambda p: p.stem)
def test_roundtrip_is_triple_identical(fixture: Path, tmp_path: Path) -> None:
    """The whole point: nothing is lost going out and back."""
    original, reparsed = _roundtrip(fixture, tmp_path)

    assert set(original) == set(reparsed)  # type: ignore[call-overload]


@pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=lambda p: p.stem)
def test_roundtrip_preserves_labels_and_relationship_types(fixture: Path, tmp_path: Path) -> None:
    """Stated separately so a failure says which half broke."""
    out = tmp_path / "out.ttl"
    export(fixture, out, format="turtle")

    original_labels = Counter(n.label for c in iter_graph(fixture) for n in c.nodes)
    reparsed_labels = Counter(n.label for c in read_graph(out) for n in c.nodes)
    original_rels = Counter(r.type for c in iter_graph(fixture) for r in c.relationships)
    reparsed_rels = Counter(r.type for c in read_graph(out) for r in c.relationships)

    assert original_labels == reparsed_labels
    assert original_rels == reparsed_rels


def test_many_to_one_class_alignment_survives() -> None:
    """``disco:Question`` cannot distinguish these; the project type can."""
    assert v.standard_class_iri("Question") == v.standard_class_iri("QuestionItem")
    assert v.label_for_class_iri(v.project_class_iri("QuestionItem")) == "QuestionItem"
    assert v.label_for_class_iri(v.project_class_iri("Question")) == "Question"


def test_ambiguous_predicates_recover_their_relationship_type(tmp_path: Path) -> None:
    """Three published predicates are reached by more than one type.

    ``skos:inScheme`` is the hardest: four relationship types reach it and
    it also reverses the graph's edge direction. Without the project
    companion the reader could not tell ``HAS_CATEGORY`` from ``IN_SCHEME``,
    nor which way the original edge pointed.
    """
    fixture = FIXTURES / "fragment_instance.xml"
    out = tmp_path / "out.ttl"
    export(fixture, out, format="turtle")

    rels = {(r.start.label, r.type, r.end.label) for c in read_graph(out) for r in c.relationships}

    assert ("CodeList", "HAS_CATEGORY", "Category") in rels


def test_companion_triples_are_written_only_where_needed(tmp_path: Path) -> None:
    """Alignment stays lean: 9 of 369 relationship types get a companion."""
    ambiguous = {v.SKOS + "inScheme", v.DISCO + "question", v.DCTERMS + "isPartOf"}

    assert {iri for iri in ambiguous if v.is_ambiguous_predicate(iri)} == ambiguous
    assert not v.is_ambiguous_predicate(v.DISCO + "concept")


@pytest.mark.parametrize("fmt", ["turtle", "ntriples", "jsonld", "rdfxml"])
def test_every_written_format_reads_back(fmt: str, tmp_path: Path) -> None:
    """The reader accepts everything the writer emits."""
    original, reparsed = _roundtrip(FIXTURES / "cdi_sample.xml", tmp_path, fmt)

    assert set(original) == set(reparsed)  # type: ignore[call-overload]


def test_format_is_inferred_from_the_extension(tmp_path: Path) -> None:
    """Callers should not have to repeat what the filename already says."""
    assert EXTENSION_FORMATS[".ttl"] == "turtle"
    assert EXTENSION_FORMATS[".jsonld"] == "json-ld"

    out = tmp_path / "graph.jsonld"
    export(FIXTURES / "cdi_sample.xml", out, format="jsonld")

    assert sum(len(c.nodes) for c in read_graph(out)) > 0


# ---------------------------------------------------------------------------
# Tolerance
# ---------------------------------------------------------------------------


def test_foreign_rdf_yields_nothing_rather_than_nonsense(tmp_path: Path) -> None:
    """A subject with no project type is skipped, not guessed at.

    Pointing the reader at unrelated RDF should produce an empty graph
    rather than inventing labelled nodes out of FOAF or Dublin Core.
    """
    foreign = tmp_path / "foreign.ttl"
    foreign.write_text(
        "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n"
        '<http://example.org/a> a foaf:Person ; foaf:name "Ada" .\n',
        encoding="utf-8",
    )

    chunks = list(read_graph(foreign))

    assert not [n for c in chunks for n in c.nodes]


def test_partial_ddigraph_rdf_reads_the_part_it_understands(tmp_path: Path) -> None:
    """Mixed graphs are common; the ddigraph subject is still recovered."""
    mixed = tmp_path / "mixed.ttl"
    mixed.write_text(
        f"@prefix ddigraph: <{v.DDIGRAPH}> .\n"
        "@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n"
        f'<urn:ddi:x:v1:1.0> a ddigraph:Variable ; ddigraph:fragmentId "urn:ddi:x:v1:1.0" .\n'
        '<http://example.org/a> a foaf:Person ; foaf:name "Ada" .\n',
        encoding="utf-8",
    )

    nodes = [n for c in read_graph(mixed) for n in c.nodes]

    assert [n.label for n in nodes] == ["Variable"]
    assert nodes[0].identity == {"fragment_id": "urn:ddi:x:v1:1.0"}


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    """Fail on the path, not part-way through parsing."""
    with pytest.raises(ValueError, match="readable file"):
        list(read_graph(tmp_path / "nope.ttl"))


def test_chunks_respect_chunk_size(tmp_path: Path) -> None:
    """The reader streams like the parsers it feeds."""
    out = tmp_path / "out.ttl"
    export(FIXTURES / "codebook_sample.xml", out, format="turtle")

    chunks = list(read_graph(out, chunk_size=5))

    assert len(chunks) > 1
    assert all(len(c.nodes) <= 5 and len(c.relationships) <= 5 for c in chunks)


def test_identity_is_recovered_not_guessed(tmp_path: Path) -> None:
    """Codebook identity is not always ``<thing>_id``.

    A ``Concept`` is keyed on ``name``. Deriving the field from the label
    would key it on a ``concept_id`` that does not exist, and every Concept
    would move to a different subject IRI on re-export.
    """
    out = tmp_path / "out.ttl"
    export(FIXTURES / "codebook_sample.xml", out, format="turtle")

    concepts = [n for c in read_graph(out) for n in c.nodes if n.label == "Concept"]

    assert concepts
    assert all(set(n.identity) == {"name"} for n in concepts)


def test_composite_identity_is_recovered_in_full(tmp_path: Path) -> None:
    """``DDIGenericIdentifiable`` is keyed on three fields together."""
    out = tmp_path / "out.ttl"
    export(FIXTURES / "codebook_sample.xml", out, format="turtle")

    generics = [n for c in read_graph(out) for n in c.nodes if n.label == "DDIGenericIdentifiable"]

    assert generics
    assert all(
        set(n.identity) == {"dataset_id", "element_tag", "identifiable_id"} for n in generics
    )

"""Tests for the RDF writer and the ``ddigraph export`` command.

The golden file follows the repo's existing snapshot convention (see
``tests/fixtures/codebook_loader_snapshot.json`` and the ``REGEN=1`` habit
documented in ``docs/en/project/dsl-design.md``). Regenerate with:

    REGEN=1 .venv/bin/python -m pytest tests/test_rdf_export.py

and review the diff in the same commit as the change that caused it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ddigraph import exporter as export_mod
from ddigraph.exporter import FORMATS, RDF_FORMATS, export
from ddigraph.graph.view import iter_graph
from ddigraph.rdf import vocabulary as v
from ddigraph.rdf.writer import build_graph

if TYPE_CHECKING:
    from rdflib import Graph as RDFGraph

# Skips the whole module on a base install; rdflib ships in the dev extra,
# so CI always has it.
rdflib = pytest.importorskip("rdflib")

FIXTURES = Path(__file__).parent / "fixtures"
LIFECYCLE = FIXTURES / "fragment_instance.xml"
CODEBOOK = FIXTURES / "codebook_sample.xml"
CDI = FIXTURES / "cdi_sample.xml"
GOLDEN = FIXTURES / "rdf_export_snapshot.ttl"


def _graph(path: Path, **kwargs: object) -> RDFGraph:
    return build_graph(iter_graph(path), **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Golden file
# ---------------------------------------------------------------------------


def test_turtle_output_matches_the_snapshot() -> None:
    """Byte-equality guard over the whole serialisation.

    Any change to the vocabulary, the literal typing, or the triple layout
    shows up here as a reviewable diff rather than as a silent change in
    what consumers receive.
    """
    graph = _graph(LIFECYCLE)
    actual = graph.serialize(format="turtle")

    if os.environ.get("REGEN"):
        GOLDEN.write_text(actual, encoding="utf-8")
        pytest.skip("regenerated rdf_export_snapshot.ttl")

    assert GOLDEN.exists(), "run REGEN=1 pytest tests/test_rdf_export.py to create the snapshot"
    assert actual == GOLDEN.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Vocabulary conformance of real output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI])
def test_output_declares_exactly_one_project_namespace(fixture: Path) -> None:
    """The failure this release exists to fix: four competing namespaces."""
    serialized = _graph(fixture).serialize(format="turtle")
    ddi_namespaces = {
        line.split("<")[1].split(">")[0]
        for line in serialized.splitlines()
        if line.startswith("@prefix") and "ddigraph" in line
    }

    assert ddi_namespaces == {v.DDIGRAPH}
    assert "ddialliance.org/ontology" not in serialized
    assert "example.org" not in serialized


@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI])
def test_no_predicate_is_a_neo4j_relationship_name(fixture: Path) -> None:
    """``ddi:USES_CODELIST`` leaking into predicate space was the old bug."""
    for _s, predicate, _o in _graph(fixture):
        local = str(predicate).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        assert "_" not in local, f"{predicate} leaks a raw relationship name"
        assert not local.isupper()


@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI])
def test_every_subject_carries_a_project_type(fixture: Path) -> None:
    """Round-tripping depends on it, so it must never be omitted."""
    graph = _graph(fixture)
    rdf_type = rdflib.URIRef(v.RDF + "type")

    for subject in set(graph.subjects()):
        types = {str(o) for o in graph.objects(subject, rdf_type)}
        assert any(t.startswith(v.DDIGRAPH) for t in types), f"{subject} has no project type"


def test_aligned_nodes_carry_both_types() -> None:
    """Standard class for interop, project class for identity."""
    graph = _graph(LIFECYCLE)
    rdf_type = rdflib.URIRef(v.RDF + "type")

    categories = set(graph.subjects(rdf_type, rdflib.URIRef(v.SKOS + "Concept")))
    assert categories

    for subject in categories:
        types = {str(o) for o in graph.objects(subject, rdf_type)}
        assert v.SKOS + "Concept" in types
        assert v.DDIGRAPH + "Category" in types


# ---------------------------------------------------------------------------
# SKOS
# ---------------------------------------------------------------------------


def test_code_lists_are_concept_schemes_with_members_pointing_in() -> None:
    """SKOS models scheme membership from the member's side.

    The graph edge runs ``CodeList -HAS_CATEGORY-> Category``. Emitting that
    verbatim would give a ``skos:ConceptScheme`` a ``skos:member``, which
    belongs to ``skos:Collection``. The writer inverts it.
    """
    graph = _graph(LIFECYCLE)
    in_scheme = rdflib.URIRef(v.SKOS + "inScheme")
    rdf_type = rdflib.URIRef(v.RDF + "type")

    pairs = list(graph.subject_objects(in_scheme))
    assert pairs, "expected at least one skos:inScheme triple"

    for concept, scheme in pairs:
        assert (concept, rdf_type, rdflib.URIRef(v.SKOS + "Concept")) in graph
        assert (scheme, rdf_type, rdflib.URIRef(v.SKOS + "ConceptScheme")) in graph

    assert not list(graph.subject_objects(rdflib.URIRef(v.SKOS + "member")))


def test_skos_subjects_use_skos_labelling_predicates() -> None:
    """A concept must not be labelled with ``rdfs:label``."""
    graph = _graph(LIFECYCLE)
    rdf_type = rdflib.URIRef(v.RDF + "type")
    rdfs_label = rdflib.URIRef(v.RDFS + "label")

    for concept in graph.subjects(rdf_type, rdflib.URIRef(v.SKOS + "Concept")):
        assert (concept, rdflib.URIRef(v.SKOS + "prefLabel"), None) in graph
        assert (concept, rdfs_label, None) not in graph


# ---------------------------------------------------------------------------
# IRI minting
# ---------------------------------------------------------------------------


def test_relationship_endpoints_resolve_to_real_subjects() -> None:
    """Endpoint stubs carry no properties, so IRIs must not depend on them.

    If minting used ``properties["urn"]`` the full node and the endpoint
    would land on different IRIs and every edge would point at an empty
    subject.
    """
    for fixture in (LIFECYCLE, CODEBOOK, CDI):
        graph = _graph(fixture)
        described = set(graph.subjects())
        rdf_type = rdflib.URIRef(v.RDF + "type")

        for _s, predicate, obj in graph:
            if predicate != rdf_type and isinstance(obj, rdflib.URIRef):
                assert obj in described, f"{fixture.name}: {obj} is referenced but never described"


def test_lifecycle_subjects_keep_the_ddi_urn_intact() -> None:
    """``demo/load_rdf.py`` flattened colons and destroyed the URN."""
    subjects = {str(s) for s in _graph(LIFECYCLE).subjects()}

    assert any(s.startswith("urn:ddi:") for s in subjects)
    assert not any("urn_ddi_" in s for s in subjects)


def test_base_uri_is_applied_to_records_without_a_urn() -> None:
    """Publishers supply their own namespace."""
    subjects = {str(s) for s in _graph(CODEBOOK, base="https://example.net/id/").subjects()}

    assert any(s.startswith("https://example.net/id/") for s in subjects)


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------


def test_booleans_are_not_typed_as_integers() -> None:
    """``bool`` subclasses ``int``, so the natural isinstance order is wrong."""
    from ddigraph.rdf.writer import _literal

    assert _literal(True, "flag", None).datatype == rdflib.URIRef(v.XSD + "boolean")
    assert _literal(3, "count", None).datatype == rdflib.URIRef(v.XSD + "integer")


def test_language_becomes_a_tag_rather_than_a_predicate() -> None:
    """A language field describes the other literals, not the subject."""
    from ddigraph.rdf.writer import _literal

    tagged = _literal("Bonjour", "label", "fr")
    untagged = _literal("code-1", "name", None)

    assert tagged.language == "fr"
    assert untagged.language is None


def test_a_category_carrying_a_language_is_tagged_end_to_end() -> None:
    """The whole point of the language field, exercised through the writer.

    ``_literal`` is unit-tested above, but nothing proved a real SKOS
    category comes out tagged: no fixture in the repo declares ``xml:lang``,
    so every category the suite exports is an untagged literal and the path
    that matters was never run.
    """
    from ddigraph.graph.view import GraphChunk
    from ddigraph.schema.ddi_graph import Node

    graph = build_graph(
        [
            GraphChunk(
                [
                    Node(
                        "Category",
                        {"category_id": "c1"},
                        {"label": "Moins de 18 ans", "language": "fr-CA", "code": "1"},
                    )
                ],
                [],
            )
        ]
    )

    skos = rdflib.Namespace(v.SKOS)
    subject = next(iter(graph.subjects(rdflib.RDF.type, skos.Concept)))
    pref_label = next(iter(graph.objects(subject, skos.prefLabel)))
    notation = next(iter(graph.objects(subject, skos.notation)))

    assert isinstance(pref_label, rdflib.Literal)
    assert pref_label.language == "fr-CA"
    # ``code`` is a notation, not prose: tagging it would claim the symbol
    # itself is French.
    assert isinstance(notation, rdflib.Literal)
    assert notation.language is None


def test_a_category_without_a_language_is_not_given_one() -> None:
    """Absent metadata stays absent. Defaulting to ``@en`` would invent it.

    Every fixture in this repo is in this position, which is why the
    exported categories carry plain literals.
    """
    from ddigraph.graph.view import GraphChunk
    from ddigraph.schema.ddi_graph import Node

    graph = build_graph(
        [GraphChunk([Node("Category", {"category_id": "c1"}, {"label": "Under 18"})], [])]
    )

    skos = rdflib.Namespace(v.SKOS)
    subject = next(iter(graph.subjects(rdflib.RDF.type, skos.Concept)))
    pref_label = next(iter(graph.objects(subject, skos.prefLabel)))

    assert isinstance(pref_label, rdflib.Literal)
    assert pref_label.language is None


# ---------------------------------------------------------------------------
# Export command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", sorted(RDF_FORMATS))
def test_every_rdf_format_round_trips_through_rdflib(fmt: str, tmp_path: Path) -> None:
    """What we write must parse back with the same triple count."""
    out = tmp_path / f"out{fmt}"
    result = export(LIFECYCLE, out, format=fmt)

    reparsed = rdflib.Graph().parse(str(out), format=RDF_FORMATS[fmt])

    assert result.triples == len(reparsed)


def test_json_export_carries_a_summary(tmp_path: Path) -> None:
    """The JSON shape is a graph, not a rectangle."""
    out = tmp_path / "graph.json"
    result = export(CODEBOOK, out, format="json")

    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["summary"]["nodes"] == result.nodes
    assert payload["summary"]["relationships"] == result.relationships
    assert payload["nodes"] and payload["relationships"]


def test_csv_export_writes_a_directory_of_two_files(tmp_path: Path) -> None:
    """A graph does not fit one rectangle, so CSV gets two."""
    out = tmp_path / "csvout"
    result = export(CDI, out, format="csv")

    assert (out / "nodes.csv").exists()
    assert (out / "relationships.csv").exists()
    assert result.format == "csv"


@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI])
def test_export_works_for_every_flavor(fixture: Path, tmp_path: Path) -> None:
    """The point of the graph view: one exporter, three input formats."""
    result = export(fixture, tmp_path / "out.ttl", format="turtle")

    assert result.nodes > 0
    assert result.triples is not None and result.triples > 0


def test_unknown_format_is_rejected(tmp_path: Path) -> None:
    """Fail on the argument, not part-way through writing."""
    with pytest.raises(ValueError, match="Unknown export format"):
        export(LIFECYCLE, tmp_path / "out.xyz", format="yaml")


def test_missing_rdflib_gives_an_actionable_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RDF formats need an extra; say which one."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "rdflib":
            raise ImportError("no rdflib")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError, match=r"ddigraph\[rdf\]"):
        export(LIFECYCLE, tmp_path / "out.ttl", format="turtle")


def test_plain_formats_need_no_optional_extra() -> None:
    """JSON and CSV must work on a base install."""
    assert set(export_mod.PLAIN_FORMATS) == {"json", "csv"}
    assert set(FORMATS) == set(RDF_FORMATS) | set(export_mod.PLAIN_FORMATS)

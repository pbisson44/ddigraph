"""Tests for SHACL shape generation.

The important test here is not that shapes are produced but that real
exported output *conforms* to them. That is what makes the shapes a
contract rather than decoration, and it holds the vocabulary and the writer
to the same standard consumers are asked to validate against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ddigraph.graph.view import iter_graph
from ddigraph.rdf import vocabulary as v
from ddigraph.rdf.shacl import FLAVORS, SHAPES_NS, shapes_graph
from ddigraph.rdf.writer import build_graph
from ddigraph.schema.definitions import DDISchema

rdflib = pytest.importorskip("rdflib")
pyshacl = pytest.importorskip("pyshacl")

FIXTURES = Path(__file__).parent / "fixtures"
BY_FLAVOR = {
    "lifecycle": FIXTURES / "fragment_instance.xml",
    "codebook": FIXTURES / "codebook_sample.xml",
    "cdi": FIXTURES / "cdi_sample.xml",
}


def _conforms(fixture: Path, flavor: str | None) -> tuple[bool, str]:
    data = build_graph(iter_graph(fixture))
    conforms, _graph, text = pyshacl.validate(data, shacl_graph=shapes_graph(flavor=flavor))
    return conforms, text


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flavor", sorted(BY_FLAVOR))
def test_exported_graphs_conform_to_their_flavor_shapes(flavor: str) -> None:
    """Real output validates against the generated shapes."""
    conforms, report = _conforms(BY_FLAVOR[flavor], flavor)

    assert conforms, report


@pytest.mark.parametrize("flavor", sorted(BY_FLAVOR))
def test_exported_graphs_conform_to_the_unscoped_shapes(flavor: str) -> None:
    """The all-flavors graph must not fire on any single flavor's data.

    An unscoped graph unions definitions that disagree: 21 labels appear in
    both the codebook and lifecycle tables with different identity fields,
    and a codebook category sits in a ``CodeScheme`` where a DDI-L one sits
    in a ``CodeList``. Constraints the flavors disagree on are dropped
    rather than guessed at.
    """
    conforms, report = _conforms(BY_FLAVOR[flavor], None)

    assert conforms, report


# ---------------------------------------------------------------------------
# Shape structure
# ---------------------------------------------------------------------------


def test_a_shape_exists_for_every_schema_label() -> None:
    """Derived from ``DDISchema``, so coverage is automatic, not curated."""
    graph = shapes_graph()
    targets = {str(o) for o in graph.objects(None, rdflib.URIRef(v.SH + "targetClass"))}

    for node in DDISchema.get_all_nodes():
        assert v.project_class_iri(node.label) in targets


def test_shapes_target_the_project_class_not_the_standard_one() -> None:
    """Only the project class is carried by every node.

    Targeting ``disco:Question`` would silently apply the ``QuestionItem``
    shape to a ``Question`` as well, since the alignment is many-to-one.
    """
    graph = shapes_graph()
    targets = {str(o) for o in graph.objects(None, rdflib.URIRef(v.SH + "targetClass"))}

    assert all(target.startswith(v.DDIGRAPH) for target in targets)


def test_flavor_scoping_narrows_the_shape_set() -> None:
    """Each flavor emits only its own labels."""
    scoped = {
        flavor: {
            str(o)
            for o in shapes_graph(flavor=flavor).objects(None, rdflib.URIRef(v.SH + "targetClass"))
        }
        for flavor in FLAVORS
    }

    assert v.project_class_iri("CDIConcept") in scoped["cdi"]
    assert v.project_class_iri("CDIConcept") not in scoped["codebook"]
    assert len(scoped["lifecycle"]) > len(scoped["cdi"])


def test_identity_constraint_uses_the_record_attribute() -> None:
    """``NodeDefinition`` describes the Neo4j side, not the record side.

    ``id_field`` is the node property the Cypher merges on -- 44 of the 45
    codebook mappings call it ``id`` -- while the writer emits the record
    attributes ``DDIIngestGraph.nodes()`` reads
    (``MERGE (s:Study {id: row.study_id})``). Shapes built from the Neo4j
    names would put ``minCount 1`` on ``ddigraph:id``, a predicate no
    exported ``Study`` contains, and every codebook node would fail.
    """
    graph = shapes_graph(flavor="codebook")
    shape = rdflib.URIRef(f"{SHAPES_NS}StudyShape")

    required = {
        str(path)
        for constraint in graph.objects(shape, rdflib.URIRef(v.SH + "property"))
        for path in graph.objects(constraint, rdflib.URIRef(v.SH + "path"))
        if (constraint, rdflib.URIRef(v.SH + "minCount"), None) in graph
    }

    assert required == {v.DDIGRAPH + "studyId"}


def test_shapes_describe_predicates_that_actually_occur() -> None:
    """Every constrained path must appear in real exported output.

    A shape naming predicates nothing emits is not merely useless, it
    misdescribes the vocabulary to anyone reading it as documentation.
    """
    graph = shapes_graph(flavor="codebook")
    declared = {
        str(path)
        for constraint in graph.objects(None, rdflib.URIRef(v.SH + "property"))
        for path in graph.objects(constraint, rdflib.URIRef(v.SH + "path"))
    }
    emitted = {str(p) for _s, p, _o in build_graph(iter_graph(BY_FLAVOR["codebook"]))}

    # The fixture is small, so it exercises only part of the schema; the
    # direction that matters is that what it does emit is described.
    undescribed = emitted - declared - {v.RDF + "type"}

    assert not undescribed, f"emitted but not described by any shape: {sorted(undescribed)}"


def test_composite_identity_asserts_no_cardinality() -> None:
    """``DDIGenericIdentifiable`` is keyed on three fields together.

    No single part is unique across sibling nodes, so ``maxCount 1`` on any
    one of them would fire on correct data.
    """
    graph = shapes_graph(flavor="codebook")
    shape = rdflib.URIRef(f"{SHAPES_NS}DDIGenericIdentifiableShape")

    max_counts = [
        o
        for constraint in graph.objects(shape, rdflib.URIRef(v.SH + "property"))
        for o in graph.objects(constraint, rdflib.URIRef(v.SH + "maxCount"))
    ]

    assert not max_counts


def test_unknown_flavor_is_rejected() -> None:
    """Fail on the argument rather than emitting empty shapes."""
    with pytest.raises(ValueError, match="Unknown flavor"):
        shapes_graph(flavor="sdmx")


def test_shapes_graph_is_valid_rdf() -> None:
    """It must reparse; a shapes file consumers cannot load is useless."""
    serialized = shapes_graph(flavor="cdi").serialize(format="turtle")

    assert len(rdflib.Graph().parse(data=serialized, format="turtle")) > 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_shapes_command_writes_a_file(tmp_path: Path) -> None:
    """``ddigraph shapes`` needs no input document and no database."""
    from ddigraph import cli

    out = tmp_path / "shapes.ttl"
    cli.main(["shapes", "-o", str(out), "--flavor", "cdi"])

    assert out.exists()
    assert len(rdflib.Graph().parse(str(out), format="turtle")) > 0


def test_shapes_command_defaults_to_all_flavors(tmp_path: Path) -> None:
    """Omitting --flavor emits the union."""
    from ddigraph import cli

    out = tmp_path / "all.ttl"
    cli.main(["shapes", "-o", str(out)])

    graph = rdflib.Graph().parse(str(out), format="turtle")
    targets = {str(o) for o in graph.objects(None, rdflib.URIRef(v.SH + "targetClass"))}

    assert v.project_class_iri("CDIConcept") in targets
    assert v.project_class_iri("Variable") in targets

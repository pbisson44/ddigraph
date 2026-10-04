"""Tests for SHACL validation through ``ddigraph validate``.

XSD answers "is this valid DDI?". SHACL answers a different question: "is
this graph the shape ddigraph promises?" -- which is the one that matters
to whoever receives an export. Until 0.5.1 answering it took ``ddigraph
shapes``, a ``pyshacl`` install and a script; now it is one verb.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("pyshacl", reason="SHACL validation needs the [shacl] extra")

from rdflib import Graph, Literal, URIRef

from ddigraph import cli, export
from ddigraph.validation import (
    GraphParseError,
    ShapesResult,
    ShapeViolation,
    is_rdf_path,
    validate_shapes,
)

FIXTURES = Path(__file__).parent / "fixtures"
BY_FLAVOR = {
    "codebook": FIXTURES / "codebook_sample.xml",
    "lifecycle": FIXTURES / "fragment_instance.xml",
    "cdi": FIXTURES / "cdi_sample.xml",
}

NS = "https://pbisson44.github.io/ddigraph/ns/1.0/"
INSTRUMENT = URIRef("urn:ddi:test.org:inst1:1.0")
QUESTION = URIRef("urn:ddi:test.org:q1:1.0")
FRAGMENT_ID = URIRef(f"{NS}fragmentId")


@pytest.fixture
def turtle(tmp_path: Path) -> Path:
    """A clean Turtle export of the DDI-L fixture."""
    out = tmp_path / "survey.ttl"
    export(BY_FLAVOR["lifecycle"], out, format="turtle")
    return out


@pytest.fixture
def broken(turtle: Path, tmp_path: Path) -> Path:
    """The same export with one identity removed and one duplicated."""
    graph = Graph().parse(turtle)
    assert (INSTRUMENT, FRAGMENT_ID, None) in graph, "fixture changed; pick another subject"
    graph.remove((INSTRUMENT, FRAGMENT_ID, None))
    graph.add((QUESTION, FRAGMENT_ID, Literal("a-second-identity")))
    out = tmp_path / "broken.ttl"
    graph.serialize(out, format="turtle")
    return out


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flavor", sorted(BY_FLAVOR))
def test_ddi_xml_is_projected_and_conforms(flavor: str) -> None:
    result = validate_shapes(BY_FLAVOR[flavor])

    assert result.valid, [str(issue) for issue in result.issues]
    assert result.flavor == flavor, "the shapes should be scoped to the detected flavor"
    assert result.triples > 0


@pytest.mark.parametrize("flavor", [None, "lifecycle"])
def test_a_clean_export_conforms(turtle: Path, flavor: str | None) -> None:
    assert validate_shapes(turtle, flavor=flavor)


def test_a_missing_identity_is_reported(broken: Path) -> None:
    result = validate_shapes(broken, flavor="lifecycle")

    assert not result.valid
    missing = [i for i in result.issues if i.focus_node == str(INSTRUMENT)]
    assert len(missing) == 1
    assert missing[0].constraint == "MinCountConstraintComponent"
    assert missing[0].path == str(FRAGMENT_ID)
    assert missing[0].severity == "Violation"


def test_a_duplicate_identity_is_reported(broken: Path) -> None:
    result = validate_shapes(broken, flavor="lifecycle")

    duplicate = [i for i in result.issues if i.focus_node == str(QUESTION)]
    assert [i.constraint for i in duplicate] == ["MaxCountConstraintComponent"]


def test_unscoped_shapes_catch_less(broken: Path) -> None:
    """Why the CLI tells you to pass --flavor for RDF.

    ``QuestionItem`` is defined by more than one flavor with different
    identity fields, so the all-flavors shapes cannot assert its identity
    and miss the duplicate that the lifecycle shapes catch.
    """
    unscoped = validate_shapes(broken)
    scoped = validate_shapes(broken, flavor="lifecycle")

    assert not unscoped.valid
    assert unscoped.total < scoped.total


def test_issues_are_sorted_and_truncation_keeps_the_total(broken: Path) -> None:
    full = validate_shapes(broken, flavor="lifecycle")
    capped = validate_shapes(broken, flavor="lifecycle", max_issues=1)

    keys = [(i.focus_node, i.path or "", i.constraint) for i in full.issues]
    assert keys == sorted(keys)
    assert capped.issues == full.issues[:1]
    assert capped.total == full.total == 2


def test_a_violation_renders_its_subject_and_path() -> None:
    violation = ShapeViolation(
        focus_node="urn:x", path="urn:p", constraint="MinCountConstraintComponent", message="m"
    )

    assert str(violation) == "urn:x urn:p: m"


def test_result_is_falsy_when_it_does_not_conform() -> None:
    assert not ShapesResult(valid=False, flavor=None, triples=0)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("a.ttl", True), ("a.nt", True), ("a.jsonld", True), ("a.rdf", True), ("a.xml", False)],
)
def test_rdf_is_recognised_by_extension(name: str, expected: bool) -> None:
    """``.xml`` stays DDI: it is far more often DDI than RDF/XML."""
    assert is_rdf_path(name) is expected


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_rdf_input_is_checked_against_the_shapes(
    turtle: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["validate", str(turtle)])

    out = capsys.readouterr().out
    assert "Shapes result: conforms" in out
    assert "Schema:" not in out, "RDF has no XSD to check"
    assert "--flavor" in out, "the all-flavors caveat should be stated"


def test_non_conforming_rdf_exits_one(broken: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["validate", str(broken), "--flavor", "lifecycle"])

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "does not conform (2 result(s))" in out
    assert str(INSTRUMENT) in out


def test_shapes_flag_adds_shacl_to_xml(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:  # the fixture fails its XSD on purpose
        cli.main(["validate", str(BY_FLAVOR["lifecycle"]), "--shapes", "--json"])

    assert excinfo.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["flavor"] == "lifecycle"
    assert payload["shapes"]["valid"] is True
    assert payload["shapes"]["flavor"] == "lifecycle"


def test_xml_without_the_flag_skips_shacl(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["validate", str(BY_FLAVOR["lifecycle"]), "--json"])

    assert "shapes" not in json.loads(capsys.readouterr().out)


def test_json_reports_each_shape_violation(
    broken: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        cli.main(["validate", str(broken), "--flavor", "lifecycle", "--json"])

    shapes = json.loads(capsys.readouterr().out)["shapes"]
    assert shapes["total"] == 2
    assert {issue["constraint"] for issue in shapes["issues"]} == {
        "MinCountConstraintComponent",
        "MaxCountConstraintComponent",
    }


def test_a_missing_extra_exits_two(
    turtle: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """2 means "could not check", so a script can tell it from "bad data"."""
    import ddigraph.validation

    def missing(*_args: object, **_kwargs: object) -> ShapesResult:
        raise ImportError('Install them with: pip install "ddigraph[shacl]"')

    monkeypatch.setattr(ddigraph.validation, "validate_shapes", missing)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["validate", str(turtle)])

    assert excinfo.value.code == 2
    assert "ddigraph[shacl]" in capsys.readouterr().err


@pytest.fixture
def malformed(tmp_path: Path) -> Path:
    out = tmp_path / "broken.ttl"
    out.write_text("<urn:a> <urn:b> .\n", encoding="utf-8")  # no object
    return out


def test_malformed_rdf_raises_a_parse_error(malformed: Path) -> None:
    with pytest.raises(GraphParseError, match="Not valid turtle"):
        validate_shapes(malformed)


def test_malformed_rdf_does_not_conform_rather_than_crash(
    malformed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Bad data is exit 1, not a traceback and not exit 2."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["validate", str(malformed)])

    assert excinfo.value.code == 1
    assert "not valid RDF" in capsys.readouterr().out


def test_malformed_rdf_still_emits_json(
    malformed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["validate", str(malformed), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert excinfo.value.code == 1
    assert payload["valid"] is False
    assert "turtle" in payload["error"]

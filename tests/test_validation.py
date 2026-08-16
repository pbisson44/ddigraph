"""Tests for XSD validation.

The package has shipped the official DDI schemas since long before this
module existed, but only the build-time codegen ever read them. These tests
cover the gap that closed: asking whether a file is actually valid DDI.

Two things here are easy to mistake for bugs and are not. The upstream
DDI-Codebook 2.6 schema is itself invalid XSD and has to be repaired before
it will load. And every pre-existing fixture in this directory fails
validation, because they are synthetic files written to exercise the
parsers rather than to conform.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ddigraph.validation import (
    XS,
    SchemaUnavailableError,
    ValidationResult,
    _repair_codebook_annotations,
    schema_path,
    validate,
)

FIXTURES = Path(__file__).parent / "fixtures"
LIFECYCLE = FIXTURES / "fragment_instance.xml"
CODEBOOK = FIXTURES / "codebook_sample.xml"
CDI = FIXTURES / "cdi_sample.xml"
VALID_CDI = FIXTURES / "cdi_valid_minimal.xml"


# ---------------------------------------------------------------------------
# Picking the schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flavor", "version", "expected"),
    [
        ("codebook", None, "codebook.xsd"),
        ("lifecycle", "3_1", "instance_3_1.xsd"),
        ("lifecycle", "3_2", "instance_3_2.xsd"),
        ("lifecycle", "3_3", "instance_3_3.xsd"),
        ("cdi", None, "ddi-cdi.xsd"),
    ],
)
def test_each_flavor_resolves_to_its_schema(
    flavor: str, version: str | None, expected: str
) -> None:
    """Each flavor and DDI-L version maps to the right entry-point XSD."""
    assert schema_path(flavor, version).name == expected


def test_all_referenced_schemas_are_actually_bundled() -> None:
    """The mapping is only useful if the files ship with the package."""
    for flavor, version in [
        ("codebook", None),
        ("lifecycle", "3_1"),
        ("lifecycle", "3_2"),
        ("lifecycle", "3_3"),
        ("cdi", None),
    ]:
        assert schema_path(flavor, version).is_file()


def test_an_unknown_flavor_is_refused_by_name() -> None:
    """Better a clear error than a mysterious parse failure later."""
    with pytest.raises(SchemaUnavailableError, match="No bundled schema"):
        schema_path("sdmx")


def test_lifecycle_version_comes_from_the_document() -> None:
    """DDI-L declares its version in the namespace; use it, do not guess."""
    assert validate(LIFECYCLE).version == "3_3"


def test_only_lifecycle_carries_a_version() -> None:
    """Codebook and CDI ship one schema each, so a version would be noise."""
    assert validate(CDI).version is None


# ---------------------------------------------------------------------------
# The upstream Codebook schema defect
# ---------------------------------------------------------------------------


def test_the_upstream_codebook_schema_is_invalid_xsd() -> None:
    """Pin the reason the repair exists, so nobody deletes it as dead code.

    ``schemas/ddi-c/codebook.xsd`` puts ``xs:annotation`` after
    ``xs:simpleType`` inside ``xs:attribute`` in 55 places. XSD requires
    ``(annotation?, simpleType?)``. This is upstream -- the file's checksum
    matches ``schemas/manifest.json`` -- so it is what the DDI Alliance
    published, not a packaging accident.

    If a future schema refresh fixes it upstream, this test fails and the
    repair can go.
    """
    from lxml import etree

    tree = etree.parse(str(schema_path("codebook")))

    misordered = [
        attribute
        for attribute in tree.iter(f"{XS}attribute")
        if (annotation := attribute.find(f"{XS}annotation")) is not None
        and list(attribute).index(annotation) != 0
    ]

    assert len(misordered) == 55

    with pytest.raises(etree.XMLSchemaParseError):
        etree.XMLSchema(tree)


def test_the_repair_makes_the_codebook_schema_load() -> None:
    """And the repaired schema compiles, which is the whole point."""
    from lxml import etree

    tree = etree.parse(str(schema_path("codebook")))
    moved = _repair_codebook_annotations(tree)

    assert moved == 55
    assert etree.XMLSchema(tree) is not None


def test_the_repair_only_moves_annotations() -> None:
    """It must not change what the schema says, only the element order.

    ``xs:annotation`` is documentation. Moving it is safe precisely because
    nothing else depends on it -- but that is a claim worth testing rather
    than asserting in a comment.
    """
    from lxml import etree

    tree = etree.parse(str(schema_path("codebook")))
    before = sorted(
        (etree.QName(element).localname, element.get("name") or "")
        for element in tree.iter()
        if isinstance(element.tag, str)
    )

    _repair_codebook_annotations(tree)

    after = sorted(
        (etree.QName(element).localname, element.get("name") or "")
        for element in tree.iter()
        if isinstance(element.tag, str)
    )

    assert before == after


def test_the_repair_is_not_written_back_to_disk() -> None:
    """The file must stay byte-identical to upstream, or the manifest breaks."""
    import hashlib
    import json

    from ddigraph.resources import manifest_path

    validate(CODEBOOK)  # compiles and repairs the schema in memory

    manifest = json.loads(manifest_path().read_text(encoding="utf-8"))
    expected = manifest["ddi-c"]["files"]["codebook.xsd"]
    actual = hashlib.sha256(schema_path("codebook").read_bytes()).hexdigest()

    assert actual == expected


# ---------------------------------------------------------------------------
# Validating documents
# ---------------------------------------------------------------------------


def test_a_conforming_document_passes() -> None:
    """A validator only ever tested on bad input proves nothing."""
    result = validate(VALID_CDI)

    assert result.valid
    assert result.issues == []
    assert bool(result) is True


@pytest.mark.parametrize("fixture", [LIFECYCLE, CODEBOOK, CDI], ids=lambda p: p.stem)
def test_the_synthetic_fixtures_do_not_conform(fixture: Path) -> None:
    """Documents the reason validation is opt-in rather than automatic.

    These files parse and load perfectly well. They are not conformant DDI,
    and neither is a good deal of what real archives publish. Validating by
    default would refuse work that currently succeeds.
    """
    result = validate(fixture)

    assert not result.valid
    assert result.issues


def test_issues_carry_a_line_number() -> None:
    """A bare "invalid" is not actionable; "invalid at line 8" is."""
    issues = validate(LIFECYCLE).issues

    assert issues[0].line > 0
    assert str(issues[0]).startswith(f"line {issues[0].line}:")


def test_max_issues_bounds_the_report() -> None:
    """A badly mismatched file can produce thousands of them."""
    assert len(validate(LIFECYCLE, max_issues=2).issues) == 2


def test_zero_max_issues_keeps_everything() -> None:
    """``0`` means unbounded, matching ``--limit`` elsewhere in the CLI."""
    assert len(validate(LIFECYCLE, max_issues=0).issues) >= 3


def test_flavor_can_be_forced() -> None:
    """Detection reads the root element; sometimes you know better."""
    result = validate(CDI, flavor="cdi")

    assert result.flavor == "cdi"


def test_the_schema_used_is_reported() -> None:
    """You cannot argue with a verdict that will not say what it checked."""
    result = validate(LIFECYCLE)

    assert result.schema.name == "instance_3_3.xsd"
    assert result.schema.is_file()


def test_compiling_a_schema_is_cached() -> None:
    """Compiling costs up to a second; a loop over files must not pay it twice."""
    from ddigraph.validation import _compiled_schema

    _compiled_schema.cache_clear()
    validate(CDI)
    validate(VALID_CDI)

    info = _compiled_schema.cache_info()
    assert info.hits >= 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_validate_command_exits_zero_on_a_valid_file() -> None:
    """So it drops into a shell pipeline or a CI step without glue."""
    from ddigraph import cli

    cli.main(["validate", str(VALID_CDI)])


def test_validate_command_exits_one_on_an_invalid_file() -> None:
    """A non-zero exit is the only part a CI step actually reads."""
    from ddigraph import cli

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["validate", str(LIFECYCLE)])

    assert excinfo.value.code == 1


def test_validate_command_reports_the_violations(capsys: pytest.CaptureFixture[str]) -> None:
    """Naming the file and the schema makes the verdict checkable."""
    from ddigraph import cli

    with pytest.raises(SystemExit):
        cli.main(["validate", str(LIFECYCLE), "--max-issues", "2"])

    out = capsys.readouterr().out
    assert "instance_3_3.xsd" in out
    assert "lifecycle 3.3" in out
    assert out.count("line ") == 2


def test_validate_command_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    """For anything that has to consume the result rather than read it."""
    import json

    from ddigraph import cli

    with pytest.raises(SystemExit):
        cli.main(["validate", str(LIFECYCLE), "--json", "--max-issues", "1"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert payload["flavor"] == "lifecycle"
    assert len(payload["issues"]) == 1


def test_load_and_export_take_validate_but_do_not_default_to_it() -> None:
    """Opt-in is the whole design decision; pin it."""
    from ddigraph import cli

    parser = cli.build_parser()

    for argv in (["load", str(LIFECYCLE)], ["export", str(LIFECYCLE), "-o", "out.ttl"]):
        assert parser.parse_args(argv).validate is False
        assert parser.parse_args([*argv, "--validate"]).validate is True


def test_validate_flag_stops_export_before_it_writes(tmp_path: Path) -> None:
    """Refusing after writing the file would defeat the point."""
    from ddigraph import cli

    out = tmp_path / "out.ttl"
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["export", str(LIFECYCLE), "-o", str(out), "--validate"])

    assert "does not conform" in str(excinfo.value)
    assert not out.exists()


def test_result_is_falsy_when_invalid() -> None:
    """``if not validate(path):`` should read the way it looks."""
    assert not ValidationResult(valid=False, flavor="cdi", schema=Path("x.xsd"))

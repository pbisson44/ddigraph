"""Tests for version-aware identity in the DDI-L fragment parser.

DDI identity is agency + id + version (the URN). Two fragments that share an id
but differ in version are distinct objects, so they must become distinct nodes,
and a reference that names a specific version must resolve to that version. The
parser keys nodes on a version-aware ``fragment_id`` (URN-based) while preserving
the bare DDI id as ``ddi_id``. Genuine duplicates (same id *and* version) are
still collapsed, with a warning.
"""

from __future__ import annotations

from pathlib import Path

from ddigraph.ingest.fragment_loader import DDIFragmentParser, make_node_key

# Two Category fragments sharing id ``cat-dup`` (versions 3 and 4), each
# referenced by a separate CodeList -- mirroring the real Ireland LFS anomaly.
_TWO_VERSIONS = """<?xml version="1.0" encoding="UTF-8"?>
<FragmentInstance xmlns="ddi:instance:3_3"
                  xmlns:r="ddi:reusable:3_3"
                  xmlns:l="ddi:logicalproduct:3_3">
    <Fragment>
        <l:CodeList id="cl1" agency="test.org" version="1.0">
            <r:Agency>test.org</r:Agency>
            <r:ID>cl1</r:ID>
            <r:Version>1.0</r:Version>
            <r:Label><r:Content>List A</r:Content></r:Label>
            <l:Code>
                <r:CategoryReference>
                    <r:Agency>test.org</r:Agency>
                    <r:ID>cat-dup</r:ID>
                    <r:Version>3</r:Version>
                    <r:TypeOfObject>Category</r:TypeOfObject>
                </r:CategoryReference>
            </l:Code>
        </l:CodeList>
    </Fragment>
    <Fragment>
        <l:CodeList id="cl2" agency="test.org" version="1.0">
            <r:Agency>test.org</r:Agency>
            <r:ID>cl2</r:ID>
            <r:Version>1.0</r:Version>
            <r:Label><r:Content>List B</r:Content></r:Label>
            <l:Code>
                <r:CategoryReference>
                    <r:Agency>test.org</r:Agency>
                    <r:ID>cat-dup</r:ID>
                    <r:Version>4</r:Version>
                    <r:TypeOfObject>Category</r:TypeOfObject>
                </r:CategoryReference>
            </l:Code>
        </l:CodeList>
    </Fragment>
    <Fragment>
        <l:Category id="cat-dup" agency="test.org" version="3">
            <r:Agency>test.org</r:Agency>
            <r:ID>cat-dup</r:ID>
            <r:Version>3</r:Version>
            <r:Label><r:Content>C6</r:Content></r:Label>
        </l:Category>
    </Fragment>
    <Fragment>
        <l:Category id="cat-dup" agency="test.org" version="4">
            <r:Agency>test.org</r:Agency>
            <r:ID>cat-dup</r:ID>
            <r:Version>4</r:Version>
            <r:Label><r:Content>C7</r:Content></r:Label>
        </l:Category>
    </Fragment>
</FragmentInstance>
"""

# Same id *and* version twice -> a genuine duplicate that should be collapsed.
_TRUE_DUPLICATE = """<?xml version="1.0" encoding="UTF-8"?>
<FragmentInstance xmlns="ddi:instance:3_3"
                  xmlns:r="ddi:reusable:3_3"
                  xmlns:l="ddi:logicalproduct:3_3">
    <Fragment>
        <l:Category id="cat-x" agency="test.org" version="1">
            <r:Agency>test.org</r:Agency><r:ID>cat-x</r:ID><r:Version>1</r:Version>
            <r:Label><r:Content>X</r:Content></r:Label>
        </l:Category>
    </Fragment>
    <Fragment>
        <l:Category id="cat-x" agency="test.org" version="1">
            <r:Agency>test.org</r:Agency><r:ID>cat-x</r:ID><r:Version>1</r:Version>
            <r:Label><r:Content>X</r:Content></r:Label>
        </l:Category>
    </Fragment>
</FragmentInstance>
"""


def _parse(
    tmp_path: Path, xml: str
) -> tuple[list[dict[str, object]], list[tuple[str, str, str]], DDIFragmentParser]:
    xml_path = tmp_path / "frag.xml"
    xml_path.write_text(xml, encoding="utf-8")
    parser = DDIFragmentParser(xml_path)

    nodes: list[dict[str, object]] = []
    relationships: list[tuple[str, str, str]] = []
    for batch in parser.parse_batches():
        for fragments in batch.fragments_by_type.values():
            nodes.extend(f.to_dict() for f in fragments)
        relationships.extend(batch.relationships)
    return nodes, relationships, parser


def test_distinct_versions_are_kept_as_distinct_nodes(tmp_path: Path) -> None:
    nodes, _relationships, parser = _parse(tmp_path, _TWO_VERSIONS)

    cat_nodes = [n for n in nodes if n.get("ddi_id") == "cat-dup"]
    # Both versions survive as separate nodes.
    assert len(cat_nodes) == 2
    assert {n["version"] for n in cat_nodes} == {"3", "4"}
    # Their node keys (fragment_id) are version-distinct URNs.
    assert {n["fragment_id"] for n in cat_nodes} == {
        "urn:ddi:test.org:cat-dup:3",
        "urn:ddi:test.org:cat-dup:4",
    }
    # No genuine (id+version) duplicates were collapsed here.
    assert parser._duplicate_fragment_count == 0


def test_references_resolve_to_the_correct_version(tmp_path: Path) -> None:
    _nodes, relationships, _parser = _parse(tmp_path, _TWO_VERSIONS)

    has_category = {(r[0], r[2]) for r in relationships if r[1] == "HAS_CATEGORY"}
    # cl1 referenced version 3, cl2 referenced version 4 -- each resolves to its
    # own version rather than collapsing onto one node.
    assert has_category == {
        ("urn:ddi:test.org:cl1:1.0", "urn:ddi:test.org:cat-dup:3"),
        ("urn:ddi:test.org:cl2:1.0", "urn:ddi:test.org:cat-dup:4"),
    }


def test_true_duplicate_same_id_and_version_is_collapsed(tmp_path: Path) -> None:
    nodes, _relationships, parser = _parse(tmp_path, _TRUE_DUPLICATE)

    assert len([n for n in nodes if n.get("ddi_id") == "cat-x"]) == 1
    assert parser._duplicate_fragment_count == 1


def test_make_node_key_prefers_urn_then_composes_then_falls_back() -> None:
    assert make_node_key("a", "id1", "2", urn="urn:ddi:a:id1:2") == "urn:ddi:a:id1:2"
    assert make_node_key("a", "id1", "2") == "urn:ddi:a:id1:2"
    assert make_node_key(None, "id1", None) == "id1"

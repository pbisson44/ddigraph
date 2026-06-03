"""Unit tests for the codebook composition selector primitives.

These pin the behaviour of every function in
``ddigraph.ingest._compose`` against small synthetic ``lxml``
fixtures. The primitives are a faithful facade over the loader's
existing helpers; these tests document the contract the TOML walker
and the recursive-handler rewrites depend on (plan step K).
"""

from __future__ import annotations

from lxml import etree

from ddigraph.ingest import _compose as compose


def _el(xml: str) -> etree._Element:
    """Parse a fragment string into an element."""
    return etree.fromstring(xml)


def test_text_returns_first_match_or_none() -> None:
    elem = _el("<var><labl>Age</labl><labl>Second</labl></var>")
    assert compose.text(elem, "labl") == "Age"
    assert compose.text(elem, "missing") is None


def test_text_any_tries_each_path() -> None:
    elem = _el("<q><qstnText>Hi</qstnText></q>")
    assert compose.text_any(elem, "qstnLit", "qstnText", "labl") == "Hi"
    assert compose.text_any(elem, "nope", "alsono") is None


def test_text_local_is_namespace_insensitive() -> None:
    elem = _el('<r xmlns:l="ddi:logicalproduct:3_3"><l:Label>X</l:Label></r>')
    assert compose.text_local(elem, "Label") == "X"
    assert compose.text_local(None, "Label") is None


def test_text_or_none_reads_direct_text() -> None:
    assert compose.text_or_none(_el("<u>Adults 18+</u>")) == "Adults 18+"
    assert compose.text_or_none(_el("<u></u>")) is None
    assert compose.text_or_none(None) is None


def test_attr_with_fallbacks() -> None:
    elem = _el('<location FILEID="f1" />')
    assert compose.attr(elem, "fileid", "FILEID") == "f1"
    assert compose.attr(elem, "fileid") is None
    assert compose.attr(None, "fileid") is None
    direct = _el('<location fileid="f2" />')
    assert compose.attr(direct, "fileid", "FILEID") == "f2"


def test_count_direct_children_only() -> None:
    elem = _el("<var><catgry/><catgry/><other><catgry/></other></var>")
    # findall with a bare tag matches direct children only.
    assert compose.count(elem, "catgry") == 2
    assert compose.count(elem, "missing") == 0


def test_metadata_pulls_attributes_and_reusable() -> None:
    elem = _el('<var agency="NSO" version="1.0" URN="urn:ddi:v1"><labl>A</labl></var>')
    md = compose.metadata(elem)
    assert md["agency"] == "NSO"
    assert md["version"] == "1.0"
    assert md["urn"] == "urn:ddi:v1"
    # reusable_* keys are always present (None when absent).
    assert "reusable_urn" in md
    assert compose.metadata(None)["agency"] is None


def test_textual_collects_label_and_description() -> None:
    elem = _el("<var><labl>Age</labl><Description>The age</Description></var>")
    tx = compose.textual(elem)
    assert tx["label"] == "Age"
    assert tx["description"] == "The age"
    blank = compose.textual(None)
    assert set(blank) == {"name", "label", "description", "rationale", "language"}
    assert all(v is None for v in blank.values())


def test_question_text_fallback_chain() -> None:
    assert compose.question_text(_el("<qstn><qstnLit>Q?</qstnLit></qstn>")) == "Q?"
    assert compose.question_text(_el("<qstn><labl>Fallback</labl></qstn>")) == "Fallback"
    assert compose.question_text(None) is None


def test_identifier_resolution_and_default() -> None:
    assert compose.identifier(_el('<var ID="v1" />')) == "v1"
    assert compose.identifier(_el("<var />"), default="fallback") == "fallback"


def test_refs_by_suffix_collects_reference_targets() -> None:
    elem = _el(
        '<construct xmlns:r="ddi:reusable:3_3">'
        "<ControlConstructReference><r:ID>cc1</r:ID></ControlConstructReference>"
        "<ControlConstructReference><r:ID>cc2</r:ID></ControlConstructReference>"
        "</construct>"
    )
    refs = compose.refs_by_suffix(elem, "ControlConstructReference")
    assert refs == ["cc1", "cc2"]
    assert compose.refs_by_suffix(_el("<x/>"), "Reference") == []


def test_truncate_caps_length_and_passes_none() -> None:
    assert compose.truncate("abcdef", 3) == "abc"
    assert compose.truncate("ab", 5) == "ab"
    assert compose.truncate(None, 5) is None


def test_child_texts_collects_shallow_text_across_paths() -> None:
    elem = _el(
        "<grp>"
        "<nCubeRef> n1 </nCubeRef><nCubeRef></nCubeRef>"
        "<ncubeRef>n2</ncubeRef>"
        "<other>skip</other>"
        "</grp>"
    )
    assert compose.child_texts(elem, ".//nCubeRef", ".//ncubeRef") == ["n1", "n2"]
    assert compose.child_texts(_el("<x/>"), ".//nCubeRef") == []


def test_primitives_match_loader_helpers_exactly() -> None:
    """The facade must not drift from the loader helpers it wraps.

    A direct equality check on a representative element guarantees the
    snapshot test cannot be defeated by ``_compose`` quietly diverging.
    """
    from ddigraph.ingest import loader

    elem = _el(
        '<var ID="v1" agency="NSO" version="1.0">'
        "<labl>Age</labl><concept>Demographics</concept>"
        "</var>"
    )
    assert compose.text(elem, "labl") == loader._first_text(elem, "labl")
    assert compose.metadata(elem) == loader._common_metadata(elem)
    assert compose.textual(elem) == loader._textual_metadata(elem)
    assert compose.identifier(elem) == loader._get_identifier(elem)

"""Tests for the XSD-driven CDI schema generator output.

Verifies that ``src/ddigraph/schema/_generated/cdi.py`` (produced by
``scripts/generate_schema_definitions.py``) is a structural superset of
the hand-written CDI literals currently consumed by the runtime. This is
the bridge that lets a later commit collapse ``cdi_loader.py`` onto the
generated tables without losing coverage of any tag the runtime relies on.

When this test fails:

* If the message says a current tag is missing from the generated output,
  the bundled XSD has changed and the runtime literal references an
  element that no longer exists. Reconcile the XSD/literal pair.
* If the message says a current label maps to a different XSD source/
  target, the runtime literal disagrees with the XSD; investigate before
  bumping the generator.
"""

from __future__ import annotations

from ddigraph.ingest.cdi_loader import _CDI_RELATIONSHIP_MAP, _CDI_TAG_MAP
from ddigraph.schema._generated.cdi import (
    CDI_GENERATED_ASSOCIATIONS,
    CDI_GENERATED_ENTITIES,
)
from ddigraph.schema.definitions import DDISchema

# DDI* framing wrappers (e.g. DDICDIModels) are XML root containers, not
# graph entities. They appear in the loader's tag map for parsing but not
# in the XSD entity list, so they are excluded from this coverage check.
_FRAMING_TAGS: frozenset[str] = frozenset({"DDICDIModels"})


def test_every_runtime_cdi_label_has_an_xsd_entity() -> None:
    """Every ``CDINode.label`` in ``DDISchema.CDI_NODES`` must map to an XSD entity.

    The runtime label drops the ``CDI`` prefix; e.g. ``CDIConcept`` ↔
    ``Concept`` in the XSD.
    """
    generated = set(CDI_GENERATED_ENTITIES)
    missing = sorted(
        node.label.removeprefix("CDI")
        for node in DDISchema.CDI_NODES
        if node.label.removeprefix("CDI") not in generated
    )
    assert not missing, f"runtime CDI labels missing from generated XSD entities: {missing}"


def test_every_runtime_tag_map_key_has_an_xsd_entity() -> None:
    """Every parser tag in ``_CDI_TAG_MAP`` must exist as an XSD entity.

    DDI framing tags (``DDICDIModels``) are excluded.
    """
    generated = set(CDI_GENERATED_ENTITIES)
    missing = sorted(
        tag for tag in _CDI_TAG_MAP if tag not in generated and tag not in _FRAMING_TAGS
    )
    assert not missing, f"runtime CDI tag-map keys missing from generated XSD entities: {missing}"


def test_every_runtime_association_exists_in_generated() -> None:
    """Every association in ``_CDI_RELATIONSHIP_MAP`` must exist in the generated set.

    The check matches on the XSD ``<source>_<verb>_<target>`` element name
    (the dict key in ``_CDI_RELATIONSHIP_MAP``) and on the source/target
    labels (after stripping the ``CDI`` prefix).
    """
    generated_by_tag = {assoc.tag: assoc for assoc in CDI_GENERATED_ASSOCIATIONS}

    missing_tags: list[str] = []
    label_mismatches: list[str] = []
    for tag, (_, source_label, target_label) in _CDI_RELATIONSHIP_MAP.items():
        assoc = generated_by_tag.get(tag)
        if assoc is None:
            missing_tags.append(tag)
            continue
        expected_source = source_label.removeprefix("CDI")
        expected_target = target_label.removeprefix("CDI")
        if assoc.source != expected_source or assoc.target != expected_target:
            label_mismatches.append(
                f"{tag}: runtime says {expected_source}->{expected_target}, "
                f"XSD says {assoc.source}->{assoc.target}"
            )

    assert not missing_tags, f"runtime associations missing from generated XSD set: {missing_tags}"
    assert not label_mismatches, "runtime/XSD label disagreement: " + "; ".join(label_mismatches)


def test_runtime_relationship_coverage_is_complete() -> None:
    """The runtime relationship map covers every XSD-declared association.

    Plan step C wired ``_CDI_RELATIONSHIP_MAP`` through
    ``cdi_relationships()`` in ``schema/_overrides/_loader.py``. Every
    XSD ``<Source>_<verb>_<Target>`` element now produces a graph
    relationship; the "silently-dropped relationships" gap is closed.
    If this regresses (runtime < generated), step C has been undone.
    """
    runtime = len(_CDI_RELATIONSHIP_MAP)
    generated = len(CDI_GENERATED_ASSOCIATIONS)
    assert runtime == generated, (
        f"runtime CDI relationship coverage is no longer complete; "
        f"runtime={runtime}, generated={generated}"
    )

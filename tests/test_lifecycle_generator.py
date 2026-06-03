"""Tests for the XSD-driven DDI-L lifecycle schema generator output.

Verifies that ``src/ddigraph/schema/_generated/lifecycle.py`` (produced by
``scripts/generate_schema_definitions.py``) is a structural superset of
the hand-written DDI-L literals currently consumed by the runtime. This
bridge lets a later commit collapse ``fragment_loader.py`` and
``DDIFragmentParser`` onto the generated tables without losing coverage
of any tag the runtime relies on.
"""

from __future__ import annotations

from ddigraph.schema._generated.lifecycle import (
    FRAGMENT_GENERATED_ENTITIES,
    FRAGMENT_GENERATED_REFERENCES,
)
from ddigraph.schema.definitions import DDISchema

# Runtime labels and reference keys that diverge from the XSDs. These
# are the items the override file (``schema_overrides.toml``) will
# carry once Step B lands. Each entry needs a short justification:
#
# * ``Collection``: declared in ``archive.xsd`` but its ``CollectionType``
#   does not extend Maintainable / Versionable / Identifiable. The runtime
#   treats it as an honorary identifiable.
# * ``DevelopmentActivity``: declared as ``abstract="true"`` in the XSD
#   (a substitution-group head); the runtime persists it anyway.
# * ``ExternalURLReference``: synthetic edge the runtime emits for typed
#   external references that have no dedicated XSD element.
_RUNTIME_ONLY_IDENTIFIABLES: frozenset[str] = frozenset({"Collection", "DevelopmentActivity"})
_RUNTIME_ONLY_REFERENCES: frozenset[str] = frozenset({"ExternalURLReference"})


def test_every_runtime_fragment_label_has_an_xsd_identifiable() -> None:
    """Every ``FragmentNode.label`` must map to a concrete XSD identifiable.

    Runtime labels are the bare element name (e.g. ``"Concept"``,
    ``"Variable"``, ``"StudyUnit"``) and must each appear in the
    XSD-derived list, except for the small documented allow-list of
    runtime-only identifiables.
    """
    generated = {entity.name for entity in FRAGMENT_GENERATED_ENTITIES}
    missing = sorted(
        node.label
        for node in DDISchema.FRAGMENT_NODES
        if node.label not in generated and node.label not in _RUNTIME_ONLY_IDENTIFIABLES
    )
    assert not missing, (
        f"runtime FRAGMENT_NODES labels missing from generated XSD entities: {missing}"
    )


def test_every_runtime_reference_type_exists_in_generated() -> None:
    """Every key in ``FRAGMENT_RELATIONSHIP_TYPES`` must be an XSD reference element.

    Exception: a small allow-list of runtime-only references documented
    in ``_RUNTIME_ONLY_REFERENCES`` is carried via overrides.
    """
    generated = {ref.tag for ref in FRAGMENT_GENERATED_REFERENCES}
    runtime_keys = set(DDISchema.FRAGMENT_RELATIONSHIP_TYPES)
    missing = sorted(
        tag for tag in runtime_keys if tag not in generated and tag not in _RUNTIME_ONLY_REFERENCES
    )
    assert not missing, (
        f"runtime FRAGMENT_RELATIONSHIP_TYPES keys missing from generated XSD references: {missing}"
    )


def test_identifiable_kind_classification_is_consistent() -> None:
    """No XSD element should appear under more than one identifiable kind."""
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for entity in FRAGMENT_GENERATED_ENTITIES:
        previous = seen.get(entity.name)
        if previous is not None and previous != entity.kind:
            duplicates.append(f"{entity.name}: {previous} vs {entity.kind}")
        seen[entity.name] = entity.kind
    assert not duplicates, f"identifiable kind disagreement: {duplicates}"


def test_runtime_reference_coverage_is_complete() -> None:
    """The runtime relationship map covers every XSD-declared ``*Reference``.

    Plan step D wired ``FRAGMENT_RELATIONSHIP_TYPES`` through
    ``fragment_relationships()`` in ``schema/_overrides/_loader.py``.
    Every XSD-declared ``*Reference`` element now produces a runtime
    rel_type; the previous 64/282 gap is closed.

    The runtime dict can be one entry larger than the XSD set thanks to
    the synthetic ``ExternalURLReference`` runtime edge documented in
    the override file.
    """
    runtime = set(DDISchema.FRAGMENT_RELATIONSHIP_TYPES)
    generated = {ref.tag for ref in FRAGMENT_GENERATED_REFERENCES}
    missing = sorted(generated - runtime)
    assert not missing, f"runtime dropped XSD-declared references: {missing}"

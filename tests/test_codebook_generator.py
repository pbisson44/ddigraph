"""Tests for the XSD-driven DDI-Codebook schema generator output.

Verifies that ``src/ddigraph/schema/_generated/codebook.py`` (produced by
``scripts/generate_schema_definitions.py``) is a structural superset of
every DDI-Codebook lowercase tag the runtime ``DDILoader`` dispatches on.
This bridge lets a later commit replace the hand-rolled
``_GENERIC_IDENTIFIABLE_TAGS`` frozenset and the ``ingest_*`` lookup
table in ``ingest/loader.py`` with a generated mapping.
"""

from __future__ import annotations

import re
from pathlib import Path

from ddigraph.schema._generated.codebook import CODEBOOK_GENERATED_ELEMENTS

# CALS table / XHTML presentation markup. These elements appear in
# the XSD because the codebook spec lets data files include arbitrary
# tabular renderings, but they are not graph-relevant. The runtime
# loader does not register them either.
_LAYOUT_TAGS: frozenset[str] = frozenset(
    {element.tag for element in CODEBOOK_GENERATED_ELEMENTS if element.is_layout}
)


def _runtime_codebook_tag_keys() -> set[str]:
    """Return the lowercase tag keys dispatched by ``ingest/loader.py``.

    Mirrors the regex used by ``scripts/xsd_coverage.py`` so this test
    sees the same dispatch surface the audit script sees: bespoke
    ``"tag": lambda`` handler literals plus the generic codebook tags
    routed through the ``_GENERIC_IDENTIFIABLE_TAGS`` fallback.
    """
    from ddigraph.ingest.loader import _GENERIC_IDENTIFIABLE_TAGS

    src = (
        Path(__file__).resolve().parent.parent / "src" / "ddigraph" / "ingest" / "loader.py"
    ).read_text()
    bespoke = {m.lower() for m in re.findall(r'"([a-zA-Z][a-zA-Z0-9]+)"\s*:\s*lambda\b', src)}
    return bespoke | {tag.lower() for tag in _GENERIC_IDENTIFIABLE_TAGS}


def test_every_xsd_in_scope_codebook_element_is_dispatched_by_loader() -> None:
    """Every non-layout XSD codebook element must be reachable from the loader.

    The runtime maps DDI-L and DDI-CDI tags in addition to codebook
    tags, so the loader set is a superset of the XSD codebook set --
    we assert ``in-scope XSD elements ⊆ loader keys``.
    """
    runtime = _runtime_codebook_tag_keys()
    in_scope_xsd = {element.tag for element in CODEBOOK_GENERATED_ELEMENTS if not element.is_layout}
    missing = sorted(in_scope_xsd - runtime)
    assert not missing, f"in-scope XSD codebook elements not dispatched by loader: {missing}"


def test_layout_elements_are_not_dispatched_by_loader() -> None:
    """Layout-only elements (row, table, tbody, ...) must not be in the dispatch map.

    Catches the regression of accidentally adding a CALS table tag to
    the codebook dispatch table.
    """
    runtime = _runtime_codebook_tag_keys()
    leaked = sorted(_LAYOUT_TAGS & runtime)
    assert not leaked, f"layout-only XSD tags leaked into loader dispatch: {leaked}"


def test_layout_set_matches_xsd_coverage_audit() -> None:
    """The generator's layout-exclusion config must equal the audit script's.

    Both ``scripts/generate_schema_definitions.py:_DDI_C_LAYOUT_EXCLUDES``
    and ``scripts/xsd_coverage.py:DDI_C_LAYOUT_EXCLUDES`` are *config*
    sets driving the GLOBALS walker. They must stay identical until
    ``schema_overrides.toml`` (Step B) becomes the single source of
    truth. Some entries in the config (e.g. ``entry``) never appear in
    the generated output because their XSD type does not inherit
    GLOBALS, so this test compares the config sets directly rather
    than what materially gets emitted.
    """
    import sys

    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "scripts"))
    try:
        from generate_schema_definitions import (
            _DDI_C_LAYOUT_EXCLUDES as generator_excludes,
        )
        from xsd_coverage import DDI_C_LAYOUT_EXCLUDES as audit_excludes
    finally:
        sys.path.pop(0)
    assert set(generator_excludes) == set(audit_excludes), (
        f"generator layout config ({sorted(generator_excludes)}) "
        f"diverged from xsd_coverage.py ({sorted(audit_excludes)})"
    )


def test_generated_element_count_is_stable() -> None:
    """Sanity-check element counts so XSD swaps surface immediately.

    The DDI-C 2.6 XSD bundled in ``schemas/ddi-c`` declares 83 elements
    with GLOBALS; 10 of those are layout/presentation markup, leaving
    73 in-scope graph elements.
    """
    in_scope = sum(1 for el in CODEBOOK_GENERATED_ELEMENTS if not el.is_layout)
    layout = sum(1 for el in CODEBOOK_GENERATED_ELEMENTS if el.is_layout)
    assert in_scope == 73, f"unexpected in-scope codebook element count: {in_scope}"
    assert layout == 10, f"unexpected layout-element count: {layout}"

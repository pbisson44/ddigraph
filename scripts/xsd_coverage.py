"""Real XSD-driven coverage audit for the ddigraph package.

This tool *parses the bundled XSD files* to discover which identifiable
element declarations exist in each DDI flavor, then compares that set
against what the package actually registers as graph nodes / dispatch
handlers.  Unlike a curated target list, the target set is derived
deterministically from the schemas that ship with the package, so the
coverage number reflects real schema conformance.

Scope (what is considered "in-scope for graph nodes"):

* **DDI-L 3.x** — every concrete (non-abstract) element whose XSD type
  extends ``MaintainableType``, ``VersionableType`` or ``IdentifiableType``.
  Abstract substitution-group heads (``ControlConstruct``,
  ``ManagedRepresentation``, ``DevelopmentActivity``, ...) are excluded —
  only their concrete substitutes are counted.
* **DDI-Codebook 2.x** — every global element whose complexType (directly
  or via inheritance) includes the ``GLOBALS`` attribute group, i.e. every
  element that can carry an ``ID`` attribute and be referenced.  Pure
  text-only types that do not pull in ``GLOBALS`` are excluded.
* **DDI-CDI 1.0** — every top-level concrete entity element declared in
  ``ddi-cdi.xsd``, excluding the ``*_<verb>_*`` association elements
  (which are covered by the relationship-coverage section).

Usage::

    python scripts/xsd_coverage.py                # human-readable table
    python scripts/xsd_coverage.py --json         # machine-readable JSON
    python scripts/xsd_coverage.py --threshold 100  # require 100% coverage

Exit codes:
  0 - coverage meets or exceeds the threshold for every flavor
  1 - one or more flavors fall below the threshold
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from lxml import etree  # type: ignore[import-untyped,unused-ignore]

XS = "{http://www.w3.org/2001/XMLSchema}"
REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
SRC_DIR = REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# XSD parsing
# ---------------------------------------------------------------------------


def _iter_xsds(root: Path) -> list[Path]:
    """Return the schema files relevant for DDI identifiables in `root`."""
    return sorted(p for p in root.glob("*.xsd") if p.name != "xml.xsd" and "xhtml" not in p.name)


def _local(qname: str | None) -> str:
    if not qname:
        return ""
    return qname.split(":", 1)[-1]


def _ddi_l_identifiables(schema_dir: Path) -> dict[str, set[str]]:
    """Extract concrete identifiable elements from a DDI-L schema directory.

    Walks the complexType inheritance graph to identify which element names ultimately
    extend MaintainableType, VersionableType, or IdentifiableType. Abstract elements are
    excluded.
    """
    bases: dict[str, str] = {}
    element_type: dict[str, str] = {}
    element_abstract: dict[str, bool] = {}

    for xsd in _iter_xsds(schema_dir):
        tree = etree.parse(str(xsd))
        root = tree.getroot()

        for ct in root.findall(f"{XS}complexType"):
            name = ct.get("name")
            if not name:
                continue
            ext = ct.find(f"{XS}complexContent/{XS}extension")
            if ext is not None and ext.get("base"):
                bases[name] = _local(ext.get("base"))
                continue
            restr = ct.find(f"{XS}complexContent/{XS}restriction")
            if restr is not None and restr.get("base"):
                bases[name] = _local(restr.get("base"))
                continue
            bases.setdefault(name, "")

        for el in root.findall(f"{XS}element"):
            en = el.get("name")
            if not en:
                continue
            element_abstract[en] = el.get("abstract") == "true"
            t = el.get("type")
            if t:
                element_type[en] = _local(t)
                continue
            inline = el.find(f"{XS}complexType")
            if inline is not None:
                ext = inline.find(f"{XS}complexContent/{XS}extension")
                if ext is not None and ext.get("base"):
                    synth = f"__anon__{en}"
                    element_type[en] = synth
                    bases[synth] = _local(ext.get("base"))
                    continue
                restr = inline.find(f"{XS}complexContent/{XS}restriction")
                if restr is not None and restr.get("base"):
                    synth = f"__anon__{en}"
                    element_type[en] = synth
                    bases[synth] = _local(restr.get("base"))

    def ancestors(t: str) -> set[str]:
        seen: set[str] = set()
        cur = t
        while cur and cur not in seen:
            seen.add(cur)
            cur = bases.get(cur, "")
        return seen

    maintainables: set[str] = set()
    versionables: set[str] = set()
    identifiables: set[str] = set()
    abstracts: set[str] = set()

    for en, tname in element_type.items():
        if element_abstract.get(en):
            abstracts.add(en)
            continue
        anc = ancestors(tname)
        if "MaintainableType" in anc:
            maintainables.add(en)
        elif "VersionableType" in anc:
            versionables.add(en)
        elif "IdentifiableType" in anc:
            identifiables.add(en)

    return {
        "maintainables": maintainables,
        "versionables": versionables,
        "identifiables": identifiables,
        "abstracts": abstracts,
    }


def _ddi_c_identifiable_elements(schema_dir: Path) -> set[str]:
    """Return codebook elements whose type (or an ancestor) carries ``GLOBALS``.

    Every such element can carry an ``ID`` and be referenced.  We return
    their lowercased names so they can be compared directly with the
    codebook loader's dispatch keys (which are lowercase).
    """
    codebook = schema_dir / "codebook.xsd"
    tree = etree.parse(str(codebook))
    root = tree.getroot()

    type_has_globals: dict[str, bool] = {}
    type_base: dict[str, str] = {}

    for ct in root.findall(f"{XS}complexType"):
        n = ct.get("name")
        if not n:
            continue
        has_g = False
        for ag in ct.iter(f"{XS}attributeGroup"):
            if ag.get("ref") == "GLOBALS":
                has_g = True
                break
        type_has_globals[n] = has_g
        for ext in ct.iter(f"{XS}extension"):
            b = ext.get("base")
            if b:
                type_base[n] = _local(b)
                break

    changed = True
    while changed:
        changed = False
        for n, b in type_base.items():
            if type_has_globals.get(b) and not type_has_globals.get(n):
                type_has_globals[n] = True
                changed = True

    ids: set[str] = set()
    for el in root.findall(f"{XS}element"):
        en = el.get("name")
        if not en:
            continue
        t = el.get("type")
        if t and type_has_globals.get(_local(t)):
            ids.add(en.lower())
    return ids


# Layout/table markup inherited from CALS + pure-presentation elements
# whose only role is visual structure inside a codebook.  These are not
# independently-identifiable objects in the graph sense and are excluded
# from the DDI-C target set.
DDI_C_LAYOUT_EXCLUDES: set[str] = {
    "row",
    "table",
    "tbody",
    "tgroup",
    "thead",
    "colspec",
    "mrow",
    "entry",
    "item",
    "dataitem",
    "codebook",  # the root envelope itself (container, covered by children)
}


def _ddi_cdi_extract(schema_dir: Path) -> tuple[set[str], set[str], set[str]]:
    """Return (concrete_entities, association_elements, abstract_elements).

    Associations are ``<Entity>_<verb>_<Entity>`` elements; everything else non-abstract
    is considered an entity element.
    """
    cdi = schema_dir / "ddi-cdi.xsd"
    tree = etree.parse(str(cdi))
    root = tree.getroot()

    entities: set[str] = set()
    associations: set[str] = set()
    abstracts: set[str] = set()

    assoc_re = re.compile(r"^[A-Z]\w+_\w+_[A-Z]\w+$")

    for el in root.findall(f"{XS}element"):
        en = el.get("name")
        if not en:
            continue
        if el.get("abstract") == "true":
            abstracts.add(en)
            continue
        if assoc_re.match(en):
            associations.add(en)
        else:
            entities.add(en)
    return entities, associations, abstracts


# ---------------------------------------------------------------------------
# Package coverage
# ---------------------------------------------------------------------------


def _load_package_coverage() -> dict[str, Any]:
    """Load node labels and relationship / dispatch sets from the package."""
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from ddigraph.ingest.cdi_loader import (
        _CDI_RELATIONSHIP_MAP,
        _CDI_TAG_MAP,
    )
    from ddigraph.ingest.fragment_loader import DDIFragmentParser
    from ddigraph.ingest.loader import _GENERIC_IDENTIFIABLE_TAGS
    from ddigraph.schema.definitions import DDISchema

    loader_src = (SRC_DIR / "ddigraph" / "ingest" / "loader.py").read_text()
    # Bespoke handlers are ``"tag": lambda`` literals; the generic
    # codebook elements are dispatched through the
    # ``_GENERIC_IDENTIFIABLE_TAGS`` fallback instead of a per-tag
    # lambda, so the dispatch surface is their union.
    codebook_tag_keys: set[str] = {
        m.lower() for m in re.findall(r'"([a-zA-Z][a-zA-Z0-9]+)"\s*:\s*lambda\b', loader_src)
    } | {tag.lower() for tag in _GENERIC_IDENTIFIABLE_TAGS}

    return {
        "fragment_labels": {n.label for n in DDISchema.FRAGMENT_NODES},
        "codebook_labels": {n.label for n in DDISchema.CODEBOOK_NODES},
        "cdi_labels": {n.label for n in DDISchema.CDI_NODES},
        "fragment_name_tags": set(DDIFragmentParser.NAME_TAGS.keys()),
        "cdi_tag_map_keys": set(_CDI_TAG_MAP.keys()),
        "fragment_rel_types": set(DDISchema.FRAGMENT_RELATIONSHIP_TYPES.keys()),
        "cdi_rel_keys": set(_CDI_RELATIONSHIP_MAP.keys()),
        "codebook_tag_keys": codebook_tag_keys,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _pct(covered: int, total: int) -> float:
    return round(100.0 * covered / total, 1) if total > 0 else 100.0


def _print_table(
    title: str,
    covered: set[str],
    target: set[str],
    *,
    show_extra: bool = True,
) -> float:
    missing = sorted(target - covered)
    extra = sorted(covered - target)
    n_covered = len(target) - len(missing)
    pct = _pct(n_covered, len(target))

    print(f"\n{'=' * 68}")
    print(f"  {title}")
    print(f"  target={len(target)}  covered={n_covered}  pct={pct:.1f}%")
    print(f"{'=' * 68}")

    if missing:
        print(f"\n  MISSING in package ({len(missing)}):")
        for m in missing:
            print(f"    - {m}")
    else:
        print("\n  All target items covered.")

    if show_extra and extra:
        print(f"\n  Extra in package (not in XSD target) ({len(extra)}):")
        for e in extra:
            print(f"    + {e}")

    return pct


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def run_audit(json_output: bool = False, threshold: float = 100.0) -> int:
    pkg = _load_package_coverage()

    # DDI-L: scan the latest version (3.3).  3.1/3.2/3.3 have identical
    # identifiable element sets so coverage against 3.3 implies coverage
    # against 3.1/3.2 as well.
    ddi_l_3_3 = _ddi_l_identifiables(SCHEMAS_DIR / "ddi" / "v3_3")
    ddi_l_in_scope = (
        ddi_l_3_3["maintainables"] | ddi_l_3_3["versionables"] | ddi_l_3_3["identifiables"]
    )
    ddi_l_covered = pkg["fragment_labels"] & ddi_l_in_scope
    pct_ddi_l = _pct(len(ddi_l_covered), len(ddi_l_in_scope))

    # DDI-Codebook
    ddi_c_all = _ddi_c_identifiable_elements(SCHEMAS_DIR / "ddi-c")
    ddi_c_scope = ddi_c_all - DDI_C_LAYOUT_EXCLUDES
    ddi_c_covered = pkg["codebook_tag_keys"] & ddi_c_scope
    pct_ddi_c = _pct(len(ddi_c_covered), len(ddi_c_scope))

    # DDI-CDI
    cdi_entities, cdi_assocs, cdi_abs = _ddi_cdi_extract(SCHEMAS_DIR / "ddi-cdi" / "xml-schema")
    cdi_covered = pkg["cdi_tag_map_keys"] & cdi_entities
    pct_cdi = _pct(len(cdi_covered), len(cdi_entities))

    # Name-tags gap for DDI-L
    missing_name_tags = pkg["fragment_labels"] - pkg["fragment_name_tags"]

    if json_output:
        report = {
            "ddi_l": {
                "scope_description": (
                    "concrete Maintainable + Versionable + Identifiable elements "
                    "in DDI-L 3.3 (same set as 3.1/3.2)"
                ),
                "target": sorted(ddi_l_in_scope),
                "target_count": len(ddi_l_in_scope),
                "covered": sorted(ddi_l_covered),
                "covered_count": len(ddi_l_covered),
                "missing": sorted(ddi_l_in_scope - pkg["fragment_labels"]),
                "coverage_pct": pct_ddi_l,
                "abstracts_excluded": sorted(ddi_l_3_3["abstracts"]),
            },
            "ddi_c": {
                "scope_description": (
                    "global codebook elements whose complexType carries the GLOBALS "
                    "attribute group (excluding layout markup)"
                ),
                "target": sorted(ddi_c_scope),
                "target_count": len(ddi_c_scope),
                "covered": sorted(ddi_c_covered),
                "covered_count": len(ddi_c_covered),
                "missing": sorted(ddi_c_scope - pkg["codebook_tag_keys"]),
                "coverage_pct": pct_ddi_c,
                "layout_excludes": sorted(DDI_C_LAYOUT_EXCLUDES),
            },
            "ddi_cdi": {
                "scope_description": (
                    "concrete top-level entity elements in ddi-cdi.xsd (associations excluded)"
                ),
                "target": sorted(cdi_entities),
                "target_count": len(cdi_entities),
                "covered": sorted(cdi_covered),
                "covered_count": len(cdi_covered),
                "missing": sorted(cdi_entities - pkg["cdi_tag_map_keys"]),
                "coverage_pct": pct_cdi,
                "associations_found": len(cdi_assocs),
                "abstracts_excluded": sorted(cdi_abs),
            },
            "name_tags_gap": sorted(missing_name_tags),
        }
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'=' * 68}")
        print("  ddigraph XSD Coverage Audit (real XSD scan)")
        print(f"{'=' * 68}")

        _print_table(
            "DDI-L 3.x concrete identifiables (Maint + Vers + Ident)",
            pkg["fragment_labels"],
            ddi_l_in_scope,
            show_extra=False,
        )
        _print_table(
            "DDI-Codebook elements with GLOBALS (layout markup excluded)",
            pkg["codebook_tag_keys"],
            ddi_c_scope,
            show_extra=False,
        )
        _print_table(
            "DDI-CDI 1.0 concrete entity elements",
            pkg["cdi_tag_map_keys"],
            cdi_entities,
            show_extra=False,
        )

        if missing_name_tags:
            print(f"\n{'=' * 68}")
            print("  Fragment nodes missing NAME_TAGS entries")
            print(f"{'=' * 68}")
            for label in sorted(missing_name_tags):
                print(f"    - {label}")

        print(f"\n{'=' * 68}")
        print("  SUMMARY")
        print(f"{'=' * 68}")
        print(f"  DDI-L 3.x coverage:   {pct_ddi_l:6.1f}%")
        print(f"  DDI-C 2.x coverage:   {pct_ddi_c:6.1f}%")
        print(f"  DDI-CDI 1.0 coverage: {pct_cdi:6.1f}%")
        print(f"{'=' * 68}\n")

    failed = False
    for label, pct in (
        ("DDI-L", pct_ddi_l),
        ("DDI-C", pct_ddi_c),
        ("DDI-CDI", pct_cdi),
    ):
        if pct < threshold:
            print(
                f"FAIL: {label} coverage {pct:.1f}% is below threshold {threshold:.1f}%",
                file=sys.stderr,
            )
            failed = True

    if missing_name_tags:
        print(
            f"FAIL: {len(missing_name_tags)} fragment labels missing NAME_TAGS entries",
            file=sys.stderr,
        )
        failed = True

    return 1 if failed else 0


# ---------------------------------------------------------------------------
# Structural coverage (relationship dimension)
# ---------------------------------------------------------------------------


def _ddi_l_reference_elements(schema_dir: Path) -> set[str]:
    """Return every ``*Reference``-suffixed ``xs:element`` declared in DDI-L."""
    refs: set[str] = set()
    for xsd in _iter_xsds(schema_dir):
        tree = etree.parse(str(xsd))
        for el in tree.getroot().findall(f"{XS}element"):
            name = el.get("name") or ""
            if name.endswith("Reference"):
                refs.add(name)
    return refs


def _ddi_cdi_associations(schema_dir: Path) -> set[str]:
    """Return every ``<Source>_<verb>_<Target>`` association tag in DDI-CDI.

    Walks the XSD via lxml -- same data the xmlschema-based generator
    emits, but read here through lxml so this audit has no runtime
    dependency on xmlschema.
    """
    cdi = schema_dir / "ddi-cdi.xsd"
    tree = etree.parse(str(cdi))
    root = tree.getroot()
    assoc_re = re.compile(r"^[A-Z]\w*_\w+_[A-Z]\w*$")
    found: set[str] = set()
    for el in root.iter(f"{XS}element"):
        name = el.get("name") or ""
        if assoc_re.match(name):
            found.add(name)
    return found


def _structural_coverage() -> dict[str, dict[str, Any]]:
    """Compute relationship structural coverage per flavor.

    Returns one entry per flavor with at least the keys ``target``
    (sorted list of XSD-declared relationship tags), ``covered``
    (sorted intersection with the runtime), ``missing`` (sorted
    difference), and ``coverage_pct``.
    """
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from ddigraph.ingest.cdi_loader import _CDI_RELATIONSHIP_MAP
    from ddigraph.schema.definitions import DDISchema

    # DDI-CDI relationship coverage.
    cdi_xsd = _ddi_cdi_associations(SCHEMAS_DIR / "ddi-cdi" / "xml-schema")
    cdi_runtime = set(_CDI_RELATIONSHIP_MAP)
    cdi_missing = cdi_xsd - cdi_runtime

    # DDI-L reference coverage. ExternalURLReference is a synthetic
    # runtime-only edge documented in tests/test_lifecycle_generator.py.
    ddi_l_xsd = _ddi_l_reference_elements(SCHEMAS_DIR / "ddi" / "v3_3")
    ddi_l_runtime = set(DDISchema.FRAGMENT_RELATIONSHIP_TYPES)
    ddi_l_missing = ddi_l_xsd - ddi_l_runtime

    # DDI-Codebook uses positional containment rather than reference
    # patterns, so there is no relationship-tag dimension to audit.
    # The structural coverage section reports it as "n/a" with 100%.

    return {
        "ddi_l": {
            "scope_description": (
                "XSD-declared *Reference elements vs. FRAGMENT_RELATIONSHIP_TYPES dict keys"
            ),
            "target": sorted(ddi_l_xsd),
            "target_count": len(ddi_l_xsd),
            "covered_count": len(ddi_l_xsd & ddi_l_runtime),
            "missing": sorted(ddi_l_missing),
            "coverage_pct": _pct(len(ddi_l_xsd & ddi_l_runtime), len(ddi_l_xsd)),
        },
        "ddi_c": {
            "scope_description": (
                "DDI-Codebook expresses relationships via positional "
                "containment, not reference tags; structural relationship "
                "coverage is not applicable to this flavor"
            ),
            "target": [],
            "target_count": 0,
            "covered_count": 0,
            "missing": [],
            "coverage_pct": 100.0,
        },
        "ddi_cdi": {
            "scope_description": (
                "XSD-declared <Source>_<verb>_<Target> association tags vs. "
                "_CDI_RELATIONSHIP_MAP dict keys"
            ),
            "target": sorted(cdi_xsd),
            "target_count": len(cdi_xsd),
            "covered_count": len(cdi_xsd & cdi_runtime),
            "missing": sorted(cdi_missing),
            "coverage_pct": _pct(len(cdi_xsd & cdi_runtime), len(cdi_xsd)),
        },
    }


def _print_structural_table(label: str, report: dict[str, Any]) -> None:
    """Print one flavor's structural coverage as a human-readable table."""
    target = report["target_count"]
    covered = report["covered_count"]
    pct = report["coverage_pct"]
    missing = report["missing"]

    print(f"\n{'=' * 68}")
    print(f"  {label}")
    print(f"  {report['scope_description']}")
    print(f"  target={target}  covered={covered}  pct={pct:.1f}%")
    print(f"{'=' * 68}")
    if not target:
        print("\n  Not applicable for this flavor.")
        return
    if missing:
        sample = missing[:20]
        print(f"\n  MISSING from runtime ({len(missing)}; first 20 shown):")
        for m in sample:
            print(f"    - {m}")
        if len(missing) > len(sample):
            print(f"    ... and {len(missing) - len(sample)} more")
    else:
        print("\n  All XSD-declared relationships covered.")


def run_structural_audit(json_output: bool = False, threshold: float = 0.0) -> int:
    """Report relationship structural coverage per flavor.

    Args:
        json_output: When True, emit a machine-readable JSON report.
        threshold: Minimum acceptable coverage percentage per flavor.
            Defaults to 0.0 (advisory only) while the loader collapse
            in plan step C is in progress. The 0.4.0rc1 cut raises this
            to 100.0 and the override file absorbs documented exceptions.

    Returns:
        Process exit code (0 if every flavor meets the threshold).
    """
    report = _structural_coverage()

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'=' * 68}")
        print("  ddigraph XSD Structural Coverage (relationship dimension)")
        print(f"{'=' * 68}")
        _print_structural_table("DDI-L 3.x *Reference coverage", report["ddi_l"])
        _print_structural_table("DDI-Codebook 2.x", report["ddi_c"])
        _print_structural_table("DDI-CDI 1.0 association coverage", report["ddi_cdi"])
        print(f"\n{'=' * 68}")
        print("  SUMMARY")
        print(f"{'=' * 68}")
        for key, label in (
            ("ddi_l", "DDI-L *Reference"),
            ("ddi_c", "DDI-Codebook"),
            ("ddi_cdi", "DDI-CDI association"),
        ):
            print(f"  {label:30s}{report[key]['coverage_pct']:6.1f}%")
        print(f"{'=' * 68}\n")

    failed = False
    for key, label in (
        ("ddi_l", "DDI-L"),
        ("ddi_cdi", "DDI-CDI"),
    ):
        pct = float(report[key]["coverage_pct"])
        if pct < threshold:
            print(
                f"FAIL: {label} structural coverage {pct:.1f}% is below threshold {threshold:.1f}%",
                file=sys.stderr,
            )
            failed = True

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--threshold", type=float, default=100.0, help="Minimum coverage (default 100)."
    )
    parser.add_argument(
        "--structural",
        action="store_true",
        help=(
            "Emit relationship structural coverage instead of nominal "
            "element coverage. Reports per-tag gaps between XSD-declared "
            "relationships and the runtime's relationship-type maps."
        ),
    )
    parser.add_argument(
        "--structural-threshold",
        type=float,
        default=0.0,
        help=(
            "Minimum structural coverage percentage (default 0.0; raises "
            "to 100.0 once the loader collapse in plan step C lands)."
        ),
    )
    args = parser.parse_args()
    if args.structural:
        return run_structural_audit(json_output=args.json, threshold=args.structural_threshold)
    return run_audit(json_output=args.json, threshold=args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())

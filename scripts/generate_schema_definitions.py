"""Derive ``NodeDefinition`` / ``RelationshipDefinition`` data from the bundled XSDs.

This script is the source of truth for ``src/ddigraph/schema/_generated/``.
It parses each DDI flavor's XSDs and writes deterministic Python modules
that downstream code (loaders, adapters, tests) can import.

Currently implemented:

* **DDI-CDI 1.0** -- ``_generated/cdi.py`` (entities + associations) via
  ``xmlschema.XMLSchema11``.
* **DDI-L 3.x lifecycle** -- ``_generated/lifecycle.py`` (concrete
  identifiables classified by kind + every ``*Reference`` element) via
  ``lxml.etree`` (the DDI-L XSDs trip XSD 1.1 strict validation, so we
  use the same lxml walker that ``scripts/xsd_coverage.py`` relies on).
* **DDI-Codebook 2.6** -- ``_generated/codebook.py`` (every ``xs:element``
  whose complexType inherits the ``GLOBALS`` attribute group, paired with
  its complex-type name and a layout-exclusion flag) via ``lxml.etree``.
  The codebook XSD imports XHTML modules which trip xmlschema too.

Pending (separate commit per the simplification plan):

* Override merging from ``_overrides/schema_overrides.toml``.

Usage::

    python scripts/generate_schema_definitions.py            # write artefacts
    python scripts/generate_schema_definitions.py --check    # exit non-zero
                                                             # if regeneration
                                                             # would change
                                                             # the committed
                                                             # files

Exit codes:
  0 - generation succeeded (or, with ``--check``, the artefacts are current)
  1 - generation failed, or ``--check`` detected drift
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import xmlschema
from lxml import etree  # type: ignore[import-untyped,unused-ignore]

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"
GENERATED_DIR = REPO_ROOT / "src" / "ddigraph" / "schema" / "_generated"
_XS_NS = "{http://www.w3.org/2001/XMLSchema}"

SCHEMA_ENTRYPOINTS: dict[str, Path] = {
    "codebook": SCHEMAS_DIR / "ddi-c" / "codebook.xsd",
    "lifecycle": SCHEMAS_DIR / "ddi" / "v3_3" / "instance_3_3.xsd",
    "cdi": SCHEMAS_DIR / "ddi-cdi" / "xml-schema" / "ddi-cdi.xsd",
}

_ASSOCIATION_RE = re.compile(r"^([A-Z]\w*)_(\w+)_([A-Z]\w*)$")
_NON_TARGET_PREFIXES = ("DDI",)


def _verify_assets() -> list[str]:
    """Return human-readable issues with the bundled XSDs.

    Empty list means every entry-point XSD is present on disk.
    """
    issues: list[str] = []
    for flavor, path in SCHEMA_ENTRYPOINTS.items():
        if not path.exists():
            issues.append(f"missing {flavor} entrypoint: {path.relative_to(REPO_ROOT)}")
    if not GENERATED_DIR.exists():
        rel = GENERATED_DIR.relative_to(REPO_ROOT)
        issues.append(f"missing generated package directory: {rel}")
    return issues


def _walk_cdi(xsd_path: Path) -> tuple[list[str], list[tuple[str, str, str, str]]]:
    """Walk the DDI-CDI XSD and extract entities and associations.

    Args:
        xsd_path: Path to ``ddi-cdi.xsd``.

    Returns:
        A pair ``(entities, associations)`` where:
        * ``entities`` is a sorted list of concrete entity element names
          (top-level declarations whose name does not match the
          ``<Source>_<verb>_<Target>`` association pattern and is not part
          of the ``DDI*`` framing wrappers).
        * ``associations`` is a sorted list of
          ``(tag, source, verb, target)`` tuples for every association
          element seen in any entity's content tree.
    """
    schema = xmlschema.XMLSchema11(str(xsd_path))
    target_ns = schema.target_namespace

    entities: set[str] = set()
    associations: dict[str, tuple[str, str, str, str]] = {}

    for raw_name, element in schema.elements.items():
        name = str(raw_name)
        if element.target_namespace != target_ns:
            continue
        if name.startswith(_NON_TARGET_PREFIXES):
            continue

        top_match = _ASSOCIATION_RE.match(name)
        if top_match is not None:
            # Top-level association declaration (rare in CDI; nested
            # traversal below covers the common case).
            source, verb, target = top_match.groups()
            associations[name] = (name, source, verb, target)
            continue

        entities.add(name)

        element_type = element.type
        if element_type is None or element_type.is_simple():
            continue
        content = getattr(element_type, "content", None)
        if content is None or not hasattr(content, "iter_elements"):
            continue

        for child in content.iter_elements():
            child_name = child.local_name
            if not isinstance(child_name, str) or child_name in associations:
                continue
            child_match = _ASSOCIATION_RE.match(child_name)
            if child_match is None:
                continue
            source, verb, target = child_match.groups()
            associations[child_name] = (child_name, source, verb, target)

    return sorted(entities), sorted(associations.values())


def _render_cdi_module(entities: list[str], associations: list[tuple[str, str, str, str]]) -> str:
    """Render the ``_generated/cdi.py`` module source from generator output."""
    header = (
        '"""Generated DDI-CDI 1.0 schema metadata.\n'
        "\n"
        "Auto-generated from ``schemas/ddi-cdi/xml-schema/ddi-cdi.xsd`` by\n"
        "``scripts/generate_schema_definitions.py``. Do not edit by hand.\n"
        "\n"
        "Re-run::\n"
        "\n"
        "    python scripts/generate_schema_definitions.py\n"
        "\n"
        "to regenerate after changing the bundled XSDs.\n"
        '"""\n'
        "\n"
        "from typing import NamedTuple\n"
        "\n"
        "\n"
        "class CDIAssociation(NamedTuple):\n"
        '    """One ``<source>_<verb>_<target>`` XSD association element."""\n'
        "\n"
        "    tag: str\n"
        "    source: str\n"
        "    verb: str\n"
        "    target: str\n"
        "\n"
        "\n"
    )

    entities_block = "CDI_GENERATED_ENTITIES: tuple[str, ...] = (\n"
    for name in entities:
        entities_block += f'    "{name}",\n'
    entities_block += ")\n\n\n"

    assoc_block = "CDI_GENERATED_ASSOCIATIONS: tuple[CDIAssociation, ...] = (\n"
    for tag, source, verb, target in associations:
        assoc_block += (
            f'    CDIAssociation(tag="{tag}", source="{source}", '
            f'verb="{verb}", target="{target}"),\n'
        )
    assoc_block += ")\n\n\n"

    footer = (
        '__all__ = ["CDI_GENERATED_ASSOCIATIONS", "CDI_GENERATED_ENTITIES", "CDIAssociation"]\n'
    )

    return header + entities_block + assoc_block + footer


def _ruff_format(source: str) -> str:
    """Pipe ``source`` through ``ruff format`` and return the formatted text.

    Falling through ``ruff format`` makes the generator output stable under
    ``ruff format --check`` so CI does not see spurious drift.
    """
    result = subprocess.run(
        ["ruff", "format", "--stdin-filename", "cdi.py", "-"],
        input=source,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ruff format failed: {result.stderr}")
    return result.stdout


def _generate_cdi(write: bool) -> tuple[bool, str]:
    """Generate ``_generated/cdi.py``.

    Args:
        write: When False, only check that the committed file matches what
            the generator would produce and return drift information.

    Returns:
        ``(changed, message)`` -- ``changed`` is True if the on-disk file
        differs from generator output. ``message`` is a human-readable
        status line.
    """
    entities, associations = _walk_cdi(SCHEMA_ENTRYPOINTS["cdi"])
    rendered = _ruff_format(_render_cdi_module(entities, associations))

    target = GENERATED_DIR / "cdi.py"
    existing = target.read_text() if target.exists() else ""
    changed = existing != rendered

    if write and changed:
        target.write_text(rendered)
        return changed, (
            f"wrote {target.relative_to(REPO_ROOT)}: "
            f"{len(entities)} entities, {len(associations)} associations"
        )
    if changed:
        return changed, f"DRIFT: {target.relative_to(REPO_ROOT)} would be regenerated"
    return changed, (
        f"{target.relative_to(REPO_ROOT)} already up to date "
        f"({len(entities)} entities, {len(associations)} associations)"
    )


def _iter_ddi_l_xsds(schema_dir: Path) -> list[Path]:
    """Return DDI-L XSD modules excluding the XHTML drag-along payload."""
    return sorted(
        p for p in schema_dir.glob("*.xsd") if p.name != "xml.xsd" and "xhtml" not in p.name
    )


def _local(qname: str | None) -> str:
    """Strip an XML-namespace prefix from a qualified name."""
    if not qname:
        return ""
    return qname.split(":", 1)[-1]


def _walk_lifecycle(
    schema_dir: Path,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Walk every DDI-L XSD and classify identifiables and reference elements.

    Reuses the inheritance-walk approach in
    ``scripts/xsd_coverage.py:_ddi_l_identifiables`` but extends it to
    return one merged sorted list of concrete identifiables labelled by
    kind, plus the set of every ``*Reference`` element observed across
    the schemas (the reference-typed children that form relationships at
    parse time).

    Args:
        schema_dir: Directory containing the DDI-L XSD modules.

    Returns:
        A pair ``(entities, references)`` where ``entities`` is a sorted
        list of ``(name, kind)`` tuples with ``kind`` in
        ``{"Maintainable", "Versionable", "Identifiable"}``, and
        ``references`` is a sorted list of every element name that ends
        in ``"Reference"`` declared in any of the schemas.
    """
    bases: dict[str, str] = {}
    element_type: dict[str, str] = {}
    element_abstract: dict[str, bool] = {}
    reference_elements: set[str] = set()

    for xsd in _iter_ddi_l_xsds(schema_dir):
        tree = etree.parse(str(xsd))
        root = tree.getroot()

        for ct in root.findall(f"{_XS_NS}complexType"):
            name = ct.get("name")
            if not name:
                continue
            ext = ct.find(f"{_XS_NS}complexContent/{_XS_NS}extension")
            if ext is not None and ext.get("base"):
                bases[name] = _local(ext.get("base"))
                continue
            restr = ct.find(f"{_XS_NS}complexContent/{_XS_NS}restriction")
            if restr is not None and restr.get("base"):
                bases[name] = _local(restr.get("base"))
                continue
            bases.setdefault(name, "")

        for el in root.findall(f"{_XS_NS}element"):
            en = el.get("name")
            if not en:
                continue
            if en.endswith("Reference"):
                reference_elements.add(en)
            element_abstract[en] = el.get("abstract") == "true"
            t = el.get("type")
            if t:
                element_type[en] = _local(t)
                continue
            inline = el.find(f"{_XS_NS}complexType")
            if inline is not None:
                ext = inline.find(f"{_XS_NS}complexContent/{_XS_NS}extension")
                if ext is not None and ext.get("base"):
                    synth = f"__anon__{en}"
                    element_type[en] = synth
                    bases[synth] = _local(ext.get("base"))
                    continue
                restr = inline.find(f"{_XS_NS}complexContent/{_XS_NS}restriction")
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

    entities: list[tuple[str, str]] = []
    for en, tname in element_type.items():
        if element_abstract.get(en):
            continue
        anc = ancestors(tname)
        if "MaintainableType" in anc:
            entities.append((en, "Maintainable"))
        elif "VersionableType" in anc:
            entities.append((en, "Versionable"))
        elif "IdentifiableType" in anc:
            entities.append((en, "Identifiable"))

    return sorted(entities), sorted(reference_elements)


def _render_lifecycle_module(entities: list[tuple[str, str]], references: list[str]) -> str:
    """Render the ``_generated/lifecycle.py`` module source."""
    header = (
        '"""Generated DDI-L 3.x lifecycle schema metadata.\n'
        "\n"
        "Auto-generated from ``schemas/ddi/v3_3/*.xsd`` by\n"
        "``scripts/generate_schema_definitions.py``. Do not edit by hand.\n"
        "\n"
        "Re-run::\n"
        "\n"
        "    python scripts/generate_schema_definitions.py\n"
        "\n"
        "to regenerate after changing the bundled XSDs.\n"
        '"""\n'
        "\n"
        "from typing import Literal, NamedTuple\n"
        "\n"
        'IdentifiableKind = Literal["Maintainable", "Versionable", "Identifiable"]\n'
        "\n"
        "\n"
        "class FragmentEntity(NamedTuple):\n"
        '    """A concrete DDI-L identifiable element declared in the XSDs."""\n'
        "\n"
        "    name: str\n"
        "    kind: IdentifiableKind\n"
        "\n"
        "\n"
        "class FragmentReference(NamedTuple):\n"
        '    """A ``*Reference`` element name observed in any DDI-L XSD."""\n'
        "\n"
        "    tag: str\n"
        "\n"
        "\n"
    )

    entities_block = "FRAGMENT_GENERATED_ENTITIES: tuple[FragmentEntity, ...] = (\n"
    for name, kind in entities:
        entities_block += f'    FragmentEntity(name="{name}", kind="{kind}"),\n'
    entities_block += ")\n\n\n"

    refs_block = "FRAGMENT_GENERATED_REFERENCES: tuple[FragmentReference, ...] = (\n"
    for tag in references:
        refs_block += f'    FragmentReference(tag="{tag}"),\n'
    refs_block += ")\n\n\n"

    footer = (
        "__all__ = ["
        '"FRAGMENT_GENERATED_ENTITIES", '
        '"FRAGMENT_GENERATED_REFERENCES", '
        '"FragmentEntity", '
        '"FragmentReference", '
        '"IdentifiableKind"'
        "]\n"
    )

    return header + entities_block + refs_block + footer


def _generate_lifecycle(write: bool) -> tuple[bool, str]:
    """Generate ``_generated/lifecycle.py``.

    Args:
        write: When False, only check that the committed file matches what
            the generator would produce and return drift information.

    Returns:
        ``(changed, message)`` -- ``changed`` is True if the on-disk file
        differs from generator output. ``message`` is a human-readable
        status line.
    """
    schema_dir = SCHEMA_ENTRYPOINTS["lifecycle"].parent
    entities, references = _walk_lifecycle(schema_dir)
    rendered = _ruff_format(_render_lifecycle_module(entities, references))

    target = GENERATED_DIR / "lifecycle.py"
    existing = target.read_text() if target.exists() else ""
    changed = existing != rendered

    if write and changed:
        target.write_text(rendered)
        return changed, (
            f"wrote {target.relative_to(REPO_ROOT)}: "
            f"{len(entities)} identifiables, {len(references)} reference types"
        )
    if changed:
        return changed, f"DRIFT: {target.relative_to(REPO_ROOT)} would be regenerated"
    return changed, (
        f"{target.relative_to(REPO_ROOT)} already up to date "
        f"({len(entities)} identifiables, {len(references)} reference types)"
    )


# Layout / table markup inherited from CALS and pure-presentation
# elements whose only role is visual structure inside a codebook.
# These carry GLOBALS in the XSD but are not graph-relevant. The set
# mirrors ``scripts/xsd_coverage.py:DDI_C_LAYOUT_EXCLUDES``; eventually
# it will move to ``schema_overrides.toml``.
_DDI_C_LAYOUT_EXCLUDES: frozenset[str] = frozenset(
    {
        "row",
        "table",
        "tbody",
        "tgroup",
        "thead",
        "colspec",
        "mrow",
        # ``entry`` is listed for parity with ``xsd_coverage.py``; its XSD
        # type extends ``stringType`` via ``xs:simpleContent`` and does
        # not inherit GLOBALS, so it never actually appears in the
        # generated set. Kept here so the two enumerations stay
        # identical until ``schema_overrides.toml`` canonicalises both.
        "entry",
        "item",
        "dataitem",
        "codebook",
    }
)


def _walk_codebook(xsd_path: Path) -> list[tuple[str, str, bool]]:
    """Walk ``codebook.xsd`` and extract every GLOBALS-bearing element.

    Mirrors the algorithm in
    ``scripts/xsd_coverage.py:_ddi_c_identifiable_elements`` but also
    records the complexType name for each element and the layout-
    exclusion flag, so downstream code can distinguish in-scope graph
    elements from CALS table / XHTML markup.

    Args:
        xsd_path: Path to ``codebook.xsd``.

    Returns:
        A sorted list of ``(name_lowercase, complex_type, is_layout)``
        tuples covering every ``xs:element`` whose complexType (directly
        or via inheritance) carries the ``GLOBALS`` attribute group.
    """
    tree = etree.parse(str(xsd_path))
    root = tree.getroot()

    type_has_globals: dict[str, bool] = {}
    type_base: dict[str, str] = {}

    for ct in root.findall(f"{_XS_NS}complexType"):
        n = ct.get("name")
        if not n:
            continue
        has_globals = False
        for ag in ct.iter(f"{_XS_NS}attributeGroup"):
            if ag.get("ref") == "GLOBALS":
                has_globals = True
                break
        type_has_globals[n] = has_globals
        for ext in ct.iter(f"{_XS_NS}extension"):
            base = ext.get("base")
            if base:
                type_base[n] = _local(base)
                break

    # Propagate GLOBALS up the extension chain until fixpoint.
    changed = True
    while changed:
        changed = False
        for n, base in type_base.items():
            if type_has_globals.get(base) and not type_has_globals.get(n):
                type_has_globals[n] = True
                changed = True

    elements: list[tuple[str, str, bool]] = []
    for el in root.findall(f"{_XS_NS}element"):
        name = el.get("name")
        if not name:
            continue
        type_ref = _local(el.get("type"))
        if not type_ref or not type_has_globals.get(type_ref):
            continue
        lower = name.lower()
        is_layout = lower in _DDI_C_LAYOUT_EXCLUDES
        elements.append((lower, type_ref, is_layout))

    return sorted(elements)


def _render_codebook_module(elements: list[tuple[str, str, bool]]) -> str:
    """Render the ``_generated/codebook.py`` module source."""
    header = (
        '"""Generated DDI-Codebook 2.6 schema metadata.\n'
        "\n"
        "Auto-generated from ``schemas/ddi-c/codebook.xsd`` by\n"
        "``scripts/generate_schema_definitions.py``. Do not edit by hand.\n"
        "\n"
        "Re-run::\n"
        "\n"
        "    python scripts/generate_schema_definitions.py\n"
        "\n"
        "to regenerate after changing the bundled XSDs.\n"
        '"""\n'
        "\n"
        "from typing import NamedTuple\n"
        "\n"
        "\n"
        "class CodebookElement(NamedTuple):\n"
        '    """A DDI-Codebook element whose type carries the GLOBALS attributeGroup.\n'
        "\n"
        "    ``tag`` is the lowercase element name as it appears in the\n"
        "    XML payload (the codebook loader dispatches by lowercase).\n"
        "    ``complex_type`` is the XSD complexType name. ``is_layout``\n"
        "    is True for CALS table / presentation markup that the runtime\n"
        "    skips for graph ingestion.\n"
        '    """\n'
        "\n"
        "    tag: str\n"
        "    complex_type: str\n"
        "    is_layout: bool\n"
        "\n"
        "\n"
    )

    block = "CODEBOOK_GENERATED_ELEMENTS: tuple[CodebookElement, ...] = (\n"
    for tag, ctype, is_layout in elements:
        block += (
            f'    CodebookElement(tag="{tag}", complex_type="{ctype}", is_layout={is_layout}),\n'
        )
    block += ")\n\n\n"

    footer = '__all__ = ["CODEBOOK_GENERATED_ELEMENTS", "CodebookElement"]\n'

    return header + block + footer


def _generate_codebook(write: bool) -> tuple[bool, str]:
    """Generate ``_generated/codebook.py``.

    Args:
        write: When False, only check that the committed file matches what
            the generator would produce and return drift information.

    Returns:
        ``(changed, message)`` -- ``changed`` is True if the on-disk file
        differs from generator output. ``message`` is a human-readable
        status line.
    """
    elements = _walk_codebook(SCHEMA_ENTRYPOINTS["codebook"])
    rendered = _ruff_format(_render_codebook_module(elements))

    target = GENERATED_DIR / "codebook.py"
    existing = target.read_text() if target.exists() else ""
    changed = existing != rendered

    in_scope = sum(1 for _, _, is_layout in elements if not is_layout)
    layout = sum(1 for _, _, is_layout in elements if is_layout)
    if write and changed:
        target.write_text(rendered)
        return changed, (
            f"wrote {target.relative_to(REPO_ROOT)}: "
            f"{in_scope} in-scope elements, {layout} layout-excluded"
        )
    if changed:
        return changed, f"DRIFT: {target.relative_to(REPO_ROOT)} would be regenerated"
    return changed, (
        f"{target.relative_to(REPO_ROOT)} already up to date "
        f"({in_scope} in-scope elements, {layout} layout-excluded)"
    )


def generate(check_only: bool = False) -> int:
    """Run the generator (or validate that it would be a no-op).

    Args:
        check_only: When True, do not write any files; instead, return a
            non-zero exit code if regeneration would change the committed
            artefacts. Used by CI and pre-commit.

    Returns:
        Process exit code (0 on success, 1 on failure or drift).
    """
    issues = _verify_assets()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1

    drift = False
    for emit in (_generate_cdi, _generate_lifecycle, _generate_codebook):
        changed, message = emit(write=not check_only)
        print(message)
        if check_only and changed:
            drift = True

    return 1 if drift else 0


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the committed _generated/ files are up to date.",
    )
    args = parser.parse_args()
    return generate(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

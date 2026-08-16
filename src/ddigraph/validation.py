"""Validate a DDI file against the XSD its flavor and version call for.

The package has always shipped the official DDI schemas -- 154 XSD files
across DDI-Codebook 2.6, DDI-Lifecycle 3.1/3.2/3.3 and DDI-CDI 1.0 -- but
only the build-time codegen ever read them. Nothing let a user ask the
question a data archivist asks first: *is this file even valid DDI?*

This does. It needs no new dependency: ``lxml`` is already required, and
its ``XMLSchema`` covers XSD 1.0, which is what the DDI schemas are
written in.

Validation is **opt-in**, and deliberately so. Published DDI is often
imperfect -- archives ship files that parse fine and load fine but do not
strictly validate -- and refusing to read them would make the package less
useful, not more. ``ddigraph load`` therefore keeps its forgiving
behaviour unless you ask for strictness with ``--validate``.

One wrinkle is worth knowing about, because it looks like a bug here and
is not. See :func:`_repair_codebook_annotations`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from ddigraph.logging import get_logger
from ddigraph.resources import schema_bundle_root

if TYPE_CHECKING:
    from lxml import etree as _etree

logger = get_logger(__name__)

#: XSD namespace, used when walking a schema document.
XS = "{http://www.w3.org/2001/XMLSchema}"

#: Entry-point schema per ``(flavor, version)``. ``None`` means the flavor
#: has a single shipped version.
_ENTRY_POINTS: dict[tuple[str, str | None], str] = {
    ("codebook", None): "ddi-c/codebook.xsd",
    ("lifecycle", "3_1"): "ddi/v3_1/instance_3_1.xsd",
    ("lifecycle", "3_2"): "ddi/v3_2/instance_3_2.xsd",
    ("lifecycle", "3_3"): "ddi/v3_3/instance_3_3.xsd",
    ("cdi", None): "ddi-cdi/xml-schema/ddi-cdi.xsd",
}

#: DDI-L declares its version in the namespace: ``ddi:instance:3_3``.
_LIFECYCLE_VERSION = re.compile(r"ddi:[a-z]+:(3_\d)")

#: Version used when a DDI-L file declares none we recognise. 3.3 is the
#: current release and a superset of the earlier two for our purposes.
DEFAULT_LIFECYCLE_VERSION = "3_3"


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """One schema violation.

    Attributes:
        line: 1-indexed line in the source document, or 0 if unknown.
        column: Column, or 0 if unknown.
        message: The parser's description of the violation.
    """

    line: int
    column: int
    message: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validating one file.

    Attributes:
        valid: True when the document satisfies the schema.
        flavor: The DDI flavor validated against.
        version: The flavor's version, where it has more than one.
        schema: Path of the entry-point XSD used.
        issues: Every violation found, in document order.
    """

    valid: bool
    flavor: str
    schema: Path
    version: str | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


class SchemaUnavailableError(RuntimeError):
    """Raised when no bundled schema covers a flavor or version."""


def _lifecycle_version(root: _etree._Element) -> str:
    """Return the DDI-L version a document declares, from its namespaces."""
    for uri in root.nsmap.values():
        if not uri:
            continue
        found = _LIFECYCLE_VERSION.search(uri)
        if found:
            return found.group(1)
    return DEFAULT_LIFECYCLE_VERSION


def schema_path(flavor: str, version: str | None = None) -> Path:
    """Return the entry-point XSD for a flavor.

    Args:
        flavor: ``"codebook"``, ``"lifecycle"`` or ``"cdi"``.
        version: DDI-L version such as ``"3_3"``. Ignored for the others.

    Returns:
        Path to the schema inside the bundle.

    Raises:
        SchemaUnavailableError: If no bundled schema matches.
    """
    key = (flavor, version if flavor == "lifecycle" else None)
    relative = _ENTRY_POINTS.get(key)
    if relative is None:
        known = sorted({name for name, _ in _ENTRY_POINTS})
        raise SchemaUnavailableError(
            f"No bundled schema for flavor {flavor!r} version {version!r}. "
            f"Known flavors: {', '.join(known)}"
        )

    path = schema_bundle_root() / relative
    if not path.is_file():
        raise SchemaUnavailableError(f"Bundled schema is missing from this install: {path}")
    return path


def _repair_codebook_annotations(tree: _etree._ElementTree) -> int:
    """Move ``xs:annotation`` to the front of every ``xs:attribute``.

    The DDI-Codebook 2.6 schema published by the DDI Alliance is not itself
    valid XSD. In 55 places an ``xs:attribute`` holds its ``xs:annotation``
    *after* its ``xs:simpleType``, while the XSD specification requires
    ``(annotation?, simpleType?)`` in that order. Every conforming parser
    rejects it -- ``lxml`` and ``xmlschema``, in both 1.0 and 1.1 modes --
    so without this the Codebook flavor could not be validated at all.

    The defect is upstream, not a packaging accident: the file's SHA-256
    matches ``schemas/manifest.json``, so it is exactly what the Alliance
    published. The repair is applied to the in-memory tree only; the file on
    disk stays byte-identical to upstream so the manifest keeps verifying.

    Reordering is safe because ``xs:annotation`` carries documentation and
    nothing else. Moving it changes what the schema *says* not at all.

    Args:
        tree: Parsed schema document, modified in place.

    Returns:
        How many annotations were moved.
    """
    moved = 0
    for attribute in tree.iter(f"{XS}attribute"):
        annotation = attribute.find(f"{XS}annotation")
        if annotation is not None and list(attribute).index(annotation) != 0:
            attribute.remove(annotation)
            attribute.insert(0, annotation)
            moved += 1
    return moved


@lru_cache(maxsize=8)
def _compiled_schema(path: Path, repair: bool) -> _etree.XMLSchema:
    """Compile a schema, cached: compiling costs up to a second."""
    from lxml import etree

    tree = etree.parse(str(path))

    if repair:
        moved = _repair_codebook_annotations(tree)
        if moved:
            logger.debug(
                "Reordered misplaced xs:annotation elements in the upstream schema",
                extra={"schema": str(path), "count": moved},
            )

    return etree.XMLSchema(tree)


def validate(
    source: str | Path,
    *,
    flavor: str | None = None,
    max_issues: int = 0,
) -> ValidationResult:
    """Validate a DDI file against the appropriate bundled XSD.

    Args:
        source: Path to a DDI XML file.
        flavor: Force a flavor instead of detecting it from the document.
        max_issues: Keep at most this many issues. ``0`` keeps all of them;
            a badly mismatched file can produce thousands.

    Returns:
        ValidationResult: Outcome, including every violation found.

    Raises:
        SchemaUnavailableError: If no bundled schema covers the flavor.
    """
    from lxml import etree

    from ddigraph.ingest.fragment_loader import detect_ddi_format

    path = Path(source)
    resolved_flavor = flavor or detect_ddi_format(str(path))

    document = etree.parse(str(path))
    root = document.getroot()

    version = _lifecycle_version(root) if resolved_flavor == "lifecycle" else None
    xsd = schema_path(resolved_flavor, version)
    schema = _compiled_schema(xsd, resolved_flavor == "codebook")

    valid = bool(schema.validate(document))
    issues = [
        ValidationIssue(line=entry.line or 0, column=entry.column or 0, message=entry.message)
        for entry in schema.error_log
    ]
    if max_issues:
        issues = issues[:max_issues]

    logger.info(
        "Validated against XSD",
        extra={
            "path": str(path),
            "flavor": resolved_flavor,
            "version": version,
            "valid": valid,
            "issues": len(issues),
        },
    )

    return ValidationResult(
        valid=valid,
        flavor=resolved_flavor,
        schema=xsd,
        version=version,
        issues=issues,
    )


__all__ = [
    "DEFAULT_LIFECYCLE_VERSION",
    "SchemaUnavailableError",
    "ValidationIssue",
    "ValidationResult",
    "schema_path",
    "validate",
]

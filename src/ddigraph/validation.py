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


class GraphParseError(ValueError):
    """Raised when an RDF file cannot be parsed, so there is no graph to check."""


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


# ---------------------------------------------------------------------------
# SHACL: is the *graph* the shape ddigraph claims to produce?
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class ShapeViolation:
    """One SHACL result.

    Attributes:
        focus_node: The subject that failed, as an IRI or blank-node id.
        path: The property the constraint is about, if it has one.
        constraint: The SHACL constraint component, e.g. ``MinCountConstraintComponent``.
        message: The validator's description of the failure.
        severity: ``Violation``, ``Warning`` or ``Info``.
        value: The offending value, where the constraint names one.
    """

    focus_node: str
    path: str | None
    constraint: str
    message: str
    severity: str = "Violation"
    value: str | None = None

    def __str__(self) -> str:
        where = f"{self.focus_node} {self.path}" if self.path else self.focus_node
        return f"{where}: {self.message}"


@dataclass(slots=True)
class ShapesResult:
    """Outcome of checking one graph against the SHACL shapes.

    Attributes:
        valid: True when the graph conforms.
        flavor: The flavor the shapes were scoped to, or ``None`` for all three.
        triples: Size of the data graph that was checked.
        total: How many results the validator reported, before truncation.
        issues: The results kept, sorted so a report is stable between runs.
    """

    valid: bool
    flavor: str | None
    triples: int
    total: int = 0
    issues: list[ShapeViolation] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def is_rdf_path(path: str | Path) -> bool:
    """Return True when a path names an RDF serialisation rather than DDI XML.

    Decided by extension, not by sniffing: Turtle and JSON-LD do not parse as
    XML, so sniffing would treat the serialisations of one graph differently.
    ``.xml`` is claimed by RDF/XML too, but DDI XML is the overwhelmingly
    common case, so it stays with the XML parsers.
    """
    from ddigraph.rdf.reader import EXTENSION_FORMATS

    suffix = Path(path).suffix.lower()
    return suffix in EXTENSION_FORMATS and suffix != ".xml"


def validate_shapes(
    source: str | Path,
    *,
    flavor: str | None = None,
    max_issues: int = 0,
) -> ShapesResult:
    """Check a graph against the SHACL shapes ddigraph derives from its schema.

    An RDF file (``.ttl``, ``.nt``, ``.jsonld``, ``.rdf``...) is checked as
    it is. A DDI XML file is first projected the way ``ddigraph export``
    would, so this answers "does what ddigraph makes of this file have the
    promised shape?" -- the question XSD validation cannot ask.

    Args:
        source: An RDF file, or a DDI XML file to project first.
        flavor: Scope the shapes to one flavor. For DDI XML it defaults to
            the detected flavor; for RDF, which does not record its flavor,
            it defaults to the shapes for all three.
        max_issues: Keep at most this many results. ``0`` keeps all of them.

    Returns:
        ShapesResult: Outcome, including every result kept.

    Raises:
        ImportError: If the ``[shacl]`` extra (``rdflib`` and ``pyshacl``)
            is not installed.
        GraphParseError: If an RDF file is not valid in its serialisation.
    """
    try:
        import pyshacl
        from rdflib import Graph
    except ImportError as exc:
        raise ImportError(
            "SHACL validation needs rdflib and pyshacl, which are optional. "
            'Install them with: pip install "ddigraph[shacl]"'
        ) from exc

    from ddigraph.rdf.shacl import shapes_graph

    path = Path(source)
    if is_rdf_path(path):
        from ddigraph.rdf.reader import EXTENSION_FORMATS

        rdf_format = EXTENSION_FORMATS[path.suffix.lower()]
        try:
            data = Graph().parse(str(path), format=rdf_format)
        # rdflib's parsers raise unrelated exception types (BadSyntax,
        # SAXParseException, JSONDecodeError...), so catch broadly and
        # report them as one thing: this file is not valid RDF.
        except Exception as exc:
            raise GraphParseError(f"Not valid {rdf_format}: {exc}") from exc
    else:
        from ddigraph.graph.view import iter_graph
        from ddigraph.ingest.fragment_loader import detect_ddi_format
        from ddigraph.rdf.writer import build_graph

        flavor = flavor or detect_ddi_format(str(path))
        data = build_graph(iter_graph(path, flavor=flavor))

    conforms, report, _text = pyshacl.validate(data, shacl_graph=shapes_graph(flavor=flavor))
    issues = sorted(
        _shape_violations(report),
        key=lambda issue: (issue.focus_node, issue.path or "", issue.constraint),
    )
    total = len(issues)
    if max_issues:
        issues = issues[:max_issues]

    logger.info(
        "Validated against SHACL shapes",
        extra={
            "path": str(path),
            "flavor": flavor,
            "valid": bool(conforms),
            "issues": total,
        },
    )

    return ShapesResult(
        valid=bool(conforms),
        flavor=flavor,
        triples=len(data),
        total=total,
        issues=issues,
    )


def _shape_violations(report: object) -> list[ShapeViolation]:
    """Read ``sh:ValidationResult`` nodes out of a pyshacl report graph.

    The report graph, not pyshacl's text rendering, is the stable interface:
    the text format changes between pyshacl releases.
    """
    from rdflib import RDF, Graph, Namespace, URIRef
    from rdflib.term import Node

    assert isinstance(report, Graph)
    sh = Namespace(SH_NAMESPACE)

    def one(subject: Node, predicate: URIRef) -> str | None:
        value = report.value(subject, predicate)
        return None if value is None else str(value)

    violations: list[ShapeViolation] = []
    for result in report.subjects(RDF.type, sh.ValidationResult):
        constraint = one(result, sh.sourceConstraintComponent) or ""
        severity = one(result, sh.resultSeverity) or f"{SH_NAMESPACE}Violation"
        violations.append(
            ShapeViolation(
                focus_node=one(result, sh.focusNode) or "",
                path=one(result, sh.resultPath),
                constraint=constraint.removeprefix(SH_NAMESPACE),
                message=one(result, sh.resultMessage) or "",
                severity=severity.removeprefix(SH_NAMESPACE),
                value=one(result, sh.value),
            )
        )
    return violations


#: The SHACL namespace, for reading reports.
SH_NAMESPACE = "http://www.w3.org/ns/shacl#"


__all__ = [
    "DEFAULT_LIFECYCLE_VERSION",
    "GraphParseError",
    "SchemaUnavailableError",
    "ShapeViolation",
    "ShapesResult",
    "ValidationIssue",
    "ValidationResult",
    "is_rdf_path",
    "schema_path",
    "validate",
    "validate_shapes",
]

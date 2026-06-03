"""Streaming DDI XML ingestion."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from inspect import isawaitable
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from lxml import etree  # type: ignore[import-untyped,unused-ignore]
from neo4j import AsyncDriver, Driver

from ddigraph.config import Settings
from ddigraph.logging import get_logger
from ddigraph.metrics import MetricsEmitter, NullMetrics
from ddigraph.paths import validate_readable_xml_path
from ddigraph.schema.adapter import GraphWriteAdapter
from ddigraph.schema.ddi_graph import DDIIngestGraph
from ddigraph.schema.neo4j_adapter import Neo4jGraphAdapter
from ddigraph.utils.chunking import as_dicts as _as_dicts
from ddigraph.utils.parsing import (
    close_iterparse_context,
    extract_reference_value,
    extract_references_by_suffix,
    get_all_child_text,
    get_child_text,
    get_text,
    strip_namespace,
)
from ddigraph.utils.retry import retry_transient

logger = get_logger(__name__)
DRY_RUN_MESSAGE = "DDI ingestion running in dry-run/validate-only mode; no data will be written"

# Lowercase tag names dispatched to :meth:`BatchBuilder.ingest_generic_identifiable`.
# These are DDI-Codebook concrete identifiables (elements whose type carries the
# GLOBALS attribute group) that do not warrant a bespoke record class.  They are
# captured as :class:`GenericIdentifiableRecord` entries so every concrete
# codebook element in ``schemas/ddi-c/codebook.xsd`` is accounted for while
# still letting bespoke parent handlers (e.g. ``stdyDscr``) read nested
# children after the generic capture has fired.
_GENERIC_IDENTIFIABLE_TAGS: frozenset[str] = frozenset(
    {
        "anlyinfo",
        "boundpoly",
        "catgry",
        "catlevel",
        "codinginstructions",
        "cohort",
        "controlledvocabused",
        "cubecoord",
        "dataaccs",
        "datacoll",
        "datadscr",
        "derivation",
        "developmentactivity",
        "dimensns",
        "diststmt",
        "dmns",
        "docsrc",
        "extlink",
        "filecitation",
        "filecommand",
        "filederivation",
        "filestrc",
        "filetxt",
        "frameunit",
        "geobndbox",
        "geomap",
        "invalrng",
        "link",
        "location",
        "locmap",
        "measure",
        "metadataaccs",
        "method",
        "othrstdymat",
        "physloc",
        "point",
        "polygon",
        "prodstmt",
        "range",
        "recdimnsn",
        "recgrp",
        "resource",
        "rspstmt",
        "serstmt",
        "setavail",
        "sourcecitation",
        "sources",
        "standard",
        "standardscompliance",
        "stdyinfo",
        "subject",
        "sumdscr",
        "targetsamplesize",
        "titlstmt",
        "usestmt",
        "valrng",
        "varrange",
        "verstmt",
    }
)


def normalize_dataset_id(dataset_id: str) -> str:
    """Strip whitespace and ensure dataset identifiers are non-empty.

    Args:
        dataset_id: User-provided dataset identifier, possibly padded with
            whitespace.

    Returns:
        A trimmed, non-empty dataset identifier.

    Raises:
        ValueError: If the identifier is empty after stripping whitespace.
    """
    normalized = dataset_id.strip()
    if not normalized:
        raise ValueError("dataset_id must be a non-empty string")
    return normalized


def _reusable_identifier(elem: etree._Element | None) -> dict[str, str | None]:
    """Extract reusable identifier fields regardless of namespace."""
    reusable_id = None
    reusable_version = None
    reusable_urn = None
    reusable_agency = None
    reusable_type_of_object = None

    if elem is not None:
        reusable_id = _first_text_local(elem, "ID") or elem.get("ID") or elem.get("id")
        reusable_version = _first_text_local(elem, "Version")
        reusable_urn = _first_text_local(elem, "URN")
        reusable_agency = _first_text_local(elem, "Agency")
        reusable_type_of_object = _first_text_local(elem, "TypeOfObject")

    return {
        "reusable_id": reusable_id,
        "reusable_version": reusable_version,
        "reusable_urn": reusable_urn,
        "reusable_agency": reusable_agency,
        "reusable_type_of_object": reusable_type_of_object,
    }


def _language(elem: etree._Element | None) -> str | None:
    """Return a best-effort language code from XML lang attributes or child tags."""
    if elem is None:
        return None

    lang = elem.get("{http://www.w3.org/XML/1998/namespace}lang")
    if isinstance(lang, str) and lang:
        return lang
    return _first_text_local(elem, "Language", "language")


def _textual_metadata(elem: etree._Element | None) -> dict[str, str | None]:
    """Capture common textual fields regardless of namespace."""
    if elem is None:
        return {
            "name": None,
            "label": None,
            "description": None,
            "rationale": None,
            "language": None,
        }

    name = _first_text_any(elem, "name") or _first_text_local(elem, "Name")
    label = _first_text_any(elem, "labl", "label") or _first_text_local(elem, "Label")
    description = _first_text_any(
        elem,
        "Description",
        "description",
        "Content",
        "content",
    ) or _text_or_none(elem)
    rationale = _first_text_local(elem, "Rationale") or _first_text_any(elem, "rationale")
    language = _language(elem)

    return {
        "name": name,
        "label": label,
        "description": description,
        "rationale": rationale,
        "language": language,
    }


def _common_metadata(elem: etree._Element | None, **_: object) -> dict[str, str | None]:
    """Extract shared DDI metadata attributes from an element."""
    reusable = _reusable_identifier(elem)
    urn = None
    agency = None
    version = None
    if elem is not None:
        urn = (
            elem.get("URN")
            or elem.get("urn")
            or _first_text_any(elem, "URN", "urn")
            or reusable.get("reusable_urn")
        )
        agency = (
            elem.get("agency")
            or elem.get("AGENCY")
            or _first_text_any(elem, "agency", "Agency")
            or reusable.get("reusable_agency")
        )
        version = (
            elem.get("version")
            or elem.get("VERSION")
            or _first_text_any(elem, "version", "Version")
            or reusable.get("reusable_version")
        )

    return {"urn": urn, "agency": agency, "version": version, **reusable}


def _question_text(elem: etree._Element | None) -> str | None:
    """Prefer literal question text with sensible fallbacks."""
    if elem is None:
        return None
    return _first_text_any(elem, "qstnLit", "qstnText", "labl") or _text_or_none(elem)


@dataclass(slots=True)
class DatasetRecord:
    """Top-level DDI dataset node that anchors every ingested record."""

    id: str
    name: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class StudyRecord:
    """A DDI study description (``<stdyDscr>``)."""

    dataset_id: str
    dataset_name: str | None
    study_id: str
    title: str | None
    abstract: str | None
    description: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    rationale: str | None = None
    language: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DataFileRecord:
    """A data file referenced by the study (``<fileDscr>``)."""

    dataset_id: str
    dataset_name: str | None
    file_id: str
    name: str | None
    uri: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class UniverseRecord:
    """The population a variable or study applies to."""

    dataset_id: str
    dataset_name: str | None
    universe_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    rationale: str | None = None
    language: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CodeSchemeRecord:
    """A code scheme that groups related categories."""

    dataset_id: str
    dataset_name: str | None
    code_scheme_id: str
    name: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    description: str | None = None
    language: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CategoryRecord:
    """A coded category / response value within a code scheme."""

    dataset_id: str
    dataset_name: str | None
    category_id: str
    label: str | None
    code: str | None
    code_scheme_id: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    description: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    rationale: str | None = None
    language: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QuestionRecord:
    """A survey question."""

    dataset_id: str
    dataset_name: str | None
    question_id: str
    text: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    external_references: list[str] = field(default_factory=list)
    control_construct_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QuestionItemRecord:
    """A single question item within a question, grid, or flow."""

    dataset_id: str
    dataset_name: str | None
    question_item_id: str
    text: str | None
    parent_question_id: str | None = None
    parent_grid_id: str | None = None
    parent_flow_id: str | None = None
    variable_id: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    external_references: list[str] = field(default_factory=list)
    control_construct_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConceptRecord:
    """A conceptual definition referenced by variables."""

    dataset_id: str
    dataset_name: str | None
    name: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class OrganizationRecord:
    """An organization referenced by the study."""

    dataset_id: str
    dataset_name: str | None
    organization_id: str
    name: str | None
    abbreviation: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class SeriesRecord:
    """A study series that the current study belongs to."""

    dataset_id: str
    dataset_name: str | None
    series_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GroupRecord:
    """A study group that the current study belongs to."""

    dataset_id: str
    dataset_name: str | None
    group_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class DataCollectionEventRecord:
    """A data collection event within the study."""

    dataset_id: str
    dataset_name: str | None
    event_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class LogicalRecord:
    """A logical record describing a row/record layout in a data file."""

    dataset_id: str
    dataset_name: str | None
    logical_record_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class PhysicalStructureRecord:
    """A physical data structure (record layout on disk)."""

    dataset_id: str
    dataset_name: str | None
    physical_structure_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class OtherMaterialRecord:
    """An external material referenced by the study."""

    dataset_id: str
    dataset_name: str | None
    material_id: str
    label: str | None
    uri: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class VarGroupRecord:
    """A variable group that aggregates related variables."""

    dataset_id: str
    dataset_name: str | None
    var_group_id: str
    label: str | None
    description: str | None
    variable_ids: list[str] = field(default_factory=list)
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class CategoryGroupRecord:
    """A category group that aggregates related categories."""

    dataset_id: str
    dataset_name: str | None
    category_group_id: str
    label: str | None
    description: str | None
    category_ids: list[str] = field(default_factory=list)
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class QuestionGridRecord:
    """A grid/matrix of related question items."""

    dataset_id: str
    dataset_name: str | None
    question_grid_id: str
    text: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    external_references: list[str] = field(default_factory=list)
    control_construct_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QuestionFlowRecord:
    """A branching flow of question items."""

    dataset_id: str
    dataset_name: str | None
    question_flow_id: str
    text: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    external_references: list[str] = field(default_factory=list)
    control_construct_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SamplingProcedureRecord:
    """A sampling procedure description."""

    dataset_id: str
    dataset_name: str | None
    sampling_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class WeightRecord:
    """A survey weight definition."""

    dataset_id: str
    dataset_name: str | None
    weight_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class RepresentationRecord:
    """A value representation (numeric, textual, coded, ...)."""

    dataset_id: str
    dataset_name: str | None
    representation_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class CodeListRecord:
    """A list of codes that variables may reference."""

    dataset_id: str
    dataset_name: str | None
    code_list_id: str
    label: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    description: str | None = None
    language: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MethodologyNoteRecord:
    """A methodology note attached to the study."""

    dataset_id: str
    dataset_name: str | None
    note_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class ProcessingEventRecord:
    """A data processing event."""

    dataset_id: str
    dataset_name: str | None
    processing_event_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class SoftwareRecord:
    """A software package used while producing the study."""

    dataset_id: str
    dataset_name: str | None
    software_id: str
    name: str | None
    version: str | None
    urn: str | None = None
    agency: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class AccessConditionRecord:
    """An access condition attached to the study."""

    dataset_id: str
    dataset_name: str | None
    access_condition_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class CitationRecord:
    """A bibliographic citation."""

    dataset_id: str
    dataset_name: str | None
    citation_id: str
    title: str | None
    bibliographic: str | None
    authors: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class CoverageRecord:
    """Temporal, spatial, or topical coverage metadata."""

    dataset_id: str
    dataset_name: str | None
    coverage_id: str
    coverage_type: str | None
    description: str | None
    start_date: str | None
    end_date: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class FundingRecord:
    """A funding / grant entry for the study."""

    dataset_id: str
    dataset_name: str | None
    funding_id: str
    agency: str | None
    grant_number: str | None
    urn: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class ContributorRoleRecord:
    """A contributor assigned a specific role in the study."""

    dataset_id: str
    dataset_name: str | None
    contributor_id: str
    name: str | None
    role: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class CollectionInstrumentRecord:
    """A data-collection instrument (questionnaire, schedule, ...)."""

    dataset_id: str
    dataset_name: str | None
    instrument_id: str
    label: str | None
    instrument_type: str | None
    element_type: str | None = None
    urn: str | None = None
    agency: str | None = None
    id: str | None = None
    version: str | None = None
    name: str | None = None
    description: str | None = None
    external_instrument_locations: list[str] = field(default_factory=list)
    control_construct_reference: str | None = None
    referenced_construct_id: str | None = None
    fielded_languages: list[str] = field(default_factory=list)
    development_results_references: list[str] = field(default_factory=list)
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class ControlConstructRecord:
    """A flow-control construct referenced by questions or instruments."""

    dataset_id: str
    dataset_name: str | None
    construct_id: str
    label: str | None
    construct_type: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class RepresentedVariableRecord:
    """A represented variable that binds a concept to a representation."""

    dataset_id: str
    dataset_name: str | None
    represented_variable_id: str
    label: str | None
    concept: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class ComparisonRecord:
    """A comparison between datasets, variables, or categories."""

    dataset_id: str
    dataset_name: str | None
    comparison_id: str
    description: str | None
    comparison_type: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class AccessPolicyRecord:
    """An access policy that governs the study's availability."""

    dataset_id: str
    dataset_name: str | None
    access_policy_id: str
    description: str | None
    policy_type: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


# =========================================================================
# DDI-C 2.6 Record Dataclasses
# =========================================================================


@dataclass(slots=True)
class NCubeRecord:
    """An N-dimensional data cube (DDI-C 2.6 nCube element)."""

    dataset_id: str
    dataset_name: str | None
    ncube_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class NCubeGroupRecord:
    """A grouping of N-Cubes (DDI-C 2.6 nCubeGrp element)."""

    dataset_id: str
    dataset_name: str | None
    ncube_group_id: str
    description: str | None
    ncube_ids: list[str] = field(default_factory=list)
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class DocumentDescriptionRecord:
    """Document description/provenance (DDI-C 2.6 docDscr element)."""

    dataset_id: str
    dataset_name: str | None
    doc_id: str
    title: str | None
    description: str | None
    producer: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class SampleFrameRecord:
    """Sampling frame description (DDI-C 2.6 sampleFrame element)."""

    dataset_id: str
    dataset_name: str | None
    sample_frame_id: str
    description: str | None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class QualityStatementRecord:
    """Quality assessment (DDI-C 2.6 qualityStatement element)."""

    dataset_id: str
    dataset_name: str | None
    quality_id: str
    description: str | None
    standard: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class StudyAuthorizationRecord:
    """Authorization records (DDI-C 2.6 studyAuthorization element)."""

    dataset_id: str
    dataset_name: str | None
    authorization_id: str
    description: str | None
    authorization_statement: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class StudyDevelopmentRecord:
    """Development activities (DDI-C 2.6 studyDevelopment element)."""

    dataset_id: str
    dataset_name: str | None
    development_id: str
    description: str | None
    activity_type: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class ExPostEvaluationRecord:
    """Post-collection evaluation (DDI-C 2.6 exPostEvaluation element)."""

    dataset_id: str
    dataset_name: str | None
    evaluation_id: str
    description: str | None
    completion_date: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class GenericIdentifiableRecord:
    """Generic identifiable DDI-Codebook element with no bespoke record type.

    Captures concrete codebook elements that carry an ID (via the GLOBALS attribute
    group) but do not warrant a dedicated record class. The ``element_tag`` field
    preserves the original codebook tag so downstream consumers can discriminate when
    needed.
    """

    dataset_id: str
    dataset_name: str | None
    identifiable_id: str
    element_tag: str
    description: str | None = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    label: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None


@dataclass(slots=True)
class VariableRecord:
    """A data variable captured in a file, produced from a question and concept."""

    dataset_id: str
    dataset_name: str | None
    variable_id: str
    label: str | None
    concept: str | None
    file_id: str | None
    question_id: str | None
    question_text: str | None
    universe_id: str | None
    category_ids: list[str] = field(default_factory=list)
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    name: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None
    reusable_id: str | None = None
    reusable_version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_type_of_object: str | None = None
    external_references: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DDIBatch:
    """Collection of parsed DDI entities held until flush to Neo4j.

    Attributes:
        dataset: Dataset metadata parsed from the source file.
        studies: Studies associated with the dataset.
        data_files: Physical data file descriptors.
        code_schemes: Code scheme definitions tied to categories.
        categories: Category nodes referenced by variables and questions.
        universes: Universe definitions covering variable applicability.
        concepts: Concepts associated with variables or questions.
        variables: Parsed variable definitions.
        questions: Question entities referenced by variables.
        question_items: Question item content parsed from DDI.
        organizations: Organizations involved in the dataset lifecycle.
        series_list: Series metadata related to the dataset.
        groups: Group records referencing subsets of the dataset.
        data_collection_events: Events associated with data collection.
        logical_records: Logical record definitions.
        physical_structures: Physical structure definitions.
        other_materials: Additional materials linked to the dataset.
        var_groups: Variable grouping information.
        category_groups: Category grouping information.
        question_grids: Parsed question grid records.
        question_flows: Question flow definitions.
        sampling_procedures: Sampling procedure descriptions.
        weights: Weight definitions associated with the dataset.
        representations: Representation metadata for variables.
        code_lists: Code lists referenced by representations.
        methodology_notes: Methodology notes parsed from the file.
        processing_events: Processing events captured in the dataset lifecycle.
        software: Software tools referenced in processing events.
        access_conditions: Access condition information.
        citations: Citation references recorded in the DDI.
        coverage: Coverage records including temporal or geographic scope.
        funding: Funding sources tied to the dataset.
        contributor_roles: Contributors and their roles.
        instruments: Collection instruments such as questionnaires.
        control_constructs: Control construct entities parsed from the DDI.
        represented_variables: Represented variable metadata.
        comparisons: Comparison records parsed from the source.
        access_policies: Access policy records related to archival metadata.
    """

    dataset: DatasetRecord
    studies: list[StudyRecord]
    data_files: list[DataFileRecord]
    code_schemes: list[CodeSchemeRecord]
    categories: list[CategoryRecord]
    universes: list[UniverseRecord]
    concepts: list[ConceptRecord]
    variables: list[VariableRecord]
    questions: list[QuestionRecord]
    question_items: list[QuestionItemRecord]
    organizations: list[OrganizationRecord]
    series_list: list[SeriesRecord]
    groups: list[GroupRecord]
    data_collection_events: list[DataCollectionEventRecord]
    logical_records: list[LogicalRecord]
    physical_structures: list[PhysicalStructureRecord]
    other_materials: list[OtherMaterialRecord]
    var_groups: list[VarGroupRecord]
    category_groups: list[CategoryGroupRecord]
    question_grids: list[QuestionGridRecord]
    question_flows: list[QuestionFlowRecord]
    sampling_procedures: list[SamplingProcedureRecord]
    weights: list[WeightRecord]
    representations: list[RepresentationRecord]
    code_lists: list[CodeListRecord]
    methodology_notes: list[MethodologyNoteRecord]
    processing_events: list[ProcessingEventRecord]
    software: list[SoftwareRecord]
    access_conditions: list[AccessConditionRecord]
    citations: list[CitationRecord]
    coverage: list[CoverageRecord]
    funding: list[FundingRecord]
    contributor_roles: list[ContributorRoleRecord]
    instruments: list[CollectionInstrumentRecord]
    control_constructs: list[ControlConstructRecord]
    represented_variables: list[RepresentedVariableRecord]
    comparisons: list[ComparisonRecord]
    access_policies: list[AccessPolicyRecord]
    # DDI-C 2.6 additions
    ncubes: list[NCubeRecord] = field(default_factory=list)
    ncube_groups: list[NCubeGroupRecord] = field(default_factory=list)
    document_descriptions: list[DocumentDescriptionRecord] = field(default_factory=list)
    sample_frames: list[SampleFrameRecord] = field(default_factory=list)
    quality_statements: list[QualityStatementRecord] = field(default_factory=list)
    study_authorizations: list[StudyAuthorizationRecord] = field(default_factory=list)
    study_developments: list[StudyDevelopmentRecord] = field(default_factory=list)
    ex_post_evaluations: list[ExPostEvaluationRecord] = field(default_factory=list)
    generic_identifiables: list[GenericIdentifiableRecord] = field(default_factory=list)

    def total_records(self) -> int:
        """Count all records contained in the batch.

        Returns:
            The total number of parsed entities currently held in the batch.
        """
        return sum(
            len(items)
            for items in (
                self.studies,
                self.data_files,
                self.code_schemes,
                self.categories,
                self.universes,
                self.concepts,
                self.variables,
                self.questions,
                self.question_items,
                self.organizations,
                self.series_list,
                self.groups,
                self.data_collection_events,
                self.logical_records,
                self.physical_structures,
                self.other_materials,
                self.var_groups,
                self.category_groups,
                self.question_grids,
                self.question_flows,
                self.sampling_procedures,
                self.weights,
                self.representations,
                self.code_lists,
                self.methodology_notes,
                self.processing_events,
                self.software,
                self.access_conditions,
                self.citations,
                self.coverage,
                self.funding,
                self.contributor_roles,
                self.instruments,
                self.control_constructs,
                self.represented_variables,
                self.comparisons,
                self.access_policies,
                self.ncubes,
                self.ncube_groups,
                self.document_descriptions,
                self.sample_frames,
                self.quality_statements,
                self.study_authorizations,
                self.study_developments,
                self.ex_post_evaluations,
                self.generic_identifiables,
            )
        )

    def as_dict(self) -> dict[str, object]:
        """Convert the batch into plain Python collections for serialization.

        Returns:
            A nested dictionary mirroring the structure expected by the ingest
            graph adapter.
        """
        return {
            "dataset": asdict(self.dataset),
            "studies": _as_dicts(self.studies),
            "data_files": _as_dicts(self.data_files),
            "code_schemes": _as_dicts(self.code_schemes),
            "categories": _as_dicts(self.categories),
            "universes": _as_dicts(self.universes),
            "concepts": _as_dicts(self.concepts),
            "variables": _as_dicts(self.variables),
            "questions": _as_dicts(self.questions),
            "question_items": _as_dicts(self.question_items),
            "organizations": _as_dicts(self.organizations),
            "series_list": _as_dicts(self.series_list),
            "groups": _as_dicts(self.groups),
            "data_collection_events": _as_dicts(self.data_collection_events),
            "logical_records": _as_dicts(self.logical_records),
            "physical_structures": _as_dicts(self.physical_structures),
            "other_materials": _as_dicts(self.other_materials),
            "var_groups": _as_dicts(self.var_groups),
            "category_groups": _as_dicts(self.category_groups),
            "question_grids": _as_dicts(self.question_grids),
            "question_flows": _as_dicts(self.question_flows),
            "sampling_procedures": _as_dicts(self.sampling_procedures),
            "weights": _as_dicts(self.weights),
            "representations": _as_dicts(self.representations),
            "code_lists": _as_dicts(self.code_lists),
            "methodology_notes": _as_dicts(self.methodology_notes),
            "processing_events": _as_dicts(self.processing_events),
            "software": _as_dicts(self.software),
            "access_conditions": _as_dicts(self.access_conditions),
            "citations": _as_dicts(self.citations),
            "coverage": _as_dicts(self.coverage),
            "funding": _as_dicts(self.funding),
            "contributor_roles": _as_dicts(self.contributor_roles),
            "instruments": _as_dicts(self.instruments),
            "control_constructs": _as_dicts(self.control_constructs),
            "represented_variables": _as_dicts(self.represented_variables),
            "comparisons": _as_dicts(self.comparisons),
            "access_policies": _as_dicts(self.access_policies),
            "ncubes": _as_dicts(self.ncubes),
            "ncube_groups": _as_dicts(self.ncube_groups),
            "document_descriptions": _as_dicts(self.document_descriptions),
            "sample_frames": _as_dicts(self.sample_frames),
            "quality_statements": _as_dicts(self.quality_statements),
            "study_authorizations": _as_dicts(self.study_authorizations),
            "study_developments": _as_dicts(self.study_developments),
            "ex_post_evaluations": _as_dicts(self.ex_post_evaluations),
            "generic_identifiables": _as_dicts(self.generic_identifiables),
        }


class DDILoader:
    """Stream DDI content into Neo4j using back-pressure aware chunking.

    Args:
        driver: Neo4j driver used to open write sessions.
        settings: Optional runtime settings; defaults to :class:`Settings` if not
            provided.
        metrics: Optional metrics emitter for ingest instrumentation.
        adapter: Optional graph adapter; defaults to
            :class:`ddigraph.schema.neo4j_adapter.Neo4jGraphAdapter`.
    """

    def __init__(
        self,
        driver: Driver | AsyncDriver,
        settings: Settings | None = None,
        metrics: MetricsEmitter | None = None,
        adapter: GraphWriteAdapter | None = None,
    ) -> None:
        self.driver = driver
        self.settings = settings or Settings()
        self.metrics = metrics or NullMetrics(namespace=self.settings.metrics_namespace)
        self.adapter = adapter or Neo4jGraphAdapter(driver, self.settings)

    async def load(
        self,
        path: Path | str,
        dataset_id: str,
        dataset_name: str | None = None,
        *,
        dry_run: bool | None = None,
        replace: bool = False,
    ) -> dict[str, int]:
        """Parse the DDI XML and persist variables to Neo4j.

        Args:
            path: Filesystem path to the input DDI XML.
            dataset_id: Identifier assigned to the ingested dataset.
            dataset_name: Optional human-readable dataset label.
            dry_run: If True, parse without writing; defaults to settings.dry_run
                when unset.
            replace: When True, purge existing data for the dataset before
                ingesting.

        Returns:
            A mapping of entity names to the total counts ingested.

        Raises:
            ValueError: If dataset identifiers are empty.
            Exception: Any error encountered during parsing or writes after retry
                handling completes.
        """
        dataset_id = normalize_dataset_id(dataset_id)
        xml_path = validate_readable_xml_path(path)

        effective_dry_run = self.settings.dry_run if dry_run is None else dry_run

        if effective_dry_run:
            logger.warning(
                DRY_RUN_MESSAGE,
                extra={"dataset_id": dataset_id},
            )

        if replace and effective_dry_run:
            logger.info(
                "Replace requested, but dry-run is active; skipping purge step",
                extra={"dataset_id": dataset_id},
            )

        if replace and not effective_dry_run:
            purge_result = self.adapter.purge_dataset(
                dataset_id,
                session_config={"database": self.settings.neo4j_database},
                transaction_config=(
                    {"timeout": self.settings.transaction_timeout}
                    if self.settings.transaction_timeout is not None
                    else None
                ),
            )
            if isawaitable(purge_result):
                await purge_result

        start = perf_counter()
        batch_stream = cast(
            DDIBatchStream,
            parse_ddi_batches(
                xml_path,
                dataset_id,
                dataset_name,
                self.settings.chunk_size,
                recover=not self.settings.strict_parsing,
                metrics=self.metrics,
            ),
        )

        try:
            queue: asyncio.Queue[DDIBatch | None] = asyncio.Queue(
                maxsize=self.settings.queue_maxsize
            )
            writer_concurrency = max(1, self.settings.writer_concurrency)
            writer_errors: list[BaseException] = []
            writer_error_event = asyncio.Event()

            logger.info(
                "DDI ingestion starting producer/consumer pipeline with queue maxsize %s "
                "and %s writer task(s)",
                self.settings.queue_maxsize,
                writer_concurrency,
                extra={
                    "dataset_id": dataset_id,
                    "queue_maxsize": self.settings.queue_maxsize,
                    "writer_concurrency": writer_concurrency,
                },
            )

            writer_tasks = [
                asyncio.create_task(
                    self._writer_worker(
                        queue,
                        effective_dry_run,
                        writer_error_event,
                        writer_errors,
                        worker_id=worker_id,
                    )
                )
                for worker_id in range(writer_concurrency)
            ]
            sentinels_sent = False
            try:
                for batch in batch_stream:
                    if writer_error_event.is_set():
                        break
                    await queue.put(batch)
                    self.metrics.increment("ingest.batches_queued")
                    if self.settings.batch_metrics:
                        self.metrics.observe("ingest.queue_depth", float(queue.qsize()))

                logger.info(
                    "DDI ingestion producer finished queuing batches",
                    extra={
                        "dataset_id": dataset_id,
                        "queue_depth": queue.qsize(),
                    },
                )
                for _ in range(writer_concurrency):
                    await queue.put(None)
                sentinels_sent = True
            finally:
                if not sentinels_sent:
                    for _ in range(writer_concurrency):
                        await queue.put(None)
                await queue.join()
                await asyncio.gather(*writer_tasks, return_exceptions=True)

            if writer_errors:
                raise writer_errors[0]
        except Exception:
            self.metrics.increment("ingest.failures")
            logger.exception(
                "DDI ingestion failed",
                extra={"dataset_id": dataset_id},
            )
            raise
        duration = perf_counter() - start
        totals = batch_stream.totals
        for name, count in totals.items():
            self.metrics.increment(f"ingest.total.{name}", count)
        self.metrics.observe("ingest.duration_seconds", duration)
        logger.info(
            "DDI ingestion finished with totals %s",
            totals,
            extra={
                "dataset_id": dataset_id,
                "duration_s": round(duration, 3),
                "totals": totals,
            },
        )
        return totals

    async def _write_batch(self, batch: DDIBatch) -> None:
        """Persist a batch of parsed entities with retry handling.

        Args:
            batch: Parsed entities ready to be written to Neo4j.

        Raises:
            TransientError: If all retry attempts fail.
        """
        if batch.total_records() == 0:
            return

        start = perf_counter()
        graph = DDIIngestGraph.from_ddi_batch(batch)
        session_config: dict[str, object] = {"database": self.settings.neo4j_database}
        if self.settings.session_timeout is not None:
            session_config["session_timeout"] = self.settings.session_timeout

        transaction_config: dict[str, object] | None = None
        if self.settings.transaction_timeout is not None:
            transaction_config = {"timeout": self.settings.transaction_timeout}

        async def _do_write() -> None:
            write_result = self.adapter.write_batch(
                graph,
                session_config=session_config,
                transaction_config=transaction_config,
            )
            if isawaitable(write_result):
                await write_result

        await retry_transient(
            _do_write,
            attempts=self.settings.write_retry_attempts,
            base_delay=self.settings.write_retry_base_delay,
            jitter=self.settings.write_retry_jitter,
            retry_metric="ingest.batch_write_retries",
            log_prefix="Batch write",
            log_extra={"dataset_id": batch.dataset.id},
            metrics=self.metrics,
        )

        duration = perf_counter() - start
        self._record_batch_metrics(batch, duration)

    async def _writer_worker(
        self,
        queue: asyncio.Queue[DDIBatch | None],
        dry_run: bool,
        error_event: asyncio.Event,
        errors: list[BaseException],
        *,
        worker_id: int,
    ) -> None:
        """Consume queued batches and persist them with optional dry-run handling."""
        while True:
            batch = await queue.get()
            try:
                if batch is None:
                    return
                self.metrics.increment("ingest.batches_dequeued")
                if self.settings.batch_metrics:
                    self.metrics.observe("ingest.queue_depth", float(queue.qsize()))
                if error_event.is_set():
                    continue
                if dry_run:
                    start_batch = perf_counter()
                    duration = perf_counter() - start_batch
                    self._record_batch_metrics(batch, duration)
                    continue
                try:
                    await self._write_batch(batch)
                except Exception as exc:
                    if not error_event.is_set():
                        errors.append(exc)
                        error_event.set()
                        logger.exception(
                            "DDI batch writer failed",
                            extra={
                                "dataset_id": batch.dataset.id,
                                "worker_id": worker_id,
                            },
                        )
            finally:
                queue.task_done()

    def _record_batch_metrics(self, batch: DDIBatch, duration: float) -> None:
        """Emit per-batch metrics when enabled.

        Args:
            batch: The ingested batch for which metrics are recorded.
            duration: Duration in seconds spent processing the batch.
        """
        self.metrics.increment("ingest.batches")
        if self.settings.batch_metrics:
            self.metrics.observe("ingest.batch_duration_seconds", duration)
            self.metrics.observe("ingest.batch_size", float(batch.total_records()))


class DDIBatchStream(Iterable[DDIBatch]):
    """Iterate over DDI XML and yield batches of parsed entities.

    Args:
        path: Path to the DDI XML payload.
        dataset_id: Dataset identifier applied to parsed entities.
        dataset_name: Optional human-readable dataset label.
        chunk_size: Maximum number of parsed records to include per batch.
        recover: Whether XML parsing should attempt to recover from errors.
        metrics: Optional metrics emitter for parse-time instrumentation.
    """

    def __init__(
        self,
        path: Path,
        dataset_id: str,
        dataset_name: str | None,
        chunk_size: int,
        *,
        recover: bool = True,
        metrics: MetricsEmitter | None = None,
    ) -> None:
        self.path = path
        self.dataset_id = normalize_dataset_id(dataset_id)
        self.dataset_name = dataset_name
        self.chunk_size = chunk_size
        self.recover = recover
        self.metrics = metrics or NullMetrics()
        self.builder = BatchBuilder(dataset_id, dataset_name, chunk_size)
        self.handlers: dict[str, Callable[[Any, str], None]] = self._build_handlers()
        # Tags dispatched to the generic-identifiable capture path.  These
        # elements are recorded but their subtree must remain intact because a
        # bespoke parent handler (e.g. ``stdyDscr`` -> ``_first_text(".//titl")``)
        # fires afterwards and expects to read nested children.
        self.generic_handler_tags: frozenset[str] = _GENERIC_IDENTIFIABLE_TAGS

    def __iter__(self) -> Iterator[DDIBatch]:
        """Parse the XML stream and yield batches as they become available."""
        with self.path.open("rb") as xml_file:
            context = etree.iterparse(
                xml_file,
                events=("end",),
                recover=self.recover,
                huge_tree=True,
                # Defence in depth against XXE on untrusted input.
                resolve_entities=False,
                load_dtd=False,
                no_network=True,
            )

            try:
                for _, elem in context:
                    tag = _strip_namespace(elem.tag)
                    tag_lower = tag.lower()
                    handled = False
                    generic = False
                    handler = self.handlers.get(tag_lower)
                    if handler:
                        handler(elem, tag)
                        handled = True
                        generic = tag_lower in self.generic_handler_tags
                    elif tag_lower in self.generic_handler_tags:
                        self.builder.ingest_generic_identifiable(elem, tag_lower)
                        handled = True
                        generic = True
                    elif tag_lower.endswith("construct"):
                        self.builder.ingest_control_construct(elem, construct_type=tag)
                        handled = True

                    maybe_batch = self.builder.flush_if_ready()
                    if maybe_batch:
                        yield maybe_batch

                    # Skip in-place clear when the element was captured through
                    # the generic path: an enclosing bespoke handler may still
                    # need to read nested children once its own end-event fires.
                    if handled and not generic:
                        elem.clear()
                        parent = elem.getparent()
                        if parent is not None:
                            while elem.getprevious() is not None:
                                del parent[0]

                final_batch = self.builder.finalize()
                if final_batch:
                    yield final_batch

                if self.recover and context.error_log:
                    self.metrics.increment("ingest.parse_errors", len(context.error_log))
                    for error in context.error_log:
                        logger.warning(
                            "Recovered DDI XML parse error",
                            extra={
                                "dataset_id": self.dataset_id,
                                "line": error.line,
                                "column": error.column,
                                "message": error.message,
                            },
                        )
            finally:
                close_iterparse_context(context)

    @property
    def totals(self) -> dict[str, int]:
        """Return aggregate totals tracked during iteration."""
        return self.builder.totals_summary()

    def _build_handlers(self) -> dict[str, Callable[[Any, str], None]]:
        """Register element handlers keyed by lowercase tag names."""
        builder = self.builder
        return {
            "var": lambda elem, _: builder.ingest_variable(elem),
            "variable": lambda elem, _: builder.ingest_variable(elem),
            "filedscr": lambda elem, _: builder.ingest_file(elem),
            "stdydscr": lambda elem, _: builder.ingest_study(elem),
            "catgryscheme": lambda elem, _: builder.ingest_code_scheme(elem),
            "categoryscheme": lambda elem, _: builder.ingest_code_scheme(elem),
            "producer": lambda elem, _: builder.ingest_organization(elem),
            "distrbtr": lambda elem, _: builder.ingest_organization(elem),
            "org": lambda elem, _: builder.ingest_organization(elem),
            "organization": lambda elem, _: builder.ingest_organization(elem),
            "qstn": lambda elem, _: builder.ingest_question(elem),
            "question": lambda elem, _: builder.ingest_question(elem),
            "sername": lambda elem, _: builder.ingest_series(elem),
            "series": lambda elem, _: builder.ingest_series(elem),
            "group": lambda elem, _: builder.ingest_group(elem),
            "colldate": lambda elem, _: builder.ingest_data_collection_event(elem),
            "datacollectionevent": lambda elem, _: builder.ingest_data_collection_event(elem),
            "qstnitem": lambda elem, _: builder.ingest_question_item(elem),
            "questionitem": lambda elem, _: builder.ingest_question_item(elem),
            "logicalrecord": lambda elem, _: builder.ingest_logical_record(elem),
            "physicalstructure": lambda elem, _: builder.ingest_physical_structure(elem),
            "othermat": lambda elem, _: builder.ingest_other_material(elem),
            "othermaterial": lambda elem, _: builder.ingest_other_material(elem),
            "vargrp": lambda elem, _: builder.ingest_var_group(elem),
            "vargroup": lambda elem, _: builder.ingest_var_group(elem),
            "catgrygrp": lambda elem, _: builder.ingest_category_group(elem),
            "categorygroup": lambda elem, _: builder.ingest_category_group(elem),
            "qstngrid": lambda elem, _: builder.ingest_question_grid(elem),
            "questiongrid": lambda elem, _: builder.ingest_question_grid(elem),
            "qstnflow": lambda elem, _: builder.ingest_question_flow(elem),
            "questionflow": lambda elem, _: builder.ingest_question_flow(elem),
            "sampproc": lambda elem, _: builder.ingest_sampling_procedure(elem),
            "samplingprocedure": lambda elem, _: builder.ingest_sampling_procedure(elem),
            "weight": lambda elem, _: builder.ingest_weight(elem),
            "representation": lambda elem, _: builder.ingest_representation(elem),
            "codelist": lambda elem, _: builder.ingest_code_list(elem),
            "methodology": lambda elem, _: builder.ingest_methodology(elem),
            "processingevent": lambda elem, _: builder.ingest_processing_event(elem),
            "software": lambda elem, _: builder.ingest_software(elem),
            "accessconditions": lambda elem, _: builder.ingest_access_condition(elem),
            "citation": lambda elem, _: builder.ingest_citation(elem),
            "bibliographiccitation": lambda elem, _: builder.ingest_citation(elem),
            "biblcit": lambda elem, _: builder.ingest_citation(elem),
            "concept": lambda elem, _: builder.ingest_concept(elem),
            "coverage": lambda elem, tag: builder.ingest_coverage(elem, coverage_type=tag),
            "geogcover": lambda elem, tag: builder.ingest_coverage(elem, coverage_type=tag),
            "geographiccoverage": lambda elem, tag: builder.ingest_coverage(
                elem, coverage_type=tag
            ),
            "temporalcoverage": lambda elem, tag: builder.ingest_coverage(elem, coverage_type=tag),
            "timeprd": lambda elem, tag: builder.ingest_coverage(elem, coverage_type=tag),
            "topicalcoverage": lambda elem, tag: builder.ingest_coverage(elem, coverage_type=tag),
            "nation": lambda elem, tag: builder.ingest_coverage(elem, coverage_type=tag),
            "fundag": lambda elem, _: builder.ingest_funding(elem),
            "funding": lambda elem, _: builder.ingest_funding(elem),
            "fundinginformation": lambda elem, _: builder.ingest_funding(elem),
            "contributor": lambda elem, _: builder.ingest_contributor_role(elem),
            "authenty": lambda elem, _: builder.ingest_contributor_role(elem),
            "respstmt": lambda elem, _: builder.ingest_contributor_role(elem),
            "instrument": lambda elem, tag: builder.ingest_collection_instrument(
                elem, instrument_type=tag
            ),
            "collectioninstrument": lambda elem, tag: builder.ingest_collection_instrument(
                elem, instrument_type=tag
            ),
            "qstnnaire": lambda elem, tag: builder.ingest_collection_instrument(
                elem, instrument_type=tag
            ),
            "questionnaire": lambda elem, tag: builder.ingest_collection_instrument(
                elem, instrument_type=tag
            ),
            "sequence": lambda elem, tag: builder.ingest_control_construct(
                elem, construct_type=tag
            ),
            "loop": lambda elem, tag: builder.ingest_control_construct(elem, construct_type=tag),
            "ifthenelse": lambda elem, tag: builder.ingest_control_construct(
                elem, construct_type=tag
            ),
            "repeatuntil": lambda elem, tag: builder.ingest_control_construct(
                elem, construct_type=tag
            ),
            "repeatwhile": lambda elem, tag: builder.ingest_control_construct(
                elem, construct_type=tag
            ),
            "statementitem": lambda elem, tag: builder.ingest_control_construct(
                elem, construct_type=tag
            ),
            "computationitem": lambda elem, tag: builder.ingest_control_construct(
                elem, construct_type=tag
            ),
            "universe": lambda elem, _: builder.ingest_universe(elem),
            "representedvariable": lambda elem, _: builder.ingest_represented_variable(elem),
            "repvar": lambda elem, _: builder.ingest_represented_variable(elem),
            "comparison": lambda elem, tag: builder.ingest_comparison(elem, comparison_type=tag),
            "comparisoninformation": lambda elem, tag: builder.ingest_comparison(
                elem, comparison_type=tag
            ),
            "accesspolicy": lambda elem, tag: builder.ingest_access_policy(elem, policy_type=tag),
            "archive": lambda elem, tag: builder.ingest_access_policy(elem, policy_type=tag),
            # DDI-C 2.6 elements
            "ncube": lambda elem, _: builder.ingest_ncube(elem),
            "ncubegrp": lambda elem, _: builder.ingest_ncube_group(elem),
            "docdscr": lambda elem, _: builder.ingest_document_description(elem),
            "documentdescription": lambda elem, _: builder.ingest_document_description(elem),
            "sampleframe": lambda elem, _: builder.ingest_sample_frame(elem),
            "qualitystatement": lambda elem, _: builder.ingest_quality_statement(elem),
            "qualitystmt": lambda elem, _: builder.ingest_quality_statement(elem),
            "studyauthorization": lambda elem, _: builder.ingest_study_authorization(elem),
            "studydevelopment": lambda elem, _: builder.ingest_study_development(elem),
            "expostevaluation": lambda elem, _: builder.ingest_ex_post_evaluation(elem),
            "exposteval": lambda elem, _: builder.ingest_ex_post_evaluation(elem),
        }


def parse_ddi_batches(
    path: Path,
    dataset_id: str,
    dataset_name: str | None,
    chunk_size: int,
    *,
    recover: bool = True,
    metrics: MetricsEmitter | None = None,
) -> Iterable[DDIBatch]:
    """Stream batched DDI nodes using iterparse to bound memory.

    Args:
        path: Filesystem path to the DDI XML payload.
        dataset_id: Identifier applied to each parsed entity.
        dataset_name: Optional human-readable dataset label.
        chunk_size: Maximum number of records to collect before yielding a batch.
        recover: Whether XML parsing should attempt to recover from syntax
            errors.
        metrics: Optional metrics emitter for parse-time instrumentation.

    Returns:
        An iterable that yields :class:`DDIBatch` instances as they are parsed.
    """
    dataset_id = normalize_dataset_id(dataset_id)
    return DDIBatchStream(
        path,
        dataset_id,
        dataset_name,
        chunk_size,
        recover=recover,
        metrics=metrics,
    )


def parse_ddi_variables(
    path: Path,
    dataset_id: str,
    dataset_name: str | None,
    chunk_size: int,
    *,
    recover: bool = True,
    metrics: MetricsEmitter | None = None,
) -> Iterable[list[VariableRecord]]:
    """Compatibility wrapper yielding only variable batches.

    Args:
        path: Filesystem path to the DDI XML payload.
        dataset_id: Identifier applied to each parsed variable.
        dataset_name: Optional human-readable dataset label.
        chunk_size: Maximum number of records to collect before yielding a batch.
        recover: Whether XML parsing should attempt to recover from syntax
            errors.
        metrics: Optional metrics emitter for parse-time instrumentation.

    Returns:
        An iterable that yields lists of :class:`VariableRecord` objects.
    """
    for batch in parse_ddi_batches(
        path,
        dataset_id,
        dataset_name,
        chunk_size,
        recover=recover,
        metrics=metrics,
    ):
        if batch.variables:
            yield batch.variables


class BatchBuilder:
    """Accumulate parsed DDI records until the chunk threshold is met.

    Args:
        dataset_id: Dataset identifier applied to each parsed entity.
        dataset_name: Optional human-readable dataset label.
        chunk_size: Maximum number of records to collect before yielding a
            :class:`DDIBatch`.
    """

    def __init__(self, dataset_id: str, dataset_name: str | None, chunk_size: int) -> None:
        self.dataset = DatasetRecord(
            id=dataset_id,
            name=dataset_name,
            label=dataset_name,
        )
        self.chunk_size = chunk_size
        self.dataset_name = dataset_name
        self.dataset_id = dataset_id
        self.totals: dict[str, int] = {}
        self.variable_index = 0
        self.universe_index = 0
        self.concept_index = 0
        self.organization_index = 0
        self.series_index = 0
        self.group_index = 0
        self.collection_event_index = 0
        self.logical_record_index = 0
        self.physical_structure_index = 0
        self.other_material_index = 0
        self.var_group_index = 0
        self.category_group_index = 0
        self.question_grid_index = 0
        self.question_flow_index = 0
        self.sampling_index = 0
        self.weight_index = 0
        self.representation_index = 0
        self.code_list_index = 0
        self.method_note_index = 0
        self.processing_event_index = 0
        self.software_index = 0
        self.access_condition_index = 0
        self.citation_index = 0
        self.coverage_index = 0
        self.funding_index = 0
        self.contributor_index = 0
        self.instrument_index = 0
        self.construct_index = 0
        self.represented_variable_index = 0
        self.comparison_index = 0
        self.access_policy_index = 0
        self.question_index = 0
        # DDI-C 2.6 indexes
        self.ncube_index = 0
        self.ncube_group_index = 0
        self.doc_description_index = 0
        self.sample_frame_index = 0
        self.quality_statement_index = 0
        self.study_authorization_index = 0
        self.study_development_index = 0
        self.ex_post_evaluation_index = 0
        self.generic_identifiable_index = 0
        self._init_totals()
        self._reset()
        self.seen_categories: set[str] = set()
        self.seen_code_schemes: set[str] = set()
        self.seen_universes: set[str] = set()
        self.seen_concepts: set[str] = set()
        self.seen_questions: set[str] = set()
        self.seen_question_items: set[str] = set()
        self.seen_files: set[str] = set()
        self.seen_studies: set[str] = set()
        self.seen_variable_ids: set[str] = set()
        self.seen_organizations: set[str] = set()
        self.seen_series: set[str] = set()
        self.seen_groups: set[str] = set()
        self.seen_collection_events: set[str] = set()
        self.seen_logical_records: set[str] = set()
        self.seen_physical_structures: set[str] = set()
        self.seen_materials: set[str] = set()
        self.seen_var_groups: set[str] = set()
        self.seen_category_groups: set[str] = set()
        self.seen_question_grids: set[str] = set()
        self.seen_question_flows: set[str] = set()
        self.seen_sampling: set[str] = set()
        self.seen_weights: set[str] = set()
        self.seen_representations: set[str] = set()
        self.seen_code_lists: set[str] = set()
        self.seen_method_notes: set[str] = set()
        self.seen_processing_events: set[str] = set()
        self.seen_software: set[str] = set()
        self.seen_access_conditions: set[str] = set()
        self.seen_citations: set[str] = set()
        self.seen_coverage: set[str] = set()
        self.seen_funding: set[str] = set()
        self.seen_contributors: set[str] = set()
        self.seen_instruments: set[str] = set()
        self.seen_constructs: set[str] = set()
        self.seen_represented_variables: set[str] = set()
        self.seen_comparisons: set[str] = set()
        self.seen_access_policies: set[str] = set()
        # DDI-C 2.6 seen-sets
        self.seen_ncubes: set[str] = set()
        self.seen_ncube_groups: set[str] = set()
        self.seen_doc_descriptions: set[str] = set()
        self.seen_sample_frames: set[str] = set()
        self.seen_quality_statements: set[str] = set()
        self.seen_study_authorizations: set[str] = set()
        self.seen_study_developments: set[str] = set()
        self.seen_ex_post_evaluations: set[str] = set()
        self.seen_generic_identifiables: set[str] = set()

    def _init_totals(self) -> None:
        self.totals = {
            "studies": 0,
            "data_files": 0,
            "code_schemes": 0,
            "categories": 0,
            "universes": 0,
            "concepts": 0,
            "variables": 0,
            "questions": 0,
            "question_items": 0,
            "organizations": 0,
            "series_list": 0,
            "groups": 0,
            "data_collection_events": 0,
            "logical_records": 0,
            "physical_structures": 0,
            "other_materials": 0,
            "var_groups": 0,
            "category_groups": 0,
            "question_grids": 0,
            "question_flows": 0,
            "sampling_procedures": 0,
            "weights": 0,
            "representations": 0,
            "code_lists": 0,
            "methodology_notes": 0,
            "processing_events": 0,
            "software": 0,
            "access_conditions": 0,
            "citations": 0,
            "coverage": 0,
            "funding": 0,
            "contributor_roles": 0,
            "instruments": 0,
            "control_constructs": 0,
            "represented_variables": 0,
            "comparisons": 0,
            "access_policies": 0,
            # DDI-C 2.6
            "ncubes": 0,
            "ncube_groups": 0,
            "document_descriptions": 0,
            "sample_frames": 0,
            "quality_statements": 0,
            "study_authorizations": 0,
            "study_developments": 0,
            "ex_post_evaluations": 0,
            "generic_identifiables": 0,
            "batches": 0,
        }

    def _increment_total(self, name: str, amount: int = 1) -> None:
        self.totals[name] = self.totals.get(name, 0) + amount

    def _append_and_count(self, collection: list[Any], record: Any, name: str) -> None:
        collection.append(record)
        self._increment_total(name)

    @staticmethod
    def _claim_id(dedup_set: set[str], identifier: str) -> bool:
        """Reserve an identifier in ``dedup_set``.

        Returns True if the identifier was previously unseen (and is now
        recorded), False if the caller should treat the element as a
        duplicate and skip it. Replaces the three-line ``if id in set:
        return / set.add(id)`` pattern that occurred in 30+ ``ingest_*``
        methods.
        """
        if identifier in dedup_set:
            return False
        dedup_set.add(identifier)
        return True

    def _run_composition(
        self,
        method_name: str,
        elem: etree._Element,
        *,
        extra: dict[str, object] | None = None,
    ) -> None:
        """Execute a declarative ``CompositionSpec`` for a flat handler.

        Replaces the near-identical body of a flat ``ingest_*`` method
        (resolve id, dedup, extract a few fields, append). The spec is
        looked up by the calling method's name in
        ``_composition_specs.SPECS``. Behaviour is intentionally
        byte-identical to the hand-written handler -- the codebook
        snapshot test is the gate.

        Args:
            method_name: The ``ingest_*`` method name (the SPECS key).
            elem: The XML element to ingest.
            extra: Pre-computed record kwargs the caller supplies that
                cannot come from the element alone (e.g. the
                per-dispatch-tag ``coverage_type`` literal). Merged at
                the same precedence as declared ``fields`` -- after them
                and before the metadata splat.
        """
        from ddigraph.ingest._composition_specs import SPECS

        spec = SPECS[method_name]
        record_cls = globals()[spec.record]

        if spec.id_slug is None:
            record_id = _get_identifier(elem)
            if not record_id:
                return
        elif spec.id_mode == "lazy":
            record_id = _get_identifier(elem)
            if not record_id:
                counter = getattr(self, spec.counter) + 1
                setattr(self, spec.counter, counter)
                record_id = f"{self.dataset_id}:{spec.id_slug}_{counter}"
        else:
            counter = getattr(self, spec.counter) + 1
            setattr(self, spec.counter, counter)
            fallback = f"{self.dataset_id}:{spec.id_slug}_{counter}"
            record_id = _get_identifier(elem, default=fallback) or fallback

        dedup_set = getattr(self, spec.dedup)
        if not self._claim_id(dedup_set, record_id):
            return

        kwargs: dict[str, Any] = {
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            spec.id_field: record_id,
        }
        computed: dict[str, object] = {}
        for fld in spec.fields:
            if fld.alias is not None:
                value: object = computed[fld.alias]
            elif fld.has_const:
                value = fld.const
            else:
                assert fld.select is not None  # spec invariant
                value = fld.select(elem)
            computed[fld.name] = value
            kwargs[fld.name] = value

        if extra:
            kwargs.update(extra)

        if spec.textual_fields:
            partial = _textual_metadata(elem)
            for key in spec.textual_fields:
                kwargs[key] = partial[key]

        if spec.splat_textual:
            textual = _textual_metadata(elem)
            fallback_field = spec.textual_label_fallback
            if fallback_field is not None and textual["label"] is None:
                assert fallback_field.select is not None
                fallback_value = fallback_field.select(elem)
                textual["label"] = fallback_value if isinstance(fallback_value, str) else None
            kwargs.update(textual)

        if spec.splat_metadata:
            meta = _common_metadata(elem)
            for drop in spec.metadata_drop:
                meta.pop(drop, None)
            kwargs.update(meta)

        self._append_and_count(
            getattr(self, spec.collection),
            record_cls(**kwargs),
            spec.collection,
        )

    def _reset(self) -> None:
        self.studies: list[StudyRecord] = []
        self.data_files: list[DataFileRecord] = []
        self.code_schemes: list[CodeSchemeRecord] = []
        self.categories: list[CategoryRecord] = []
        self.universes: list[UniverseRecord] = []
        self.concepts: list[ConceptRecord] = []
        self.variables: list[VariableRecord] = []
        self.questions: list[QuestionRecord] = []
        self.question_items: list[QuestionItemRecord] = []
        self.organizations: list[OrganizationRecord] = []
        self.series_list: list[SeriesRecord] = []
        self.groups: list[GroupRecord] = []
        self.data_collection_events: list[DataCollectionEventRecord] = []
        self.logical_records: list[LogicalRecord] = []
        self.physical_structures: list[PhysicalStructureRecord] = []
        self.other_materials: list[OtherMaterialRecord] = []
        self.var_groups: list[VarGroupRecord] = []
        self.category_groups: list[CategoryGroupRecord] = []
        self.question_grids: list[QuestionGridRecord] = []
        self.question_flows: list[QuestionFlowRecord] = []
        self.sampling_procedures: list[SamplingProcedureRecord] = []
        self.weights: list[WeightRecord] = []
        self.representations: list[RepresentationRecord] = []
        self.code_lists: list[CodeListRecord] = []
        self.methodology_notes: list[MethodologyNoteRecord] = []
        self.processing_events: list[ProcessingEventRecord] = []
        self.software: list[SoftwareRecord] = []
        self.access_conditions: list[AccessConditionRecord] = []
        self.citations: list[CitationRecord] = []
        self.coverage: list[CoverageRecord] = []
        self.funding: list[FundingRecord] = []
        self.contributor_roles: list[ContributorRoleRecord] = []
        self.instruments: list[CollectionInstrumentRecord] = []
        self.control_constructs: list[ControlConstructRecord] = []
        self.represented_variables: list[RepresentedVariableRecord] = []
        self.comparisons: list[ComparisonRecord] = []
        self.access_policies: list[AccessPolicyRecord] = []
        # DDI-C 2.6
        self.ncubes: list[NCubeRecord] = []
        self.ncube_groups: list[NCubeGroupRecord] = []
        self.document_descriptions: list[DocumentDescriptionRecord] = []
        self.sample_frames: list[SampleFrameRecord] = []
        self.quality_statements: list[QualityStatementRecord] = []
        self.study_authorizations: list[StudyAuthorizationRecord] = []
        self.study_developments: list[StudyDevelopmentRecord] = []
        self.ex_post_evaluations: list[ExPostEvaluationRecord] = []
        self.generic_identifiables: list[GenericIdentifiableRecord] = []

    def ingest_study(self, elem: etree._Element) -> None:
        """Ingest a study description element and record it on the batch.

        Args:
            elem: XML element carrying the study description metadata.
        """
        study_id = _get_identifier(elem, default=self.dataset_id) or self.dataset_id
        if not self._claim_id(self.seen_studies, study_id):
            return
        title = _first_text(elem, ".//titl") or next(
            (citation.title for citation in reversed(self.citations) if citation.title), None
        )
        abstract = _first_text(elem, ".//abstract")
        textual = _textual_metadata(elem)
        if textual["label"] is None:
            textual["label"] = title
        if textual["name"] is None:
            textual["name"] = title
        description = textual["description"] or abstract
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.studies,
            StudyRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                study_id=study_id,
                title=title,
                abstract=abstract,
                description=description,
                name=textual["name"],
                label=textual["label"],
                rationale=textual["rationale"],
                language=textual["language"],
                external_references=_reference_values_by_suffix(elem, "Reference"),
                **metadata,
            ),
            "studies",
        )
        for universe in elem.findall(".//universe"):
            self._ingest_universe(universe, fallback_prefix=study_id)
        for series in elem.findall(".//serName"):
            self.ingest_series(series)
        for group in elem.findall(".//group"):
            self.ingest_group(group)
        for event in elem.findall(".//collDate"):
            self.ingest_data_collection_event(event)

    def ingest_file(self, elem: etree._Element) -> None:
        """Ingest a data file element and record it on the batch.

        Args:
            elem: XML element carrying the data file metadata.
        """
        self._run_composition("ingest_file", elem)

    def ingest_code_scheme(self, elem: etree._Element) -> None:
        """Ingest a code scheme element and record it on the batch.

        Args:
            elem: XML element carrying the code scheme metadata.
        """
        scheme_id = _get_identifier(elem)
        if scheme_id and scheme_id not in self.seen_code_schemes:
            self.seen_code_schemes.add(scheme_id)
            label = _first_text(elem, "labl")
            textual = _textual_metadata(elem)
            if textual["label"] is None:
                textual["label"] = label
            if textual["name"] is None:
                textual["name"] = label
            metadata = _common_metadata(elem)
            self._append_and_count(
                self.code_schemes,
                CodeSchemeRecord(
                    dataset_id=self.dataset_id,
                    dataset_name=self.dataset_name,
                    code_scheme_id=scheme_id,
                    name=textual["name"],
                    label=textual["label"],
                    description=textual["description"],
                    language=textual["language"],
                    external_references=_reference_values_by_suffix(elem, "Reference"),
                    **metadata,
                ),
                "code_schemes",
            )

        for category in elem.findall(".//catgry") + elem.findall(".//Category"):
            self._ingest_category(category, code_scheme_id=scheme_id)

    def ingest_question(self, elem: etree._Element) -> None:
        """Ingest a question element and record it on the batch.

        Args:
            elem: XML element carrying the question metadata.
        """
        parent = elem.getparent()
        default_question_id: str | None = None
        if parent is not None:
            parent_tag_lower = _strip_namespace(parent.tag).lower()
            parent_id = _get_identifier(parent, default=None)
            if parent_tag_lower in {
                "var",
                "variable",
                "qstngrid",
                "questiongrid",
                "qstnflow",
                "questionflow",
            }:
                default_question_id = f"{parent_id}:question" if parent_id else None

        question_id = _get_identifier(elem, default=default_question_id)
        if question_id is None:
            self.question_index += 1
            question_id = f"{self.dataset_id}:question_{self.question_index}"
        if not self._claim_id(self.seen_questions, question_id):
            return

        text = _question_text(elem)
        textual = _textual_metadata(elem)
        if textual["label"] is None:
            textual["label"] = _first_text(elem, "labl") or text
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.questions,
            QuestionRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                question_id=question_id,
                text=text,
                name=textual["name"],
                label=textual["label"],
                description=textual["description"],
                rationale=textual["rationale"],
                language=textual["language"],
                external_references=_reference_values_by_suffix(elem, "Reference"),
                control_construct_references=_reference_values_by_suffix(
                    elem, "ControlConstructReference"
                ),
                **metadata,
            ),
            "questions",
        )

    def ingest_variable(self, elem: etree._Element) -> None:
        """Ingest a variable element and record it on the batch.

        Args:
            elem: XML element carrying the variable metadata.
        """
        self.variable_index += 1
        raw_variable_id = _get_identifier(elem)
        variable_id = raw_variable_id or f"{self.dataset_id}:var_{self.variable_index}"
        if variable_id in self.seen_variable_ids:
            raise ValueError(
                "Duplicate variable ID "
                f"'{variable_id}' encountered at position {self.variable_index}"
            )
        self.seen_variable_ids.add(variable_id)
        label = _first_text(elem, "labl")
        concept = _first_text(elem, "concept") or _first_text(elem, "catgry//labl")
        question_elem = elem.find("qstn")
        question_text = _question_text(question_elem)
        question_id = None
        if question_elem is not None:
            question_id = _get_identifier(question_elem, default=f"{variable_id}:question")
            if question_id and question_id not in self.seen_questions:
                self.seen_questions.add(question_id)
                question_textual = _textual_metadata(question_elem)
                if question_textual["label"] is None:
                    question_textual["label"] = question_text
                question_metadata = _common_metadata(question_elem)
                self._append_and_count(
                    self.questions,
                    QuestionRecord(
                        dataset_id=self.dataset_id,
                        dataset_name=self.dataset_name,
                        question_id=question_id,
                        text=question_text,
                        name=question_textual["name"],
                        label=question_textual["label"],
                        description=question_textual["description"],
                        rationale=question_textual["rationale"],
                        language=question_textual["language"],
                        external_references=_reference_values_by_suffix(question_elem, "Reference"),
                        control_construct_references=_reference_values_by_suffix(
                            question_elem, "ControlConstructReference"
                        ),
                        **question_metadata,
                    ),
                    "questions",
                )

        universe_elem = elem.find("universe")
        universe_id = None
        if universe_elem is not None:
            universe_id = self._ingest_universe(universe_elem, fallback_prefix=variable_id)

        file_id = None
        location = elem.find("location")
        if location is not None:
            file_id = location.get("fileid") or location.get("FILEID")

        category_ids: list[str] = []
        for category in elem.findall("catgry"):
            category_id = self._ingest_category(category, code_scheme_id=None)
            if category_id:
                category_ids.append(category_id)

        concept_elem = elem.find("concept")
        if concept and concept not in self.seen_concepts:
            self.seen_concepts.add(concept)
            concept_textual = _textual_metadata(concept_elem)
            if concept_textual["label"] is None:
                concept_textual["label"] = concept
            concept_metadata = _common_metadata(concept_elem)
            self._append_and_count(
                self.concepts,
                ConceptRecord(
                    dataset_id=self.dataset_id,
                    dataset_name=self.dataset_name,
                    name=concept_textual["name"] or concept,
                    label=concept_textual["label"],
                    description=concept_textual["description"],
                    rationale=concept_textual["rationale"],
                    language=concept_textual["language"],
                    **concept_metadata,
                ),
                "concepts",
            )
        variable_textual = _textual_metadata(elem)
        if variable_textual["label"] is None:
            variable_textual["label"] = label
        if variable_textual["name"] is None:
            variable_textual["name"] = variable_textual["label"]
        variable_metadata = _common_metadata(elem)
        self._append_and_count(
            self.variables,
            VariableRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                variable_id=variable_id,
                label=variable_textual["label"],
                name=variable_textual["name"],
                description=variable_textual["description"],
                rationale=variable_textual["rationale"],
                language=variable_textual["language"],
                concept=concept,
                file_id=file_id,
                question_id=question_id,
                question_text=question_text,
                universe_id=universe_id,
                category_ids=category_ids,
                external_references=_reference_values_by_suffix(elem, "Reference"),
                **variable_metadata,
            ),
            "variables",
        )

    def ingest_organization(self, elem: etree._Element) -> None:
        """Ingest a organization element and record it on the batch.

        Args:
            elem: XML element carrying the organization metadata.
        """
        self._run_composition("ingest_organization", elem)

    def ingest_series(self, elem: etree._Element) -> None:
        """Ingest a study series element and record it on the batch.

        Args:
            elem: XML element carrying the study series metadata.
        """
        self._run_composition("ingest_series", elem)

    def ingest_group(self, elem: etree._Element) -> None:
        """Ingest a study group element and record it on the batch.

        Args:
            elem: XML element carrying the study group metadata.
        """
        self._run_composition("ingest_group", elem)

    def ingest_data_collection_event(self, elem: etree._Element) -> None:
        """Ingest a data collection event element and record it on the batch.

        Args:
            elem: XML element carrying the data collection event metadata.
        """
        self._run_composition("ingest_data_collection_event", elem)

    def ingest_question_item(self, elem: etree._Element) -> None:
        """Ingest a question item element and record it on the batch.

        Args:
            elem: XML element carrying the question item metadata.
        """
        parent_question_id: str | None = None
        parent_grid_id: str | None = None
        parent_flow_id: str | None = None
        variable_id: str | None = None
        parent = elem.getparent()
        if parent is not None:
            parent_tag = _strip_namespace(parent.tag)
            parent_tag_lower = parent_tag.lower()
            parent_id = _get_identifier(parent, default=None)
            if parent_tag_lower == "var" or parent_tag_lower == "variable":
                variable_id = parent_id
            elif parent_tag_lower in {"qstn", "question"}:
                parent_question_id = parent_id
            elif parent_tag_lower in {"qstngrid", "questiongrid"}:
                parent_grid_id = parent_id
            elif parent_tag_lower in {"qstnflow", "questionflow"}:
                parent_flow_id = parent_id

        question_item_id = _get_identifier(elem, default=None)
        if question_item_id is None:
            question_item_id = f"{self.dataset_id}:question_item_{len(self.question_items) + 1}"
        if not self._claim_id(self.seen_question_items, question_item_id):
            return
        text = _question_text(elem)
        textual = _textual_metadata(elem)
        name_attribute = elem.get("name") or elem.get("Name")
        if textual["label"] is None:
            textual["label"] = _first_text(elem, "labl") or text
        if name_attribute is not None:
            textual["name"] = name_attribute
        elif textual["name"] is None:
            textual["name"] = textual["label"] or text
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.question_items,
            QuestionItemRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                question_item_id=question_item_id,
                text=text,
                name=textual["name"],
                label=textual["label"],
                description=textual["description"],
                rationale=textual["rationale"],
                language=textual["language"],
                parent_question_id=parent_question_id,
                parent_grid_id=parent_grid_id,
                parent_flow_id=parent_flow_id,
                variable_id=variable_id,
                external_references=_reference_values_by_suffix(elem, "Reference"),
                control_construct_references=_reference_values_by_suffix(
                    elem, "ControlConstructReference"
                ),
                **metadata,
            ),
            "question_items",
        )

    def ingest_logical_record(self, elem: etree._Element) -> None:
        """Ingest a logical record element and record it on the batch.

        Args:
            elem: XML element carrying the logical record metadata.
        """
        self._run_composition("ingest_logical_record", elem)

    def ingest_physical_structure(self, elem: etree._Element) -> None:
        """Ingest a physical data structure element and record it on the batch.

        Args:
            elem: XML element carrying the physical data structure metadata.
        """
        self._run_composition("ingest_physical_structure", elem)

    def ingest_other_material(self, elem: etree._Element) -> None:
        """Ingest a external material element and record it on the batch.

        Args:
            elem: XML element carrying the external material metadata.
        """
        self._run_composition("ingest_other_material", elem)

    def ingest_var_group(self, elem: etree._Element) -> None:
        """Ingest a variable group element and record it on the batch.

        Args:
            elem: XML element carrying the variable group metadata.
        """
        self.var_group_index += 1
        var_group_id = (
            _get_identifier(elem, default=f"{self.dataset_id}:var_group_{self.var_group_index}")
            or f"{self.dataset_id}:var_group_{self.var_group_index}"
        )
        if var_group_id in self.seen_var_groups:
            return
        variable_ids: list[str] = []
        var_attr = elem.get("var")
        if var_attr:
            variable_ids.extend([vid for vid in var_attr.split() if vid])
        for var_ref in elem.findall(".//varRef"):
            ref_id = var_ref.get("IDREF") or var_ref.get("idref")
            if ref_id:
                variable_ids.append(ref_id)
        for var in elem.findall(".//var"):
            ref_id = _get_identifier(var)
            if ref_id:
                variable_ids.append(ref_id)
        self.seen_var_groups.add(var_group_id)
        label = _first_text(elem, "labl")
        metadata = _common_metadata(elem, label=label, name=_first_text(elem, "name"))
        self._append_and_count(
            self.var_groups,
            VarGroupRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                var_group_id=var_group_id,
                label=label,
                description=_text_or_none(elem),
                variable_ids=variable_ids,
                **metadata,
            ),
            "var_groups",
        )

    def ingest_category_group(self, elem: etree._Element) -> None:
        """Ingest a category group element and record it on the batch.

        Args:
            elem: XML element carrying the category group metadata.
        """
        self.category_group_index += 1
        category_group_id = (
            _get_identifier(
                elem,
                default=f"{self.dataset_id}:category_group_{self.category_group_index}",
            )
            or f"{self.dataset_id}:category_group_{self.category_group_index}"
        )
        if category_group_id in self.seen_category_groups:
            return
        category_ids: list[str] = []
        cat_attr = elem.get("catgry")
        if cat_attr:
            category_ids.extend([cid for cid in cat_attr.split() if cid])
        for cat_ref in elem.findall(".//catgryRef") + elem.findall(".//CategoryRef"):
            ref_id = cat_ref.get("IDREF") or cat_ref.get("idref")
            if ref_id:
                category_ids.append(ref_id)
        for cat in elem.findall(".//catgry") + elem.findall(".//Category"):
            ref_id = _get_identifier(cat)
            if ref_id:
                category_ids.append(ref_id)
        self.seen_category_groups.add(category_group_id)
        label = _first_text(elem, "labl")
        metadata = _common_metadata(elem, label=label, name=_first_text(elem, "name"))
        self._append_and_count(
            self.category_groups,
            CategoryGroupRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                category_group_id=category_group_id,
                label=label,
                description=_text_or_none(elem),
                category_ids=category_ids,
                **metadata,
            ),
            "category_groups",
        )

    def ingest_question_grid(self, elem: etree._Element) -> None:
        """Ingest a question grid element and record it on the batch.

        Args:
            elem: XML element carrying the question grid metadata.
        """
        self.question_grid_index += 1
        question_grid_id = (
            _get_identifier(elem, default=f"{self.dataset_id}:qgrid_{self.question_grid_index}")
            or f"{self.dataset_id}:qgrid_{self.question_grid_index}"
        )
        if not self._claim_id(self.seen_question_grids, question_grid_id):
            return
        text = _question_text(elem)
        textual = _textual_metadata(elem)
        if textual["label"] is None:
            textual["label"] = _first_text(elem, "labl") or text
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.question_grids,
            QuestionGridRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                question_grid_id=question_grid_id,
                text=text,
                name=textual["name"],
                label=textual["label"],
                description=textual["description"],
                rationale=textual["rationale"],
                language=textual["language"],
                external_references=_reference_values_by_suffix(elem, "Reference"),
                control_construct_references=_reference_values_by_suffix(
                    elem, "ControlConstructReference"
                ),
                **metadata,
            ),
            "question_grids",
        )

    def ingest_question_flow(self, elem: etree._Element) -> None:
        """Ingest a question flow element and record it on the batch.

        Args:
            elem: XML element carrying the question flow metadata.
        """
        self.question_flow_index += 1
        question_flow_id = (
            _get_identifier(elem, default=f"{self.dataset_id}:qflow_{self.question_flow_index}")
            or f"{self.dataset_id}:qflow_{self.question_flow_index}"
        )
        if not self._claim_id(self.seen_question_flows, question_flow_id):
            return
        text = _text_or_none(elem)
        textual = _textual_metadata(elem)
        if textual["label"] is None:
            textual["label"] = _first_text(elem, "labl") or text
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.question_flows,
            QuestionFlowRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                question_flow_id=question_flow_id,
                text=text,
                name=textual["name"],
                label=textual["label"],
                description=textual["description"],
                rationale=textual["rationale"],
                language=textual["language"],
                external_references=_reference_values_by_suffix(elem, "Reference"),
                control_construct_references=_reference_values_by_suffix(
                    elem, "ControlConstructReference"
                ),
                **metadata,
            ),
            "question_flows",
        )

    def ingest_sampling_procedure(self, elem: etree._Element) -> None:
        """Ingest a sampling procedure element and record it on the batch.

        Args:
            elem: XML element carrying the sampling procedure metadata.
        """
        self._run_composition("ingest_sampling_procedure", elem)

    def ingest_weight(self, elem: etree._Element) -> None:
        """Ingest a survey weight element and record it on the batch.

        Args:
            elem: XML element carrying the survey weight metadata.
        """
        self._run_composition("ingest_weight", elem)

    def ingest_representation(self, elem: etree._Element) -> None:
        """Ingest a value representation element and record it on the batch.

        Args:
            elem: XML element carrying the value representation metadata.
        """
        self._run_composition("ingest_representation", elem)

    def ingest_code_list(self, elem: etree._Element) -> None:
        """Ingest a code list element and record it on the batch.

        Args:
            elem: XML element carrying the code list metadata.
        """
        self._run_composition("ingest_code_list", elem)

    def ingest_methodology(self, elem: etree._Element) -> None:
        """Ingest a methodology note element and record it on the batch.

        Args:
            elem: XML element carrying the methodology note metadata.
        """
        self._run_composition("ingest_methodology", elem)

    def ingest_processing_event(self, elem: etree._Element) -> None:
        """Ingest a data processing event element and record it on the batch.

        Args:
            elem: XML element carrying the data processing event metadata.
        """
        self._run_composition("ingest_processing_event", elem)

    def ingest_software(self, elem: etree._Element) -> None:
        """Ingest a software reference element and record it on the batch.

        Args:
            elem: XML element carrying the software reference metadata.
        """
        self._run_composition("ingest_software", elem)

    def ingest_access_condition(self, elem: etree._Element) -> None:
        """Ingest a access condition element and record it on the batch.

        Args:
            elem: XML element carrying the access condition metadata.
        """
        self._run_composition("ingest_access_condition", elem)

    def ingest_citation(self, elem: etree._Element) -> None:
        """Ingest a bibliographic citation element and record it on the batch.

        Args:
            elem: XML element carrying the bibliographic citation metadata.
        """
        self._run_composition("ingest_citation", elem)

    def ingest_concept(self, elem: etree._Element) -> None:
        """Ingest a concept element and record it on the batch.

        Args:
            elem: XML element carrying the concept metadata.
        """
        self.concept_index += 1
        concept_label = _first_text_any(elem, "labl", "name", "conceptName") or _text_or_none(elem)
        concept_name = (
            _get_identifier(elem)
            or concept_label
            or f"{self.dataset_id}:concept_{self.concept_index}"
        )
        if not self._claim_id(self.seen_concepts, concept_name):
            return
        textual = _textual_metadata(elem)
        if textual["label"] is None:
            textual["label"] = concept_label
        if textual["name"] is None:
            textual["name"] = concept_name
        name = textual["name"] or concept_name
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.concepts,
            ConceptRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                name=name,
                label=textual["label"],
                description=textual["description"],
                rationale=textual["rationale"],
                language=textual["language"],
                **metadata,
            ),
            "concepts",
        )

    def ingest_coverage(self, elem: etree._Element, coverage_type: str | None) -> None:
        """Ingest a coverage entry element and record it on the batch.

        Args:
            elem: XML element carrying the coverage entry metadata.
            coverage_type: Discriminator stored on the resulting record.
        """
        self._run_composition("ingest_coverage", elem, extra={"coverage_type": coverage_type})

    def ingest_funding(self, elem: etree._Element) -> None:
        """Ingest a funding entry element and record it on the batch.

        Args:
            elem: XML element carrying the funding entry metadata.
        """
        self._run_composition("ingest_funding", elem)

    def ingest_contributor_role(self, elem: etree._Element) -> None:
        """Ingest a contributor role element and record it on the batch.

        Args:
            elem: XML element carrying the contributor role metadata.
        """
        self._run_composition("ingest_contributor_role", elem)

    def ingest_collection_instrument(
        self, elem: etree._Element, instrument_type: str | None
    ) -> None:
        """Ingest a collection instrument element and record it on the batch.

        Args:
            elem: XML element carrying the collection instrument metadata.
            instrument_type: Discriminator stored on the resulting record.
        """
        self.instrument_index += 1
        instrument_id = (
            _get_identifier(elem, default=f"{self.dataset_id}:instrument_{self.instrument_index}")
            or f"{self.dataset_id}:instrument_{self.instrument_index}"
        )
        if not self._claim_id(self.seen_instruments, instrument_id):
            return
        element_type = _strip_namespace(elem.tag)
        label = _first_text_local(
            elem, "labl", "Label", "name", "instrumentName", "InstrumentName"
        ) or _text_or_none(elem)
        instrument_name = _first_instrument_name(elem) or _first_text(elem, "name")
        description = label or _first_text_local(
            elem, "Description", "Content", "content", "Rationale", "rationale"
        )
        if description is None:
            description = _text_or_none(elem)
        metadata = _common_metadata(elem, label=label, name=instrument_name)
        metadata["urn"] = _first_text_local(elem, "URN") or metadata.get("urn")
        metadata["agency"] = _first_text_local(elem, "Agency") or metadata.get("agency")
        metadata["version"] = _first_text_local(elem, "Version") or metadata.get("version")
        type_of_instrument = _first_text_local(elem, "TypeOfInstrument") or instrument_type
        external_instrument_locations = _all_text_local(elem, "ExternalInstrumentLocation")
        fielded_languages = _all_text_local(elem, "FieldedLanguages")
        control_construct_reference = _first_reference_value(elem, "ControlConstructReference")
        referenced_construct_id = (
            _first_text_local(elem, "ControlConstructReference") or control_construct_reference
        )
        development_results_references = _reference_values(elem, "DevelopmentResultsReference")
        self._append_and_count(
            self.instruments,
            CollectionInstrumentRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                instrument_id=instrument_id,
                label=label,
                instrument_type=type_of_instrument,
                element_type=element_type,
                id=_first_text_local(elem, "ID"),
                name=instrument_name,
                description=description,
                external_instrument_locations=external_instrument_locations,
                control_construct_reference=control_construct_reference,
                referenced_construct_id=referenced_construct_id,
                fielded_languages=fielded_languages,
                development_results_references=development_results_references,
                **metadata,
            ),
            "instruments",
        )

    def ingest_control_construct(self, elem: etree._Element, construct_type: str | None) -> None:
        """Ingest a control construct element and record it on the batch.

        Args:
            elem: XML element carrying the control construct metadata.
            construct_type: Discriminator stored on the resulting record.
        """
        self._run_composition(
            "ingest_control_construct", elem, extra={"construct_type": construct_type}
        )

    def ingest_represented_variable(self, elem: etree._Element) -> None:
        """Ingest a represented variable element and record it on the batch.

        Args:
            elem: XML element carrying the represented variable metadata.
        """
        self._run_composition("ingest_represented_variable", elem)

    def ingest_comparison(self, elem: etree._Element, comparison_type: str | None) -> None:
        """Ingest a comparison element and record it on the batch.

        Args:
            elem: XML element carrying the comparison metadata.
            comparison_type: Discriminator stored on the resulting record.
        """
        self._run_composition("ingest_comparison", elem, extra={"comparison_type": comparison_type})

    def ingest_access_policy(self, elem: etree._Element, policy_type: str | None) -> None:
        """Ingest a access policy element and record it on the batch.

        Args:
            elem: XML element carrying the access policy metadata.
            policy_type: Discriminator stored on the resulting record.
        """
        self._run_composition("ingest_access_policy", elem, extra={"policy_type": policy_type})

    def ingest_universe(self, elem: etree._Element) -> None:
        """Ingest a universe element and record it on the batch.

        Args:
            elem: XML element carrying the universe metadata.
        """
        self.universe_index += 1
        default_id = f"{self.dataset_id}:universe_{self.universe_index}"
        self._ingest_universe(elem, fallback_prefix=self.dataset_id, default_id=default_id)

    def _ingest_universe(
        self,
        elem: etree._Element,
        fallback_prefix: str | None = None,
        default_id: str | None = None,
    ) -> str | None:
        universe_id = _get_identifier(
            elem,
            default=(default_id or (f"{fallback_prefix}:universe" if fallback_prefix else None)),
        )
        textual = _textual_metadata(elem)
        description = textual["description"] or _text_or_none(elem)
        if not universe_id:
            return None
        if universe_id not in self.seen_universes:
            self.seen_universes.add(universe_id)
            metadata = _common_metadata(elem)
            self._append_and_count(
                self.universes,
                UniverseRecord(
                    dataset_id=self.dataset_id,
                    dataset_name=self.dataset_name,
                    universe_id=universe_id,
                    description=description,
                    name=textual["name"],
                    label=textual["label"] or description,
                    rationale=textual["rationale"],
                    language=textual["language"],
                    external_references=_reference_values_by_suffix(elem, "Reference"),
                    **metadata,
                ),
                "universes",
            )
        return universe_id

    def _ingest_category(self, elem: etree._Element, code_scheme_id: str | None) -> str | None:
        category_id = _get_identifier(elem)
        if not category_id:
            return None
        if category_id not in self.seen_categories:
            self.seen_categories.add(category_id)
            label = _first_text(elem, "labl") or _text_or_none(elem)
            textual = _textual_metadata(elem)
            if textual["label"] is None:
                textual["label"] = label
            if textual["name"] is None:
                textual["name"] = label
            metadata = _common_metadata(elem)
            self._append_and_count(
                self.categories,
                CategoryRecord(
                    dataset_id=self.dataset_id,
                    dataset_name=self.dataset_name,
                    category_id=category_id,
                    label=textual["label"],
                    name=textual["name"],
                    code=_first_text(elem, "catValu"),
                    code_scheme_id=code_scheme_id,
                    description=textual["description"],
                    rationale=textual["rationale"],
                    language=textual["language"],
                    external_references=_reference_values_by_suffix(elem, "Reference"),
                    **metadata,
                ),
                "categories",
            )
        return category_id

    # =========================================================================
    # DDI-C 2.6 Ingest Methods
    # =========================================================================

    def ingest_ncube(self, elem: etree._Element) -> None:
        """Ingest a NCube element and record it on the batch.

        Args:
            elem: XML element carrying the NCube metadata.
        """
        self._run_composition("ingest_ncube", elem)

    def ingest_ncube_group(self, elem: etree._Element) -> None:
        """Ingest a NCube group element and record it on the batch.

        Args:
            elem: XML element carrying the NCube group metadata.
        """
        self._run_composition("ingest_ncube_group", elem)

    def ingest_document_description(self, elem: etree._Element) -> None:
        """Ingest a document description element and record it on the batch.

        Args:
            elem: XML element carrying the document description metadata.
        """
        doc_id = _get_identifier(elem)
        if not doc_id:
            self.doc_description_index += 1
            doc_id = f"{self.dataset_id}:doc_{self.doc_description_index}"
        if not self._claim_id(self.seen_doc_descriptions, doc_id):
            return
        title = (
            _first_text(elem, ".//titl")
            or _first_text(elem, ".//title")
            or next(
                (citation.title for citation in reversed(self.citations) if citation.title), None
            )
        )
        textual = _textual_metadata(elem)
        metadata = _common_metadata(elem)
        producer = (
            _first_text(elem, ".//producer")
            or _first_text(elem, ".//prodStmt//producer")
            or next(
                (org.name for org in reversed(self.organizations) if org.name),
                None,
            )
        )
        self._append_and_count(
            self.document_descriptions,
            DocumentDescriptionRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                doc_id=doc_id,
                title=title,
                description=textual["description"],
                producer=producer,
                name=textual["name"],
                label=textual["label"] or title,
                **metadata,
            ),
            "document_descriptions",
        )

    def ingest_sample_frame(self, elem: etree._Element) -> None:
        """Ingest a sample frame element and record it on the batch.

        Args:
            elem: XML element carrying the sample frame metadata.
        """
        self._run_composition("ingest_sample_frame", elem)

    def ingest_quality_statement(self, elem: etree._Element) -> None:
        """Ingest a quality statement element and record it on the batch.

        Args:
            elem: XML element carrying the quality statement metadata.
        """
        self._run_composition("ingest_quality_statement", elem)

    def ingest_study_authorization(self, elem: etree._Element) -> None:
        """Ingest a study authorization element and record it on the batch.

        Args:
            elem: XML element carrying the study authorization metadata.
        """
        self._run_composition("ingest_study_authorization", elem)

    def ingest_study_development(self, elem: etree._Element) -> None:
        """Ingest a study development activity element and record it on the batch.

        Args:
            elem: XML element carrying the study development activity metadata.
        """
        self._run_composition("ingest_study_development", elem)

    def ingest_ex_post_evaluation(self, elem: etree._Element) -> None:
        """Ingest a ex-post evaluation element and record it on the batch.

        Args:
            elem: XML element carrying the ex-post evaluation metadata.
        """
        self._run_composition("ingest_ex_post_evaluation", elem)

    def ingest_generic_identifiable(self, elem: etree._Element, element_tag: str) -> None:
        """Capture a DDI-Codebook identifiable element without a bespoke record.

        Covers concrete codebook elements that carry an ``ID`` attribute via the
        ``GLOBALS`` attribute group but don't warrant a dedicated record class.
        """
        ident = _get_identifier(elem)
        if not ident:
            self.generic_identifiable_index += 1
            ident = f"{self.dataset_id}:{element_tag}_{self.generic_identifiable_index}"
        key = f"{element_tag}:{ident}"
        if not self._claim_id(self.seen_generic_identifiables, key):
            return
        textual = _textual_metadata(elem)
        metadata = _common_metadata(elem)
        self._append_and_count(
            self.generic_identifiables,
            GenericIdentifiableRecord(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
                identifiable_id=ident,
                element_tag=element_tag,
                description=textual["description"],
                name=textual["name"],
                label=textual["label"],
                **metadata,
            ),
            "generic_identifiables",
        )

    def flush_if_ready(self) -> DDIBatch | None:
        """Emit the current batch if the record count hit ``chunk_size``.

        Returns:
            The flushed ``DDIBatch`` when the threshold was crossed,
            otherwise ``None``.
        """
        if self._count_records() >= self.chunk_size:
            return self._flush()
        return None

    def finalize(self) -> DDIBatch | None:
        """Emit a final batch for any records still buffered.

        Returns:
            A ``DDIBatch`` when the builder held buffered work (including
            generic identifiables), otherwise ``None``.
        """
        # generic_identifiables are excluded from _count_records to keep
        # chunk-flush semantics stable, but the end-of-stream flush still
        # has to emit them so the data isn't lost.
        if self._count_records() == 0 and not self.generic_identifiables:
            return None
        return self._flush()

    def _flush(self) -> DDIBatch:
        batch = DDIBatch(
            dataset=self.dataset,
            studies=self.studies,
            data_files=self.data_files,
            code_schemes=self.code_schemes,
            categories=self.categories,
            universes=self.universes,
            concepts=self.concepts,
            variables=self.variables,
            questions=self.questions,
            question_items=self.question_items,
            organizations=self.organizations,
            series_list=self.series_list,
            groups=self.groups,
            data_collection_events=self.data_collection_events,
            logical_records=self.logical_records,
            physical_structures=self.physical_structures,
            other_materials=self.other_materials,
            var_groups=self.var_groups,
            category_groups=self.category_groups,
            question_grids=self.question_grids,
            question_flows=self.question_flows,
            sampling_procedures=self.sampling_procedures,
            weights=self.weights,
            representations=self.representations,
            code_lists=self.code_lists,
            methodology_notes=self.methodology_notes,
            processing_events=self.processing_events,
            software=self.software,
            access_conditions=self.access_conditions,
            citations=self.citations,
            coverage=self.coverage,
            funding=self.funding,
            contributor_roles=self.contributor_roles,
            instruments=self.instruments,
            control_constructs=self.control_constructs,
            represented_variables=self.represented_variables,
            comparisons=self.comparisons,
            access_policies=self.access_policies,
            ncubes=self.ncubes,
            ncube_groups=self.ncube_groups,
            document_descriptions=self.document_descriptions,
            sample_frames=self.sample_frames,
            quality_statements=self.quality_statements,
            study_authorizations=self.study_authorizations,
            study_developments=self.study_developments,
            ex_post_evaluations=self.ex_post_evaluations,
            generic_identifiables=self.generic_identifiables,
        )
        self._increment_total("batches")
        self._reset()
        return batch

    def totals_summary(self) -> dict[str, int]:
        """Return cumulative totals seen by this builder.

        Returns:
            Mapping of record-type name to the number of records ingested
            across all flushed batches plus any currently buffered work.
        """
        return dict(self.totals)

    def _count_records(self) -> int:
        return sum(
            len(items)
            for items in (
                self.studies,
                self.data_files,
                self.code_schemes,
                self.categories,
                self.universes,
                self.concepts,
                self.variables,
                self.questions,
                self.question_items,
                self.organizations,
                self.series_list,
                self.groups,
                self.data_collection_events,
                self.logical_records,
                self.physical_structures,
                self.other_materials,
                self.var_groups,
                self.category_groups,
                self.question_grids,
                self.question_flows,
                self.sampling_procedures,
                self.weights,
                self.representations,
                self.code_lists,
                self.methodology_notes,
                self.processing_events,
                self.software,
                self.access_conditions,
                self.citations,
                self.coverage,
                self.funding,
                self.contributor_roles,
                self.instruments,
                self.control_constructs,
                self.represented_variables,
                self.comparisons,
                self.access_policies,
                self.ncubes,
                self.ncube_groups,
                self.document_descriptions,
                self.sample_frames,
                self.quality_statements,
                self.study_authorizations,
                self.study_developments,
                self.ex_post_evaluations,
                # ``generic_identifiables`` captures auxiliary DDI-Codebook
                # elements that do not have bespoke records.  They are
                # excluded from the flush trigger so adding broader XSD
                # coverage does not change chunking behavior for callers.
            )
        )


def _first_text(elem: etree._Element, path: str) -> str | None:
    target = elem.find(path)
    if isinstance(target, etree._Element):
        text: str | None = target.text
        if text:
            stripped = text.strip()
            if stripped:
                return stripped
    return None


def _first_text_any(elem: etree._Element, *paths: str) -> str | None:
    for path in paths:
        value = _first_text(elem, path)
        if value:
            return value
    return None


# ---------------------------------------------------------------------------
# Thin aliases delegating to shared utilities in ddigraph.utils.parsing
# ---------------------------------------------------------------------------

# Alias: get_text already accepts Element | None; _text_or_none only took
# a non-optional Element but their logic is identical.
_text_or_none = get_text

# Alias: strip_namespace handles str | bytes | bytearray | Any.
_strip_namespace = strip_namespace


def _get_identifier(elem: etree._Element, default: str | None = "") -> str | None:
    """Extract the ID attribute from a DDI element (attribute-only lookup)."""
    identifier = elem.get("ID") or elem.get("id")
    if isinstance(identifier, str) and identifier:
        return identifier
    return default


def _first_text_local(elem: etree._Element | None, *local_names: str) -> str | None:
    return get_child_text(elem, *local_names, recursive=True)


def _all_text_local(elem: etree._Element | None, *local_names: str) -> list[str]:
    return get_all_child_text(elem, *local_names, recursive=True)


def _first_instrument_name(elem: etree._Element | None) -> str | None:
    if elem is None:
        return None

    instrument_name_elem = next(
        (child for child in elem.iter() if strip_namespace(child.tag) == "InstrumentName"),
        None,
    )
    if instrument_name_elem is None:
        return None
    return get_child_text(instrument_name_elem, "String", recursive=True) or get_text(
        instrument_name_elem
    )


def _reference_values(elem: etree._Element | None, *local_names: str) -> list[str]:
    values: list[str] = []
    if elem is None:
        return values

    for target in elem.iter():
        if strip_namespace(target.tag) in local_names:
            reference = extract_reference_value(target)
            if reference:
                values.append(reference)
    return values


def _first_reference_value(elem: etree._Element | None, *local_names: str) -> str | None:
    references = _reference_values(elem, *local_names)
    if references:
        return references[0]
    return None


# Delegate directly to the shared implementation.
_reference_values_by_suffix = extract_references_by_suffix


__all__ = [
    "DDIBatch",
    "DDILoader",
    "VariableRecord",
    "normalize_dataset_id",
    "parse_ddi_batches",
    "parse_ddi_variables",
]

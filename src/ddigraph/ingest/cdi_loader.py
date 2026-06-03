"""Streaming DDI-CDI 1.0 XML ingestion.

This module handles DDI Cross-Domain Integration (DDI-CDI) XML files, which
use a ``<Wrapper>`` root element containing typed entity elements from the
DDI-CDI information model.

DDI-CDI differs fundamentally from both DDI Codebook (DDI-C) and DDI Lifecycle
(DDI-L):

- Entities derive from a UML model (DDICDIModels) with rich inheritance
  hierarchies (e.g., Concept -> UnitType -> Universe -> Population).
- Associations between entities are expressed as nested ``*_has_*``,
  ``*_isDefinedBy_*``, and ``*_correspondsTo_*`` elements with typed
  references via ``<Identifier>`` sub-elements.
- The schema covers ~158 entity types and ~240 named associations; this
  loader targets the ~25 most important types for graph representation.

This module provides:
- Streaming XML parsing with ``iterparse`` for memory efficiency
- Batched graph writes via ``CDIBatch`` containers
- Integration with the ``GraphWriteAdapter`` pattern
- Format detection support via :func:`is_cdi_format`
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree  # type: ignore[import-untyped,unused-ignore]

from ddigraph.schema._generated.cdi import CDI_GENERATED_ENTITIES
from ddigraph.schema._overrides._loader import cdi_relationships
from ddigraph.utils.chunking import as_dicts as _as_dicts
from ddigraph.utils.parsing import (
    close_iterparse_context,
    get_text,
    strip_namespace,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CDI Record Dataclasses
# ============================================================================


@dataclass(slots=True)
class CDIRecord:
    """One parsed DDI-CDI entity record.

    Carries the five universal fields plus eight optional flavor-specific
    attributes that used to live on bespoke per-entity subclasses. The
    XSD declares 210 concrete entity classes; the runtime parses them all
    into this single record and lets the downstream adapter dispatch on
    the populated extras (``entity_type``, ``agent_type``, etc.).
    """

    cdi_id: str
    name: str | None = None
    label: str | None = None
    description: str | None = None
    urn: str | None = None
    # Optional flavor-specific extras, populated only when the XSD type
    # carries the corresponding field.
    entity_type: str | None = None
    agent_type: str | None = None
    value: str | None = None
    version: str | None = None
    code: str | None = None
    structure_type: str | None = None
    component_type: str | None = None
    dataset_type: str | None = None
    domain_type: str | None = None


# Backwards-compatible alias for callers (and tests) that imported the
# pre-collapse generic record class. Both names refer to the same shape.
CDIGenericRecord = CDIRecord


@dataclass(slots=True)
class CDIRelationshipRecord:
    """A relationship between two CDI entities."""

    rel_type: str
    source_id: str
    target_id: str
    source_label: str
    target_label: str


# ============================================================================
# CDI Batch Container
# ============================================================================


@dataclass
class CDIBatch:
    """Collection of parsed DDI-CDI entities held until flush.

    Attributes:
        concepts: Concept entities.
        concept_systems: ConceptSystem entities.
        conceptual_variables: ConceptualVariable entities.
        represented_variables: RepresentedVariable entities.
        instance_variables: InstanceVariable entities.
        unit_types: UnitType entities.
        universes: Universe entities.
        populations: Population entities.
        agents: Agent entities (Individual, Organization, Machine).
        categories: Category entities.
        category_sets: CategorySet entities.
        codes: Code entities.
        code_lists: CodeList entities.
        statistical_classifications: StatisticalClassification entities.
        classification_items: ClassificationItem entities.
        data_structures: DataStructure entities.
        data_structure_components: DataStructureComponent entities.
        datasets: DataSet entities.
        data_stores: DataStore entities.
        logical_records: LogicalRecord entities.
        physical_datasets: PhysicalDataSet entities.
        activities: Activity entities.
        processing_agents: ProcessingAgent entities.
        value_domains: ValueDomain entities.
        correspondence_tables: CorrespondenceTable entities.
        relationships: Parsed relationships between entities.
    """

    concepts: list[CDIRecord] = field(default_factory=list)
    concept_systems: list[CDIRecord] = field(default_factory=list)
    conceptual_variables: list[CDIRecord] = field(default_factory=list)
    represented_variables: list[CDIRecord] = field(default_factory=list)
    instance_variables: list[CDIRecord] = field(default_factory=list)
    unit_types: list[CDIRecord] = field(default_factory=list)
    universes: list[CDIRecord] = field(default_factory=list)
    populations: list[CDIRecord] = field(default_factory=list)
    agents: list[CDIRecord] = field(default_factory=list)
    categories: list[CDIRecord] = field(default_factory=list)
    category_sets: list[CDIRecord] = field(default_factory=list)
    codes: list[CDIRecord] = field(default_factory=list)
    code_lists: list[CDIRecord] = field(default_factory=list)
    statistical_classifications: list[CDIRecord] = field(default_factory=list)
    classification_items: list[CDIRecord] = field(default_factory=list)
    data_structures: list[CDIRecord] = field(default_factory=list)
    data_structure_components: list[CDIRecord] = field(default_factory=list)
    datasets: list[CDIRecord] = field(default_factory=list)
    data_stores: list[CDIRecord] = field(default_factory=list)
    logical_records: list[CDIRecord] = field(default_factory=list)
    physical_datasets: list[CDIRecord] = field(default_factory=list)
    activities: list[CDIRecord] = field(default_factory=list)
    processing_agents: list[CDIRecord] = field(default_factory=list)
    value_domains: list[CDIRecord] = field(default_factory=list)
    correspondence_tables: list[CDIRecord] = field(default_factory=list)
    variable_relationships: list[CDIRecord] = field(default_factory=list)
    concept_maps: list[CDIRecord] = field(default_factory=list)
    concept_system_correspondences: list[CDIRecord] = field(default_factory=list)
    physical_record_segments: list[CDIRecord] = field(default_factory=list)
    classification_families: list[CDIRecord] = field(default_factory=list)
    classification_indexes: list[CDIRecord] = field(default_factory=list)
    classification_series: list[CDIRecord] = field(default_factory=list)
    generic_entities: list[CDIGenericRecord] = field(default_factory=list)
    relationships: list[CDIRelationshipRecord] = field(default_factory=list)

    def total_records(self) -> int:
        """Return the total count of entity records across all collections.

        Returns:
            Sum of ``len`` over every record list on the batch, excluding the
            ``relationships`` collection (which is not a first-class entity).
        """
        return sum(
            len(items)
            for items in (
                self.concepts,
                self.concept_systems,
                self.conceptual_variables,
                self.represented_variables,
                self.instance_variables,
                self.unit_types,
                self.universes,
                self.populations,
                self.agents,
                self.categories,
                self.category_sets,
                self.codes,
                self.code_lists,
                self.statistical_classifications,
                self.classification_items,
                self.data_structures,
                self.data_structure_components,
                self.datasets,
                self.data_stores,
                self.logical_records,
                self.physical_datasets,
                self.activities,
                self.processing_agents,
                self.value_domains,
                self.correspondence_tables,
                self.variable_relationships,
                self.concept_maps,
                self.concept_system_correspondences,
                self.physical_record_segments,
                self.classification_families,
                self.classification_indexes,
                self.classification_series,
                self.generic_entities,
            )
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the batch into a nested dict of primitive values.

        Returns:
            Mapping from collection name (e.g. ``"concepts"``, ``"relationships"``)
            to a list of per-record dicts suitable for JSON serialization or
            adapter consumption.
        """
        return {
            "concepts": _as_dicts(self.concepts),
            "concept_systems": _as_dicts(self.concept_systems),
            "conceptual_variables": _as_dicts(self.conceptual_variables),
            "represented_variables": _as_dicts(self.represented_variables),
            "instance_variables": _as_dicts(self.instance_variables),
            "unit_types": _as_dicts(self.unit_types),
            "universes": _as_dicts(self.universes),
            "populations": _as_dicts(self.populations),
            "agents": _as_dicts(self.agents),
            "categories": _as_dicts(self.categories),
            "category_sets": _as_dicts(self.category_sets),
            "codes": _as_dicts(self.codes),
            "code_lists": _as_dicts(self.code_lists),
            "statistical_classifications": _as_dicts(self.statistical_classifications),
            "classification_items": _as_dicts(self.classification_items),
            "data_structures": _as_dicts(self.data_structures),
            "data_structure_components": _as_dicts(self.data_structure_components),
            "datasets": _as_dicts(self.datasets),
            "data_stores": _as_dicts(self.data_stores),
            "logical_records": _as_dicts(self.logical_records),
            "physical_datasets": _as_dicts(self.physical_datasets),
            "activities": _as_dicts(self.activities),
            "processing_agents": _as_dicts(self.processing_agents),
            "value_domains": _as_dicts(self.value_domains),
            "correspondence_tables": _as_dicts(self.correspondence_tables),
            "variable_relationships": _as_dicts(self.variable_relationships),
            "concept_maps": _as_dicts(self.concept_maps),
            "concept_system_correspondences": _as_dicts(self.concept_system_correspondences),
            "physical_record_segments": _as_dicts(self.physical_record_segments),
            "classification_families": _as_dicts(self.classification_families),
            "classification_indexes": _as_dicts(self.classification_indexes),
            "classification_series": _as_dicts(self.classification_series),
            "generic_entities": _as_dicts(self.generic_entities),
            "relationships": _as_dicts(self.relationships),
        }


# ============================================================================
# CDI XML Parser
# ============================================================================

# Root elements that act purely as containers — their direct children are
# the actual top-level CDI entities.  When a document root is NOT in this
# set (e.g. a single-entity ``<Concept>`` document), the root itself is
# the only top-level entity and its children must NOT be dispatched.
_CDI_CONTAINER_ROOT_TAGS: frozenset[str] = frozenset(
    {
        "Wrapper",
        "DDICDIModels",
    }
)

# Bespoke (non-default) tag dispatch entries. Every other XSD-declared
# CDI entity defaults to ``(CDIGenericRecord, "generic_entities",
#   {"entity_type": <tag>})`` via ``_build_cdi_tag_map`` below.
# Refresh this list with:
#   .venv/bin/python -c \
#     "from ddigraph.ingest.cdi_loader import _CDI_BESPOKE_MAP; print(sorted(_CDI_BESPOKE_MAP))"
_CDI_BESPOKE_MAP: dict[str, tuple[type[CDIRecord], str, dict[str, str]]] = {
    # DDICDIModels is the document-level wrapper. CDI_GENERATED_ENTITIES
    # excludes ``DDI*`` framing tags from its entity list, so the auto-
    # derivation would otherwise drop it. The runtime parses it as a
    # generic record to preserve historical behaviour.
    "DDICDIModels": (CDIGenericRecord, "generic_entities", {"entity_type": "DDICDIModels"}),
    "Concept": (CDIRecord, "concepts", {}),
    "ConceptSystem": (CDIRecord, "concept_systems", {}),
    "ConceptualVariable": (CDIRecord, "conceptual_variables", {}),
    "RepresentedVariable": (CDIRecord, "represented_variables", {}),
    "InstanceVariable": (CDIRecord, "instance_variables", {}),
    "DescriptorVariable": (CDIRecord, "instance_variables", {}),
    "ReferenceVariable": (CDIRecord, "instance_variables", {}),
    "UnitType": (CDIRecord, "unit_types", {}),
    "Universe": (CDIRecord, "universes", {}),
    "Population": (CDIRecord, "populations", {}),
    "Individual": (CDIRecord, "agents", {"agent_type": "Individual"}),
    "Organization": (CDIRecord, "agents", {"agent_type": "Organization"}),
    "Machine": (CDIRecord, "agents", {"agent_type": "Machine"}),
    "Category": (CDIRecord, "categories", {}),
    "CategorySet": (CDIRecord, "category_sets", {}),
    "Code": (CDIRecord, "codes", {}),
    "CodeList": (CDIRecord, "code_lists", {}),
    "StatisticalClassification": (
        CDIRecord,
        "statistical_classifications",
        {},
    ),
    "ClassificationItem": (CDIRecord, "classification_items", {}),
    "DataStructure": (CDIRecord, "data_structures", {"structure_type": "generic"}),
    "DimensionalDataStructure": (
        CDIRecord,
        "data_structures",
        {"structure_type": "dimensional"},
    ),
    "WideDataStructure": (CDIRecord, "data_structures", {"structure_type": "wide"}),
    "LongDataStructure": (CDIRecord, "data_structures", {"structure_type": "long"}),
    "KeyValueStructure": (
        CDIRecord,
        "data_structures",
        {"structure_type": "key_value"},
    ),
    "AttributeComponent": (
        CDIRecord,
        "data_structure_components",
        {"component_type": "attribute"},
    ),
    "DimensionComponent": (
        CDIRecord,
        "data_structure_components",
        {"component_type": "dimension"},
    ),
    "MeasureComponent": (
        CDIRecord,
        "data_structure_components",
        {"component_type": "measure"},
    ),
    "IdentifierComponent": (
        CDIRecord,
        "data_structure_components",
        {"component_type": "identifier"},
    ),
    "DataSet": (CDIRecord, "datasets", {"dataset_type": "generic"}),
    "DimensionalDataSet": (CDIRecord, "datasets", {"dataset_type": "dimensional"}),
    "WideDataSet": (CDIRecord, "datasets", {"dataset_type": "wide"}),
    "LongDataSet": (CDIRecord, "datasets", {"dataset_type": "long"}),
    "DataStore": (CDIRecord, "data_stores", {}),
    "LogicalRecord": (CDIRecord, "logical_records", {}),
    "PhysicalDataSet": (CDIRecord, "physical_datasets", {}),
    "Activity": (CDIRecord, "activities", {}),
    "Step": (CDIRecord, "activities", {}),
    "ProcessingAgent": (CDIRecord, "processing_agents", {"agent_type": "generic"}),
    "Curator": (CDIRecord, "processing_agents", {"agent_type": "curator"}),
    "Service": (CDIRecord, "processing_agents", {"agent_type": "service"}),
    "SubstantiveValueDomain": (
        CDIRecord,
        "value_domains",
        {"domain_type": "substantive"},
    ),
    "SentinelValueDomain": (CDIRecord, "value_domains", {"domain_type": "sentinel"}),
    "ReferenceValueDomain": (CDIRecord, "value_domains", {"domain_type": "reference"}),
    "DescriptorValueDomain": (CDIRecord, "value_domains", {"domain_type": "descriptor"}),
    "CorrespondenceTable": (CDIRecord, "correspondence_tables", {}),
    "ClassificationFamily": (CDIRecord, "classification_families", {}),
    "ClassificationIndex": (CDIRecord, "classification_indexes", {}),
    "ClassificationSeries": (CDIRecord, "classification_series", {}),
    "VariableRelationship": (CDIRecord, "variable_relationships", {}),
    "ConceptMap": (CDIRecord, "concept_maps", {}),
    "ConceptSystemCorrespondence": (
        CDIRecord,
        "concept_system_correspondences",
        {},
    ),
    "PhysicalRecordSegment": (CDIRecord, "physical_record_segments", {}),
}


def _build_cdi_tag_map() -> dict[str, tuple[type[CDIRecord], str, dict[str, str]]]:
    """Build the full CDI tag-to-record dispatch table from XSD + overrides.

    Every entity in ``CDI_GENERATED_ENTITIES`` defaults to the generic
    ``CDIGenericRecord`` path; ``_CDI_BESPOKE_MAP`` overrides any tag that
    needs a bespoke record class or non-default ``extra_fields``.
    """
    table: dict[str, tuple[type[CDIRecord], str, dict[str, str]]] = {
        entity: (CDIGenericRecord, "generic_entities", {"entity_type": entity})
        for entity in CDI_GENERATED_ENTITIES
    }
    table.update(_CDI_BESPOKE_MAP)
    return table


_CDI_TAG_MAP: dict[str, tuple[type[CDIRecord], str, dict[str, str]]] = _build_cdi_tag_map()
# Relationship patterns: association element tag -> (rel_type, source_label, target_label).
# Derived from CDI_GENERATED_ASSOCIATIONS via schema_overrides.toml so every
# XSD-declared <Source>_<verb>_<Target> element produces a graph relationship;
# 10 explicit rel_type overrides preserve the historical hand-curated names.
_CDI_RELATIONSHIP_MAP: dict[str, tuple[str, str, str]] = cdi_relationships()


def _extract_identifier(elem: etree._Element) -> str | None:
    """Extract the identifier string from a CDI entity element.

    DDI-CDI entities use ``<Identifier>`` sub-elements that may contain
    ``<StringValue>`` for the actual ID string.
    """
    id_elem = elem.find("Identifier")
    if id_elem is None:
        # Try namespace-qualified
        for child in elem:
            if strip_namespace(child.tag) == "Identifier":
                id_elem = child
                break
    if id_elem is None:
        return None

    # Check for StringValue sub-element
    for child in id_elem:
        local = strip_namespace(child.tag)
        if local == "StringValue":
            return get_text(child)
    # Fallback to direct text
    return get_text(id_elem)


def _extract_label(elem: etree._Element) -> str | None:
    """Extract label from a CDI entity, checking LabelForDisplay and name."""
    for child in elem:
        local = strip_namespace(child.tag)
        if local in ("LabelForDisplay", "label"):
            text = get_text(child)
            if text:
                return text
    return None


def _extract_name(elem: etree._Element) -> str | None:
    """Extract name from ObjectName or name child."""
    for child in elem:
        local = strip_namespace(child.tag)
        if local in ("ObjectName", "name"):
            text = get_text(child)
            if text:
                return text
    return None


def _extract_description(elem: etree._Element) -> str | None:
    """Extract description from Description or description child."""
    for child in elem:
        local = strip_namespace(child.tag)
        if local in ("Description", "description"):
            text = get_text(child)
            if text:
                return text
    return None


def _extract_reference_id(elem: etree._Element) -> str | None:
    """Extract a reference identifier from an association element.

    CDI association elements typically contain an ``<Identifier>`` child with a
    ``<StringValue>`` holding the target ID.
    """
    # The association element directly contains an Identifier child
    cdi_id = _extract_identifier(elem)
    if cdi_id:
        return cdi_id
    # Try Reference sub-element pattern
    for child in elem:
        local = strip_namespace(child.tag)
        if local == "Reference":
            return _extract_identifier(child)
    return get_text(elem)


def _parse_cdi_entity(
    elem: etree._Element,
    record_cls: type[CDIRecord],
    extra_fields: dict[str, str],
) -> CDIRecord | None:
    """Parse a CDI XML element into a record dataclass.

    Args:
        elem: The XML element for the CDI entity.
        record_cls: The record dataclass type to create.
        extra_fields: Additional field values to set (e.g., agent_type).

    Returns:
        A record instance, or None if the element has no identifier.
    """
    cdi_id = _extract_identifier(elem)
    if not cdi_id:
        # Generate a fallback ID from tag + position
        cdi_id = elem.get("id") or elem.get("ID")
    if not cdi_id:
        return None

    name = _extract_name(elem)
    label = _extract_label(elem)
    description = _extract_description(elem)
    urn = elem.get("urn") or elem.get("URN")

    kwargs: dict[str, Any] = {
        "cdi_id": cdi_id,
        "name": name,
        "label": label or name,
        "description": description,
        "urn": urn,
    }

    # Add type-specific extra fields
    for field_name, value in extra_fields.items():
        kwargs[field_name] = value

    # Handle type-specific properties
    local_tag = strip_namespace(elem.tag)
    if local_tag == "Code" or local_tag in ("ClassificationItem",):
        # Extract code value
        for child in elem:
            child_local = strip_namespace(child.tag)
            if child_local in ("Notation", "value"):
                kwargs["value" if local_tag == "Code" else "code"] = get_text(child)
                break

    if local_tag == "StatisticalClassification":
        for child in elem:
            if strip_namespace(child.tag) == "Version":
                kwargs["version"] = get_text(child)
                break

    return record_cls(**kwargs)


def _parse_cdi_relationships(
    elem: etree._Element,
    parent_id: str,
    parent_tag: str,
) -> list[CDIRelationshipRecord]:
    """Extract relationships from association child elements of a CDI entity.

    Args:
        elem: The parent entity element.
        parent_id: Identifier of the parent entity.
        parent_tag: Local tag name of the parent entity.

    Returns:
        List of parsed relationship records.
    """
    rels: list[CDIRelationshipRecord] = []
    for child in elem:
        assoc_tag = strip_namespace(child.tag)
        if assoc_tag in _CDI_RELATIONSHIP_MAP:
            rel_type, source_label, target_label = _CDI_RELATIONSHIP_MAP[assoc_tag]
            target_id = _extract_reference_id(child)
            if target_id:
                rels.append(
                    CDIRelationshipRecord(
                        rel_type=rel_type,
                        source_id=parent_id,
                        target_id=target_id,
                        source_label=source_label,
                        target_label=target_label,
                    )
                )
    return rels


class CDIBatchBuilder:
    """Accumulate parsed CDI records into batches.

    Args:
        chunk_size: Maximum records per batch.
    """

    def __init__(self, chunk_size: int) -> None:
        self.chunk_size = chunk_size
        self.batch = CDIBatch()
        self.seen_ids: set[str] = set()
        self.totals: dict[str, int] = {"entities": 0, "relationships": 0, "batches": 0}

    def ingest_entity(
        self,
        elem: etree._Element,
        record_cls: type[CDIRecord],
        collection_name: str,
        extra_fields: dict[str, str],
    ) -> None:
        """Parse and record a single CDI entity element.

        Skips elements without a resolvable identifier and deduplicates by
        ``cdi_id``. Any association children on the element are converted into
        :class:`CDIRelationshipRecord` entries on the same batch.

        Args:
            elem: XML element of the CDI entity.
            record_cls: Record dataclass used to hold the parsed entity.
            collection_name: Name of the :class:`CDIBatch` list to append to.
            extra_fields: Extra attributes applied to the record after parsing
                (e.g. ``{"structure_type": "wide"}``).
        """
        record = _parse_cdi_entity(elem, record_cls, extra_fields)
        if record is None:
            return
        if record.cdi_id in self.seen_ids:
            return
        self.seen_ids.add(record.cdi_id)

        collection = getattr(self.batch, collection_name)
        collection.append(record)
        self.totals["entities"] = self.totals.get("entities", 0) + 1

        # Extract relationships from this entity's children
        rels = _parse_cdi_relationships(elem, record.cdi_id, strip_namespace(elem.tag))
        if rels:
            self.batch.relationships.extend(rels)
            self.totals["relationships"] = self.totals.get("relationships", 0) + len(rels)

    def flush_if_ready(self) -> CDIBatch | None:
        """Emit the current batch if the record count hit ``chunk_size``.

        Returns:
            The flushed :class:`CDIBatch` when the threshold was crossed,
            otherwise ``None``.
        """
        if self.batch.total_records() >= self.chunk_size:
            return self._flush()
        return None

    def finalize(self) -> CDIBatch | None:
        """Emit a final batch for any records still buffered.

        Returns:
            A :class:`CDIBatch` when at least one entity record is buffered,
            otherwise ``None``.
        """
        if self.batch.total_records() == 0:
            return None
        return self._flush()

    def _flush(self) -> CDIBatch:
        batch = self.batch
        self.batch = CDIBatch()
        self.totals["batches"] = self.totals.get("batches", 0) + 1
        return batch


class CDIBatchStream:
    """Streaming CDI XML parser yielding batches of CDI records.

    Args:
        path: Path to the DDI-CDI XML file.
        chunk_size: Maximum number of records per batch.
        recover: Whether to attempt recovery from XML parse errors.
    """

    def __init__(
        self,
        path: Path,
        chunk_size: int,
        *,
        recover: bool = True,
    ) -> None:
        self.path = path
        self.chunk_size = chunk_size
        self.recover = recover
        self.builder = CDIBatchBuilder(chunk_size)

    @staticmethod
    def _is_top_level_cdi_entity_element(
        *,
        elem: etree._Element,
        parent: etree._Element | None,
        root: etree._Element | None,
        root_is_container: bool,
    ) -> bool:
        """Return whether ``elem`` should be dispatched as a top-level entity.

        Only two shapes are valid top-level entity candidates:

        * The XML root itself for single-entity documents (non-container roots).
        * Direct children of container roots (``Wrapper`` / ``DDICDIModels``).

        All other elements are nested and must be skipped so the enclosing
        top-level entity can still read reusable fields (e.g. ``Identifier``).
        """
        if root is None:
            return False
        if elem is root:
            return not root_is_container
        return root_is_container and parent is root

    def __iter__(self) -> Iterator[CDIBatch]:
        """Parse the CDI XML and yield batches.

        The stream distinguishes two root shapes:

        * **Container root** (``Wrapper`` / ``DDICDIModels``): every direct
          child is an independent top-level CDI entity and is ingested in
          place.  Nested reusable types (``Identifier``, ``ObjectName``,
          ``LabelForDisplay``, ...) inside those children are ignored.
        * **Single-entity root** (root is an entity tag such as
          ``Concept``, ``Unit``, ``Category``): only the root itself is a
          top-level entity.  Its children — including reusable types that
          happen to be tag-mapped — must **not** be dispatched separately,
          otherwise the subtree would be cleared before the root parser
          could read its own identifier and textual fields.
        """
        with self.path.open("rb") as xml_file:
            context = etree.iterparse(
                xml_file,
                events=("start", "end"),
                recover=self.recover,
                huge_tree=True,
                # Defence in depth against XXE on untrusted input.
                resolve_entities=False,
                load_dtd=False,
                no_network=True,
            )
            root: etree._Element | None = None
            root_is_container = False
            try:
                for event, elem in context:
                    if event == "start":
                        if root is None:
                            root = elem
                            root_is_container = (
                                strip_namespace(root.tag) in _CDI_CONTAINER_ROOT_TAGS
                            )
                        continue
                    parent = elem.getparent()
                    eligible = CDIBatchStream._is_top_level_cdi_entity_element(
                        elem=elem,
                        parent=parent,
                        root=root,
                        root_is_container=root_is_container,
                    )

                    if eligible:
                        tag = strip_namespace(elem.tag)
                        if tag in _CDI_TAG_MAP:
                            record_cls, collection_name, extra_fields = _CDI_TAG_MAP[tag]
                            self.builder.ingest_entity(
                                elem, record_cls, collection_name, extra_fields
                            )
                            maybe_batch = self.builder.flush_if_ready()
                            if maybe_batch:
                                yield maybe_batch
                        # Memory management: clear the top-level element
                        # and trim already-processed siblings from the
                        # root.  Only safe for eligible (top-level)
                        # elements — never for nested ones.
                        elem.clear()
                        if parent is not None:
                            while elem.getprevious() is not None:
                                del parent[0]

                final_batch = self.builder.finalize()
                if final_batch:
                    yield final_batch

            finally:
                close_iterparse_context(context)

    @property
    def totals(self) -> dict[str, int]:
        """Return aggregate totals tracked during iteration."""
        return dict(self.builder.totals)


def parse_cdi_batches(
    path: Path,
    chunk_size: int = 500,
    *,
    recover: bool = True,
) -> Iterable[CDIBatch]:
    """Stream batched CDI entities from a DDI-CDI XML file.

    Args:
        path: Filesystem path to the DDI-CDI XML file.
        chunk_size: Maximum number of records per batch.
        recover: Whether to attempt recovery from XML syntax errors.

    Returns:
        An iterable that yields :class:`CDIBatch` instances.
    """
    return CDIBatchStream(path, chunk_size, recover=recover)


def is_cdi_format(path: Path | str) -> bool:
    """Check whether a file is in DDI-CDI format.

    Detects DDI-CDI by looking for the ``<Wrapper>`` root element or
    CDI-specific namespace URIs.

    Args:
        path: Path to the XML file to check.

    Returns:
        True if the file appears to be DDI-CDI format.
    """
    try:
        with open(path, "rb") as f:
            for _event, elem in etree.iterparse(
                f,
                events=("start",),
                resolve_entities=False,
                load_dtd=False,
                no_network=True,
            ):
                root_tag = strip_namespace(elem.tag)
                tag_str = str(elem.tag)
                elem.clear()
                if root_tag == "Wrapper":
                    return True
                if "ddi-cdi" in tag_str.lower():
                    return True
                # Only check the root element
                break
    except etree.XMLSyntaxError:
        pass
    return False


__all__ = [
    "CDIBatch",
    "CDIBatchBuilder",
    "CDIBatchStream",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRecord",
    "CDIRelationshipRecord",
    "is_cdi_format",
    "parse_cdi_batches",
]

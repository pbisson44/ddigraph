"""DDI-L 3.x FragmentInstance ingestion.

This module handles DDI Lifecycle (DDI-L) FragmentInstance XML files, which have
a fundamentally different structure from DDI Codebook format. In FragmentInstance:

- Each ``<Fragment>`` element contains a reusable DDI component (Instrument,
  Sequence, CodeList, QuestionItem, etc.)
- Components reference each other via ``*Reference`` elements
- The structure forms a directed graph, not a flat dataset-centric star schema

This module now provides:
- Streaming XML parsing with iterparse for memory efficiency
- Batched Neo4j writes using UNWIND for performance
- Full async support with AsyncDriver
- Integration with the GraphWriteAdapter pattern
- Retry logic with exponential backoff
"""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, ClassVar

from lxml import etree  # type: ignore[import-untyped,unused-ignore]
from neo4j import AsyncDriver, Driver

from ddigraph.config import Settings
from ddigraph.logging import get_logger
from ddigraph.metrics import MetricsEmitter, NullMetrics
from ddigraph.paths import validate_readable_xml_path
from ddigraph.schema.definitions import DDISchema
from ddigraph.utils.parsing import (
    close_iterparse_context,
    get_child_text,
    get_nested_text,
    get_text,
    strip_namespace,
)
from ddigraph.utils.retry import retry_transient

logger = get_logger(__name__)


# ============================================================================
# Data Structures
# ============================================================================


def make_node_key(
    agency: str | None,
    id: str,
    version: str | None,
    urn: str | None = None,
) -> str:
    """Return a version-aware identity key for a fragment or reference.

    DDI identity is agency + id + version (the URN), so two fragments that share
    an id but differ in version are distinct objects and must become distinct
    nodes. The verbatim ``urn`` is used when present; otherwise it is composed
    from agency/id/version in the canonical ``urn:ddi:<agency>:<id>:<version>``
    form so that a fragment and the references pointing at it derive the same
    key. Falls back to the bare id when no version is available.
    """
    if urn:
        return urn
    if version:
        return f"urn:ddi:{agency or ''}:{id}:{version}"
    return id


@dataclass
class FragmentReference:
    """A reference to another DDI-L fragment."""

    agency: str | None
    id: str
    version: str | None
    type_of_object: str

    @property
    def qualified_id(self) -> str:
        """Return agency-qualified ID if agency is present."""
        return f"{self.agency}:{self.id}" if self.agency else self.id

    @property
    def node_key(self) -> str:
        """Version-aware identity of the referenced fragment."""
        return make_node_key(self.agency, self.id, self.version)


@dataclass
class Fragment:
    """A DDI-L fragment representing a node in the graph.

    Attributes:
        element_type: The DDI element type (Instrument, Sequence, CodeList, etc.)
        agency: The maintaining agency (e.g., 'ie.cso')
        id: The fragment's unique identifier
        version: Version string
        urn: Full DDI URN if present
        label: Human-readable label
        name: Element name
        properties: Type-specific properties extracted from the element
        references: List of (relationship_type, FragmentReference) tuples
    """

    element_type: str
    agency: str | None
    id: str
    version: str | None
    urn: str | None
    label: str | None
    name: str | None
    properties: dict[str, Any] = field(default_factory=dict)
    references: list[tuple[str, FragmentReference]] = field(default_factory=list)

    @property
    def qualified_id(self) -> str:
        """Return agency-qualified ID if agency is present."""
        return f"{self.agency}:{self.id}" if self.agency else self.id

    @property
    def node_key(self) -> str:
        """Version-aware identity of this fragment (the graph node key)."""
        return make_node_key(self.agency, self.id, self.version, self.urn)

    def to_dict(self) -> dict[str, Any]:
        """Flatten fragment properties into a Cypher-ready parameter mapping.

        Returns:
            Mapping of property name to scalar value suitable for use as
            Cypher ``$params``. Complex (list/dict) values in
            :attr:`properties` and ``None`` values are omitted.
        """
        props = {
            # ``fragment_id`` is the version-aware node key so two versions of
            # the same DDI id stay distinct; the bare DDI id is kept as ``ddi_id``.
            "fragment_id": self.node_key,
            "ddi_id": self.id,
            "agency": self.agency,
            "version": self.version,
            "urn": self.urn,
            "label": self.label,
            "name": self.name,
        }
        # Add non-complex properties
        for key, value in self.properties.items():
            if not isinstance(value, (list, dict)):
                props[key] = value
        # Filter None values
        return {k: v for k, v in props.items() if v is not None}


@dataclass
class FragmentBatch:
    """A batch of parsed fragments ready for writing.

    Attributes:
        fragments_by_type: Dictionary mapping element types to lists of fragments.
        relationships: List of (from_id, rel_type, to_id) tuples.
    """

    fragments_by_type: dict[str, list[Fragment]] = field(default_factory=lambda: defaultdict(list))
    relationships: list[tuple[str, str, str]] = field(default_factory=list)

    def add_fragment(self, fragment: Fragment) -> None:
        """Add a fragment to the batch.

        Args:
            fragment: Fragment to append, grouped by :attr:`Fragment.element_type`.
        """
        self.fragments_by_type[fragment.element_type].append(fragment)

    def add_relationship(self, from_id: str, rel_type: str, to_id: str) -> None:
        """Record a directional relationship between two fragments.

        Args:
            from_id: Fragment ID at the relationship's start.
            rel_type: Relationship type label (e.g. ``HAS_CONSTRUCT``).
            to_id: Fragment ID at the relationship's end.
        """
        self.relationships.append((from_id, rel_type, to_id))

    def total_fragments(self) -> int:
        """Return the total number of fragments held across all types."""
        return sum(len(frags) for frags in self.fragments_by_type.values())

    def clear(self) -> None:
        """Drop all buffered fragments and relationships so the batch can be reused."""
        self.fragments_by_type.clear()
        self.relationships.clear()


# ============================================================================
# Streaming Fragment Parser
# ============================================================================


class DDIFragmentParser:
    """Streaming parser for DDI-L FragmentInstance XML files.

    This parser uses iterparse to stream through the XML file, keeping memory usage
    bounded regardless of file size. Fragments are yielded in batches for efficient
    Neo4j ingestion.
    """

    # Response domain type mapping (tag -> human-readable type string)
    RESPONSE_DOMAIN_TYPES: ClassVar[dict[str, str]] = {
        "CodeDomain": "code",
        "TextDomain": "text",
        "NumericDomain": "numeric",
        "DateTimeDomain": "datetime",
        "ScaleDomain": "scale",
        "GeographicDomain": "geographic",
        "DistributionDomain": "distribution",
        "LocationDomain": "location",
        "RankingDomain": "ranking",
        "NominalDomain": "nominal",
    }

    # Representation type mapping (tag -> human-readable type string)
    REPRESENTATION_TYPES: ClassVar[dict[str, str]] = {
        "CodeRepresentation": "code",
        "TextRepresentation": "text",
        "NumericRepresentation": "numeric",
        "DateTimeRepresentation": "datetime",
    }

    # Element-type-specific name tags
    NAME_TAGS: ClassVar[dict[str, list[str]]] = {
        "Instrument": ["InstrumentName"],
        "CodeList": ["CodeListName", "Name"],
        "Category": ["CategoryName", "Name"],
        "Sequence": ["ConstructName", "Name"],
        "QuestionItem": ["QuestionItemName", "Name"],
        "QuestionGrid": ["QuestionGridName", "Name"],
        "QuestionConstruct": ["ConstructName", "Name"],
        "IfThenElse": ["ConstructName", "Name"],
        "Loop": ["ConstructName", "Name"],
        "RepeatWhile": ["ConstructName", "Name"],
        "RepeatUntil": ["ConstructName", "Name"],
        "StatementItem": ["ConstructName", "Name"],
        "ComputationItem": ["ConstructName", "Name"],
        "MeasurementConstruct": ["ConstructName", "Name"],
        "MeasurementItem": ["MeasurementItemName", "Name"],
        # New element types from LFS.xml
        "Variable": ["VariableName", "Name"],
        "ResourcePackage": ["Name"],
        "StudyUnit": ["Name"],
        "DataCollection": ["Name"],
        "PhysicalInstance": ["Name"],
        "DataRelationship": ["DataRelationshipName", "Name"],
        "LogicalRecord": ["LogicalRecordName", "Name"],
        "ConceptualVariable": ["ConceptualVariableName", "Name"],
        "RepresentedVariable": ["RepresentedVariableName", "Name"],
        "RepresentedVariableGroup": ["RepresentedVariableGroupName", "Name"],
        "CategoryScheme": ["CategorySchemeName", "Name"],
        "CategoryGroup": ["CategoryGroupName", "Name"],
        "Concept": ["ConceptName", "Name"],
        "Universe": ["UniverseName", "Name"],
        "Methodology": ["Name"],
        "OtherMaterial": ["Name"],
        # Previously in FRAGMENT_NODES but missing from NAME_TAGS
        "SamplingProcedure": ["SamplingProcedureName", "Name"],
        "DataCollectionMethodology": ["Name"],
        "RepresentedVariableScheme": ["RepresentedVariableSchemeName", "Name"],
        # Scheme types (datacollection.xsd)
        "QuestionScheme": ["QuestionSchemeName", "Name"],
        "ControlConstructScheme": ["ControlConstructSchemeName", "Name"],
        "InstrumentScheme": ["InstrumentSchemeName", "Name"],
        "InterviewerInstructionScheme": ["InterviewerInstructionSchemeName", "Name"],
        "ProcessingEventScheme": ["ProcessingEventSchemeName", "Name"],
        "ProcessingInstructionScheme": ["ProcessingInstructionSchemeName", "Name"],
        "DevelopmentActivityScheme": ["DevelopmentActivitySchemeName", "Name"],
        "MeasurementScheme": ["MeasurementSchemeName", "Name"],
        "SamplingInformationScheme": ["SamplingInformationSchemeName", "Name"],
        # Scheme types (logicalproduct.xsd)
        "CodeListScheme": ["CodeListSchemeName", "Name"],
        "NCubeScheme": ["NCubeSchemeName", "Name"],
        "VariableScheme": ["VariableSchemeName", "Name"],
        # Scheme types (conceptualcomponent.xsd)
        "ConceptScheme": ["ConceptSchemeName", "Name"],
        "UniverseScheme": ["UniverseSchemeName", "Name"],
        "ConceptualVariableScheme": ["ConceptualVariableSchemeName", "Name"],
        "GeographicStructureScheme": ["GeographicStructureSchemeName", "Name"],
        "GeographicLocationScheme": ["GeographicLocationSchemeName", "Name"],
        "UnitTypeScheme": ["UnitTypeSchemeName", "Name"],
        # Control construct subtypes (datacollection.xsd)
        "Split": ["ConstructName", "Name"],
        "SplitJoin": ["ConstructName", "Name"],
        "DevelopmentStep": ["ConstructName", "Name"],
        "SamplingStage": ["ConstructName", "Name"],
        "SampleStep": ["ConstructName", "Name"],
        # Development activities & archive types
        "DevelopmentActivity": ["Name"],
        "Individual": ["Name"],
        "Access": ["Name"],
        "Collection": ["Name"],
        # Module-level maintainables
        "ConceptualComponent": ["Name"],
        "LogicalProduct": ["Name"],
        "PhysicalDataProduct": ["Name"],
        "Archive": ["Name"],
        "DDIProfile": ["Name"],
        "LocalHoldingPackage": ["Name"],
        # Classification types
        "ClassificationFamily": ["ClassificationFamilyName", "Name"],
        "StatisticalClassification": ["Name"],
        "ClassificationItem": ["ClassificationItemName", "Name"],
        # Geographic types
        "GeographicStructure": ["GeographicStructureName", "Name"],
        "GeographicLocation": ["GeographicLocationName", "Name"],
        # Group types
        "ConceptGroup": ["ConceptGroupName", "Name"],
        "UniverseGroup": ["UniverseGroupName", "Name"],
        "ConceptualVariableGroup": ["ConceptualVariableGroupName", "Name"],
        # Unit types
        "UnitType": ["UnitTypeName", "Name"],
        "UnitTypeGroup": ["UnitTypeGroupName", "Name"],
        # Variable group (DDI-L 3.x name)
        "VariableGroup": ["VariableGroupName", "Name"],
        # NCube types (logicalproduct.xsd)
        "NCube": ["NCubeName", "Name"],
        "NCubeGroup": ["NCubeGroupName", "Name"],
        # Physical data
        "PhysicalStructure": ["PhysicalStructureName", "Name"],
        "RecordLayout": ["RecordLayoutName", "Name"],
        # Archive organization type
        "Organization": ["OrganizationName", "Name"],
        # Study group container (group.xsd)
        "Group": ["Name"],
        # Complex question
        "QuestionBlock": ["QuestionBlockName", "Name"],
        # ---- Auto-extended: real XSD coverage ----
        "ActionToMinimizeLosses": ["ActionToMinimizeLossesName", "Name"],
        "AggregationVariables": ["AggregationVariablesName", "Name"],
        "ApprovalReview": ["ApprovalReviewName", "Name"],
        "ApprovalReviewDocument": ["ApprovalReviewDocumentName", "Name"],
        "Attribute": ["AttributeName", "Name"],
        "AuthorizedSource": ["AuthorizedSourceName", "Name"],
        "CategoryMap": ["CategoryMapName", "Name"],
        "ClassificationCorrespondenceTable": ["ClassificationCorrespondenceTableName", "Name"],
        "ClassificationIndex": ["ClassificationIndexName", "Name"],
        "ClassificationLevel": ["ClassificationLevelName", "Name"],
        "ClassificationSeries": ["ClassificationSeriesName", "Name"],
        "Code": ["CodeName", "Name"],
        "CodeListGroup": ["CodeListGroupName", "Name"],
        "CognitiveExpertReviewActivity": ["CognitiveExpertReviewActivityName", "Name"],
        "CognitiveInterviewActivity": ["CognitiveInterviewActivityName", "Name"],
        "CollectionEvent": ["CollectionEventName", "Name"],
        "CollectionSituation": ["CollectionSituationName", "Name"],
        "Comparison": ["ComparisonName", "Name"],
        "ConceptMap": ["ConceptMapName", "Name"],
        "ContentReviewActivity": ["ContentReviewActivityName", "Name"],
        "ControlConstructGroup": ["ControlConstructGroupName", "Name"],
        "CoordinateRegion": ["CoordinateRegionName", "Name"],
        "DDIInstance": ["DDIInstanceName", "Name"],
        "DataCaptureDevelopment": ["DataCaptureDevelopmentName", "Name"],
        "DataSet": ["DataSetName", "Name"],
        "DefaultAccess": ["DefaultAccessName", "Name"],
        "DevelopmentActivityGroup": ["DevelopmentActivityGroupName", "Name"],
        "DevelopmentImplementation": ["DevelopmentImplementationName", "Name"],
        "DevelopmentPlan": ["DevelopmentPlanName", "Name"],
        "DevelopmentResults": ["DevelopmentResultsName", "Name"],
        "DeviationFromSampleDesign": ["DeviationFromSampleDesignName", "Name"],
        "Embargo": ["EmbargoName", "Name"],
        "FocusGroupActivity": ["FocusGroupActivityName", "Name"],
        "FundingDocument": ["FundingDocumentName", "Name"],
        "GeneralInstruction": ["GeneralInstructionName", "Name"],
        "GenerationInstruction": ["GenerationInstructionName", "Name"],
        "GeographicLevel": ["GeographicLevelName", "Name"],
        "GeographicLocationGroup": ["GeographicLocationGroupName", "Name"],
        "GeographicStructureGroup": ["GeographicStructureGroupName", "Name"],
        "GrossFileStructure": ["GrossFileStructureName", "Name"],
        "GrossRecordStructure": ["GrossRecordStructureName", "Name"],
        "InParameter": ["InParameterName", "Name"],
        "InformationClassification": ["InformationClassificationName", "Name"],
        "Instruction": ["InstructionName", "Name"],
        "InstructionGroup": ["InstructionGroupName", "Name"],
        "InstrumentGroup": ["InstrumentGroupName", "Name"],
        "ItemMap": ["ItemMapName", "Name"],
        "LifecycleEvent": ["LifecycleEventName", "Name"],
        "LocalGroupContent": ["LocalGroupContentName", "Name"],
        "LocalResourcePackageContent": ["LocalResourcePackageContentName", "Name"],
        "LocalStudyUnitContent": ["LocalStudyUnitContentName", "Name"],
        "LocationValue": ["LocationValueName", "Name"],
        "ManagedDateTimeRepresentation": ["ManagedDateTimeRepresentationName", "Name"],
        "ManagedItemMap": ["ManagedItemMapName", "Name"],
        "ManagedMissingValuesRepresentation": ["ManagedMissingValuesRepresentationName", "Name"],
        "ManagedNumericRepresentation": ["ManagedNumericRepresentationName", "Name"],
        "ManagedRepresentationGroup": ["ManagedRepresentationGroupName", "Name"],
        "ManagedRepresentationScheme": ["ManagedRepresentationSchemeName", "Name"],
        "ManagedScaleRepresentation": ["ManagedScaleRepresentationName", "Name"],
        "ManagedTextRepresentation": ["ManagedTextRepresentationName", "Name"],
        "MeasureDefinition": ["MeasureDefinitionName", "Name"],
        "MeasurementGroup": ["MeasurementGroupName", "Name"],
        "ModeOfCollection": ["ModeOfCollectionName", "Name"],
        "NCubeInstance": ["NCubeInstanceName", "Name"],
        "OrganizationGroup": ["OrganizationGroupName", "Name"],
        "OrganizationScheme": ["OrganizationSchemeName", "Name"],
        "OtherMaterialGroup": ["OtherMaterialGroupName", "Name"],
        "OtherMaterialScheme": ["OtherMaterialSchemeName", "Name"],
        "OutParameter": ["OutParameterName", "Name"],
        "PhysicalInstanceGroup": ["PhysicalInstanceGroupName", "Name"],
        "PhysicalRecordSegment": ["PhysicalRecordSegmentName", "Name"],
        "PhysicalStructureGroup": ["PhysicalStructureGroupName", "Name"],
        "PhysicalStructureScheme": ["PhysicalStructureSchemeName", "Name"],
        "PretestActivity": ["PretestActivityName", "Name"],
        "ProcessingEvent": ["ProcessingEventName", "Name"],
        "ProcessingEventGroup": ["ProcessingEventGroupName", "Name"],
        "ProcessingInstructionGroup": ["ProcessingInstructionGroupName", "Name"],
        "QualityScheme": ["QualitySchemeName", "Name"],
        "QualityStandard": ["QualityStandardName", "Name"],
        "QualityStandardGroup": ["QualityStandardGroupName", "Name"],
        "QualityStatement": ["QualityStatementName", "Name"],
        "QualityStatementGroup": ["QualityStatementGroupName", "Name"],
        "QuestionGroup": ["QuestionGroupName", "Name"],
        "QuestionMap": ["QuestionMapName", "Name"],
        "RecordLayoutGroup": ["RecordLayoutGroupName", "Name"],
        "RecordLayoutScheme": ["RecordLayoutSchemeName", "Name"],
        "RecordRelationship": ["RecordRelationshipName", "Name"],
        "Relation": ["RelationName", "Name"],
        "RepresentationMap": ["RepresentationMapName", "Name"],
        "Sample": ["SampleName", "Name"],
        "SampleFrame": ["SampleFrameName", "Name"],
        "SampleFrameAccess": ["SampleFrameAccessName", "Name"],
        "SamplingInformationGroup": ["SamplingInformationGroupName", "Name"],
        "SamplingPlan": ["SamplingPlanName", "Name"],
        "SpatialCoverage": ["SpatialCoverageName", "Name"],
        "StandardWeight": ["StandardWeightName", "Name"],
        "SubUniverseClass": ["SubUniverseClassName", "Name"],
        "TemporalCoverage": ["TemporalCoverageName", "Name"],
        "TimeMethod": ["TimeMethodName", "Name"],
        "TopicalCoverage": ["TopicalCoverageName", "Name"],
        "TranslationActivity": ["TranslationActivityName", "Name"],
        "UniverseMap": ["UniverseMapName", "Name"],
        "VariableMap": ["VariableMapName", "Name"],
        "VariableStatistics": ["VariableStatisticsName", "Name"],
        "Weighting": ["WeightingName", "Name"],
        "WeightingMethodology": ["WeightingMethodologyName", "Name"],
    }

    def __init__(
        self,
        path: Path,
        *,
        chunk_size: int = 200,
        metrics: MetricsEmitter | None = None,
        recover: bool = True,
    ):
        """Initialize the parser.

        Args:
            path: Path to the DDI-L FragmentInstance XML file.
            chunk_size: Number of fragments to collect before yielding a batch.
            metrics: Optional metrics emitter for observability.
            recover: If True, attempt to recover from XML parsing errors.
        """
        self.path = path
        self.chunk_size = chunk_size
        self.metrics = metrics or NullMetrics()
        self.recover = recover
        self.top_level_ref: FragmentReference | None = None
        # Version-aware node keys (URN-based) of every fragment seen.
        self._node_keys: set[str] = set()
        # Bare DDI id -> ordered node keys, for resolving references that omit a
        # version or point at a version that is not present (fallback matching).
        self._keys_by_id: dict[str, list[str]] = defaultdict(list)
        # Count of true duplicates (same id *and* version) that were skipped.
        self._duplicate_fragment_count = 0
        self._totals: dict[str, int] = defaultdict(int)

    def parse_batches(self) -> Iterator[FragmentBatch]:
        """Parse the FragmentInstance file and yield batches of fragments.

        Uses a two-phase approach:
        1. First phase: Parse all fragments and collect node data
        2. Second phase: Resolve relationships now that all fragment IDs are known

        This ensures forward references (A -> B where B appears later) are handled.

        Yields:
            FragmentBatch objects containing parsed fragments and relationships.
        """
        start_time = perf_counter()
        logger.info("Parsing DDI-L FragmentInstance", extra={"path": str(self.path)})

        # Phase 1: Parse all fragments, yield node-only batches
        all_fragments: list[Fragment] = []
        batch = FragmentBatch()
        fragment_count = 0

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
                    tag = strip_namespace(elem.tag)

                    if tag == "TopLevelReference" and self.top_level_ref is None:
                        self.top_level_ref = self._parse_reference(elem)

                    elif tag == "Fragment":
                        fragment = self._parse_fragment(elem)
                        if fragment and fragment.node_key in self._node_keys:
                            # Same id *and* version -> a genuine duplicate (not two
                            # distinct versions). Keep the first and skip this one so
                            # the uniqueness constraint is not violated; surface it.
                            self._duplicate_fragment_count += 1
                            logger.warning(
                                "Duplicate fragment (same id and version); "
                                "keeping first occurrence and skipping later one",
                                extra={
                                    "fragment_id": fragment.node_key,
                                    "ddi_id": fragment.id,
                                    "element_type": fragment.element_type,
                                    "version": fragment.version,
                                },
                            )
                        elif fragment:
                            batch.add_fragment(fragment)
                            all_fragments.append(fragment)
                            self._node_keys.add(fragment.node_key)
                            self._keys_by_id[fragment.id].append(fragment.node_key)
                            self._totals[fragment.element_type] += 1
                            fragment_count += 1

                            # Yield batch when threshold reached (nodes only, no relationships yet)
                            if batch.total_fragments() >= self.chunk_size:
                                yield batch
                                batch = FragmentBatch()

                        # Clear processed element to free memory
                        elem.clear()
                        parent = elem.getparent()
                        if parent is not None:
                            while elem.getprevious() is not None:
                                del parent[0]

                # Yield final node batch
                if batch.total_fragments() > 0:
                    yield batch

            finally:
                close_iterparse_context(context)

        # Phase 2: Now that all fragment IDs are known, resolve relationships
        logger.debug(
            "Resolving relationships",
            extra={"fragment_count": len(all_fragments), "known_ids": len(self._node_keys)},
        )

        rel_batch = FragmentBatch()
        for fragment in all_fragments:
            for rel_type, ref in fragment.references:
                target = self._resolve_reference(ref)
                # Only create relationships to fragments that exist
                if target is not None:
                    rel_batch.add_relationship(fragment.node_key, rel_type, target)

                    # Yield relationship batches to avoid memory buildup
                    if len(rel_batch.relationships) >= self.chunk_size:
                        yield rel_batch
                        rel_batch = FragmentBatch()

        # Yield final relationship batch
        if rel_batch.relationships:
            yield rel_batch

        elapsed = perf_counter() - start_time
        self.metrics.observe("fragment_parse_time", elapsed)
        self.metrics.increment("fragments_parsed", fragment_count)

        logger.info(
            "Parsed DDI-L FragmentInstance",
            extra={
                "path": str(self.path),
                "fragment_count": fragment_count,
                "elapsed_seconds": round(elapsed, 3),
            },
        )

    def _resolve_reference(self, ref: FragmentReference) -> str | None:
        """Resolve a reference to the node key of an existing fragment.

        Prefers an exact version-aware match (same id and version). When the
        reference omits a version or points at a version that is not present,
        falls back to the most recently seen fragment with the same id so the
        edge still resolves rather than being dropped. Returns ``None`` when no
        fragment with the referenced id exists.
        """
        key = ref.node_key
        if key in self._node_keys:
            return key
        candidates = self._keys_by_id.get(ref.id)
        if candidates:
            # Fallback: reference version is missing or unknown -> link to the
            # latest fragment seen for this id.
            return candidates[-1]
        return None

    def _parse_reference(self, elem: etree._Element) -> FragmentReference | None:
        """Parse a *Reference element into a FragmentReference."""
        agency = get_child_text(elem, "Agency")
        ref_id = get_child_text(elem, "ID")
        version = get_child_text(elem, "Version")
        type_of_object = get_child_text(elem, "TypeOfObject")

        if ref_id and type_of_object:
            return FragmentReference(
                agency=agency,
                id=ref_id,
                version=version,
                type_of_object=type_of_object,
            )
        return None

    def _parse_fragment(self, fragment_elem: etree._Element) -> Fragment | None:
        """Parse a single Fragment element."""
        # The actual content is the first non-Fragment child
        content_elem = None
        for child in fragment_elem:
            tag = strip_namespace(child.tag)
            if tag != "Fragment":
                content_elem = child
                break

        if content_elem is None:
            return None

        element_type = strip_namespace(content_elem.tag)

        # Extract identifiers
        agency = get_child_text(content_elem, "Agency")
        frag_id = get_child_text(content_elem, "ID")
        version = get_child_text(content_elem, "Version")
        urn = get_child_text(content_elem, "URN")

        if not frag_id:
            return None

        # Extract label and name
        label = get_nested_text(content_elem, "Label")
        name = self._extract_name(content_elem, element_type)

        # Create fragment
        fragment = Fragment(
            element_type=element_type,
            agency=agency,
            id=frag_id,
            version=version,
            urn=urn,
            label=label,
            name=name,
        )

        # Extract references (stored temporarily, resolved later)
        self._extract_references(content_elem, fragment)

        # Extract type-specific properties
        self._extract_properties(content_elem, fragment)

        return fragment

    def _extract_name(self, elem: etree._Element, element_type: str) -> str | None:
        """Extract the name field based on element type."""
        name_tags = self.NAME_TAGS.get(element_type, ["Name"])
        for tag in name_tags:
            name = get_nested_text(elem, tag)
            if name:
                return name
        return None

    def _extract_references(self, elem: etree._Element, fragment: Fragment) -> None:
        """Extract structural and semantic references from an element.

        Extracts two types of references:

        1. Structural references (control flow):
           - Direct children that are *Reference elements
           - References inside specific structural containers (IfCondition, etc.)
           - ElseIf branches in IfThenElse constructs

        2. Semantic references (data relationships):
           - QuestionItem -> CodeList via CodeDomain/CodeListReference
           - CodeList -> Category via Code/CategoryReference

        Does NOT extract references nested inside:
        - OutParameter/InParameter (these are data flow parameters, not structure)
        - Binding elements
        """
        element_type = fragment.element_type

        # Tags to skip for structural extraction
        skip_containers = {
            "OutParameter",
            "InParameter",
            "Binding",
            "SourceParameter",
            "TargetParameter",
            "ParameterLinkage",
            "SourceLogicalRecord",
            "TargetLogicalRecord",
            "CodeRepresentation",
            "TextRepresentation",
            "NumericRepresentation",
            "DateTimeRepresentation",
            "ResponseDomain",
            "Code",  # Handle Code separately for CodeList -> Category
            "CodeDomain",  # Handle CodeDomain separately for QuestionItem -> CodeList
            "ElseIf",  # Handle ElseIf separately for IfThenElse
            "VariableRepresentation",  # Handle separately for Variable -> CodeList
        }

        # Tags that ARE structural containers (extract references from inside)
        structural_containers = {
            "IfCondition",
            "LoopCondition",
            "UntilCondition",
            "WhileCondition",
            "ExternalAid",
            "InterviewerInstructionReference",
            "BasedOnObject",
            "RequiredResourcePackages",  # StudyUnit -> ResourcePackage
            "LogicalRecord",  # LogicalRecord -> Variable via VariableUsedReference
        }

        # === Structural references (direct children) ===
        for child in elem:
            child_tag = strip_namespace(child.tag)

            # Skip containers that hold non-structural references
            if child_tag in skip_containers:
                continue

            # If it's a reference element, extract it
            if child_tag.endswith("Reference"):
                ref = self._parse_reference(child)
                if ref:
                    rel_type = DDISchema.get_fragment_relationship_type(child_tag)
                    fragment.references.append((rel_type, ref))

            # If it's a structural container, look one level deeper
            elif child_tag in structural_containers:
                for subchild in child:
                    subchild_tag = strip_namespace(subchild.tag)
                    if subchild_tag.endswith("Reference"):
                        ref = self._parse_reference(subchild)
                        if ref:
                            rel_type = DDISchema.get_fragment_relationship_type(subchild_tag)
                            fragment.references.append((rel_type, ref))

        # === ElseIf branches (IfThenElse only) ===
        # ElseIf contains IfCondition and ThenConstructReference
        if element_type == "IfThenElse":
            for child in elem:
                if strip_namespace(child.tag) == "ElseIf":
                    for subchild in child:
                        subchild_tag = strip_namespace(subchild.tag)
                        if subchild_tag == "ThenConstructReference":
                            ref = self._parse_reference(subchild)
                            if ref:
                                # ElseIf branches use ELSE_IF relationship
                                fragment.references.append(("ELSE_IF", ref))

        # === Semantic references (type-specific) ===

        # QuestionItem/QuestionGrid -> CodeList via CodeDomain
        if element_type in ("QuestionItem", "QuestionGrid"):
            for child in elem:
                child_tag = strip_namespace(child.tag)
                if child_tag == "CodeDomain":
                    # Look for CodeListReference inside CodeDomain
                    for subchild in child:
                        if strip_namespace(subchild.tag) == "CodeListReference":
                            ref = self._parse_reference(subchild)
                            if ref:
                                fragment.references.append(("USES_CODELIST", ref))
                            break  # Only one CodeListReference per CodeDomain

        # CodeList -> Category via Code/CategoryReference
        elif element_type == "CodeList":
            for child in elem:
                child_tag = strip_namespace(child.tag)
                if child_tag == "Code":
                    # Look for CategoryReference inside Code
                    for subchild in child:
                        if strip_namespace(subchild.tag) == "CategoryReference":
                            ref = self._parse_reference(subchild)
                            if ref:
                                fragment.references.append(("HAS_CATEGORY", ref))
                            break  # Only one CategoryReference per Code

        # Variable -> CodeList via VariableRepresentation/CodeRepresentation/CodeListReference
        elif element_type == "Variable":
            for child in elem:
                child_tag = strip_namespace(child.tag)
                if child_tag == "VariableRepresentation":
                    for subchild in child:
                        subchild_tag = strip_namespace(subchild.tag)
                        if subchild_tag == "CodeRepresentation":
                            # Look for CodeListReference inside CodeRepresentation
                            for sub2 in subchild:
                                if strip_namespace(sub2.tag) == "CodeListReference":
                                    ref = self._parse_reference(sub2)
                                    if ref:
                                        fragment.references.append(("USES_CODELIST", ref))
                                    break

        # RepresentedVariable -> CategoryScheme via CategorySchemeReference
        # (CategoryScheme contains the categories that define valid values)
        elif element_type == "RepresentedVariable":
            for child in elem:
                child_tag = strip_namespace(child.tag)
                if child_tag == "CategorySchemeReference":
                    ref = self._parse_reference(child)
                    if ref:
                        fragment.references.append(("USES_CATEGORY_SCHEME", ref))

        # DataRelationship -> Variable via LogicalRecord/VariableUsedReference
        # DataRelationship contains LogicalRecord elements, which contain VariableUsedReference
        elif element_type == "DataRelationship":
            for child in elem:
                child_tag = strip_namespace(child.tag)
                if child_tag == "LogicalRecord":
                    for subchild in child.iter():
                        if strip_namespace(subchild.tag) == "VariableUsedReference":
                            ref = self._parse_reference(subchild)
                            if ref:
                                fragment.references.append(("USES_VARIABLE", ref))

    def _extract_properties(self, elem: etree._Element, fragment: Fragment) -> None:
        """Extract type-specific properties from the element."""
        element_type = fragment.element_type

        if element_type == "CodeList":
            codes = []
            for child in elem.iter():
                if strip_namespace(child.tag) == "Code":
                    value = get_child_text(child, "Value")
                    if value:
                        codes.append(value)
            if codes:
                fragment.properties["code_count"] = len(codes)

        elif element_type == "Category":
            cat_label = get_nested_text(elem, "CategoryName", "Label")
            if cat_label:
                fragment.properties["category_label"] = cat_label

        elif element_type == "QuestionItem":
            for child in elem.iter():
                if strip_namespace(child.tag) in ("QuestionText", "LiteralText"):
                    text = get_nested_text(child, "Text", "String")
                    if text:
                        fragment.properties["question_text"] = text[:1000]
                        break
            # Extract response domain type
            for child in elem:
                domain = self.RESPONSE_DOMAIN_TYPES.get(strip_namespace(child.tag))
                if domain:
                    fragment.properties["response_type"] = domain
                    break

        elif element_type == "QuestionGrid":
            # Extract response domain type for grids too
            for child in elem.iter():
                domain = self.RESPONSE_DOMAIN_TYPES.get(strip_namespace(child.tag))
                if domain:
                    fragment.properties["response_type"] = domain
                    break

        elif element_type == "IfThenElse":
            for child in elem.iter():
                if strip_namespace(child.tag) == "IfCondition":
                    for sub in child.iter():
                        if strip_namespace(sub.tag) in ("Expression", "Code", "Command"):
                            text = get_text(sub)
                            if text:
                                fragment.properties["condition"] = text[:500]
                                break

        elif element_type == "Sequence":
            construct_count = sum(
                1
                for _, ref in fragment.references
                if ref.type_of_object
                in (
                    "Sequence",
                    "IfThenElse",
                    "QuestionConstruct",
                    "MeasurementConstruct",
                    "Loop",
                    "RepeatWhile",
                    "RepeatUntil",
                    "StatementItem",
                    "ComputationItem",
                )
            )
            if construct_count > 0:
                fragment.properties["construct_count"] = construct_count

        elif element_type == "MeasurementItem":
            # Extract measurement text similar to QuestionItem
            for child in elem.iter():
                if strip_namespace(child.tag) in ("MeasurementText", "LiteralText"):
                    text = get_nested_text(child, "Text", "String")
                    if text:
                        fragment.properties["measurement_text"] = text[:1000]
                        break

        elif element_type in ("RepeatWhile", "RepeatUntil"):
            # Extract condition from WhileCondition or UntilCondition
            condition_tag = "WhileCondition" if element_type == "RepeatWhile" else "UntilCondition"
            for child in elem.iter():
                if strip_namespace(child.tag) == condition_tag:
                    for sub in child.iter():
                        if strip_namespace(sub.tag) in ("Expression", "Code", "Command"):
                            text = get_text(sub)
                            if text:
                                fragment.properties["condition"] = text[:500]
                                break

        elif element_type == "Loop":
            # Extract loop condition from LoopWhile
            for child in elem.iter():
                if strip_namespace(child.tag) == "LoopWhile":
                    for sub in child.iter():
                        if strip_namespace(sub.tag) in ("Expression", "Code", "Command"):
                            text = get_text(sub)
                            if text:
                                fragment.properties["condition"] = text[:500]
                                break

        elif element_type == "Variable":
            # Extract variable representation type
            for child in elem:
                if strip_namespace(child.tag) == "VariableRepresentation":
                    for sub in child:
                        rep_type = self.REPRESENTATION_TYPES.get(strip_namespace(sub.tag))
                        if rep_type:
                            fragment.properties["representation_type"] = rep_type
                            break

        elif element_type == "StudyUnit":
            # Extract study title from Citation
            for child in elem.iter():
                if strip_namespace(child.tag) == "Title":
                    title = get_nested_text(child, "String")
                    if title:
                        fragment.properties["title"] = title[:500]
                        break

        elif element_type == "ResourcePackage":
            # Extract title from Citation
            for child in elem.iter():
                if strip_namespace(child.tag) == "Title":
                    title = get_nested_text(child, "String")
                    if title:
                        fragment.properties["title"] = title[:500]
                        break

        elif element_type == "CategoryScheme":
            # Count categories in scheme
            category_count = sum(
                1 for _ in elem.iter() if strip_namespace(getattr(_, "tag", "")) == "Category"
            )
            if category_count > 0:
                fragment.properties["category_count"] = category_count

    @property
    def totals(self) -> dict[str, int]:
        """Return counts by element type."""
        return dict(self._totals)

    def get_summary(self) -> dict[str, Any]:
        """Return a summary of parsed content."""
        return {
            "fragment_count": sum(self._totals.values()),
            "types": dict(self._totals),
            "entry_point": self.top_level_ref.node_key if self.top_level_ref else None,
        }


# ============================================================================
# Async Neo4j Writer with Batching
# ============================================================================


class AsyncFragmentGraphWriter:
    """Async writer for DDI-L fragments with batched Cypher operations.

    This writer uses UNWIND-based Cypher queries for efficient batch writes and supports
    both sync and async Neo4j drivers.
    """

    def __init__(
        self,
        driver: Driver | AsyncDriver,
        settings: Settings | None = None,
        *,
        metrics: MetricsEmitter | None = None,
    ):
        """Initialize the writer.

        Args:
            driver: Neo4j driver instance (sync or async).
            settings: Optional settings for database and retry configuration.
            metrics: Optional metrics emitter.
        """
        self.driver = driver
        self.settings = settings or Settings()
        self.metrics = metrics or NullMetrics()
        self._is_async = hasattr(driver, "execute_query") and inspect.iscoroutinefunction(
            getattr(driver, "execute_query", None)
        )

    async def write_batch(self, batch: FragmentBatch) -> dict[str, int]:
        """Write a batch of fragments to Neo4j.

        Args:
            batch: FragmentBatch containing fragments and relationships.

        Returns:
            Dictionary with counts of created nodes and relationships.
        """
        if self.settings.dry_run:
            logger.debug("Dry run mode - skipping Neo4j writes")
            return {"dry_run": True}

        counts: dict[str, int] = defaultdict(int)
        database = self.settings.neo4j_database

        # Write nodes by type using batched UNWIND
        for element_type, fragments in batch.fragments_by_type.items():
            if not fragments:
                continue

            params = [f.to_dict() for f in fragments]
            await self._write_nodes_batch(element_type, params, database)
            counts[element_type] = len(fragments)

        # Write relationships in batches
        if batch.relationships:
            await self._write_relationships_batch(batch.relationships, database)
            counts["relationships"] = len(batch.relationships)

        return dict(counts)

    async def _write_nodes_batch(
        self,
        element_type: str,
        params: list[dict[str, Any]],
        database: str,
    ) -> None:
        """Write a batch of nodes of the same type using UNWIND."""
        cypher = f"""
            UNWIND $batch AS props
            MERGE (n:{element_type} {{fragment_id: props.fragment_id}})
            SET n += props
        """
        await self._execute_with_retry(cypher, {"batch": params}, database)

    async def _write_relationships_batch(
        self,
        relationships: list[tuple[str, str, str]],
        database: str,
    ) -> None:
        """Write a batch of relationships using UNWIND."""
        # Group relationships by type for more efficient queries
        by_type: dict[str, list[dict[str, str]]] = defaultdict(list)
        for from_id, rel_type, to_id in relationships:
            by_type[rel_type].append({"from_id": from_id, "to_id": to_id})

        for rel_type, rels in by_type.items():
            cypher = f"""
                UNWIND $batch AS rel
                MATCH (from {{fragment_id: rel.from_id}})
                MATCH (to {{fragment_id: rel.to_id}})
                MERGE (from)-[:{rel_type}]->(to)
            """
            await self._execute_with_retry(cypher, {"batch": rels}, database)

    async def _execute_with_retry(
        self,
        cypher: str,
        params: dict[str, Any],
        database: str,
    ) -> None:
        """Execute a Cypher query with retry logic."""
        await retry_transient(
            lambda: self._execute(cypher, params, database),
            attempts=self.settings.write_retry_attempts,
            base_delay=self.settings.write_retry_base_delay,
            jitter=self.settings.write_retry_jitter,
            retry_metric="fragment.batch_write_retries",
            log_prefix="Fragment batch write",
            metrics=self.metrics,
        )

    async def _execute(
        self,
        cypher: str,
        params: dict[str, Any],
        database: str,
    ) -> None:
        """Execute a Cypher query."""
        if isinstance(self.driver, AsyncDriver):
            async with self.driver.session(database=database) as session:
                await session.run(cypher, params)
        else:
            # Sync driver - run in executor
            sync_driver: Driver = self.driver

            def _sync_execute() -> None:
                with sync_driver.session(database=database) as session:
                    session.run(cypher, params).consume()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _sync_execute)

    async def mark_entry_point(self, entry_id: str, database: str) -> None:
        """Mark the entry point node with an additional label."""
        cypher = "MATCH (n {fragment_id: $entry_id}) SET n:EntryPoint"
        await self._execute(cypher, {"entry_id": entry_id}, database)

    async def mark_entry_points(self, database: str) -> None:
        """Label every survey root (Instrument/StudyUnit) as an EntryPoint.

        A FragmentInstance declares a single TopLevelReference, but a file -- or
        an accumulated multi-file graph -- can contain many survey roots. Marking
        each Instrument and StudyUnit makes them all discoverable as traversal
        entry points regardless of how many files were loaded.
        """
        for label in ("Instrument", "StudyUnit"):
            await self._execute(f"MATCH (n:{label}) SET n:EntryPoint", {}, database)

    async def purge_fragments(self, database: str) -> None:
        """Delete all fragment nodes and relationships."""
        # Get all fragment node labels
        labels = [node.label for node in DDISchema.FRAGMENT_NODES]
        for label in labels:
            cypher = f"MATCH (n:{label}) DETACH DELETE n"
            await self._execute(cypher, {}, database)


# ============================================================================
# High-Level Async Loader API
# ============================================================================


class DDIFragmentLoader:
    """High-level async loader for DDI-L FragmentInstance files.

    This class provides a streaming, batched, async interface for loading
    DDI-L FragmentInstance XML files into Neo4j.

    Example:
        >>> from neo4j import AsyncGraphDatabase
        >>> from pathlib import Path
        >>> driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "pw"))
        >>> loader = DDIFragmentLoader(driver)
        >>> result = await loader.load(Path("survey.xml"))
        >>> print(result)
        {'Instrument': 1, 'Sequence': 50, 'QuestionConstruct': 200, ...}
    """

    def __init__(
        self,
        driver: Driver | AsyncDriver,
        settings: Settings | None = None,
        *,
        metrics: MetricsEmitter | None = None,
    ):
        """Initialize the loader.

        Args:
            driver: Neo4j driver instance (sync or async).
            settings: Optional settings configuration.
            metrics: Optional metrics emitter.
        """
        self.driver = driver
        self.settings = settings or Settings()
        self.metrics = metrics or NullMetrics()

    async def load(
        self,
        path: Path | str,
        *,
        clear_first: bool | None = None,
    ) -> dict[str, int]:
        """Load a DDI-L FragmentInstance file into Neo4j.

        Args:
            path: Path to the XML file.
            clear_first: If True, clear existing fragment data first.
                Defaults to settings.replace value.

        Returns:
            Dictionary with counts of created elements by type.
        """
        validated_path = validate_readable_xml_path(path)
        should_clear = clear_first if clear_first is not None else self.settings.replace

        logger.info(
            "Loading DDI-L FragmentInstance",
            extra={"path": str(validated_path), "clear_first": should_clear},
        )

        start_time = perf_counter()

        # Initialize writer
        writer = AsyncFragmentGraphWriter(
            self.driver,
            settings=self.settings,
            metrics=self.metrics,
        )

        # Clear existing data if requested
        if should_clear and not self.settings.dry_run:
            logger.info("Clearing existing fragment data")
            await writer.purge_fragments(self.settings.neo4j_database)

        # Parse and write in streaming batches
        parser = DDIFragmentParser(
            validated_path,
            chunk_size=self.settings.chunk_size,
            metrics=self.metrics,
            recover=not self.settings.strict_parsing,
        )

        totals: dict[str, int] = defaultdict(int)
        batch_count = 0

        for batch in parser.parse_batches():
            batch_start = perf_counter()
            counts = await writer.write_batch(batch)

            for key, count in counts.items():
                if key != "dry_run":
                    totals[key] += count

            batch_count += 1
            batch_duration = perf_counter() - batch_start

            if self.settings.batch_metrics:
                self.metrics.observe("fragment.batch_duration_seconds", batch_duration)
                self.metrics.observe("fragment.batch_size", float(batch.total_fragments()))

            self.metrics.increment("fragment.batches")

        # Mark entry points: the file's declared top level (which may be a Group
        # or other container) plus every survey root (Instrument/StudyUnit), so all
        # roots are discoverable even when several files are loaded into one graph.
        if not self.settings.dry_run:
            if parser.top_level_ref:
                await writer.mark_entry_point(
                    parser.top_level_ref.node_key,
                    self.settings.neo4j_database,
                )
            await writer.mark_entry_points(self.settings.neo4j_database)

        elapsed = perf_counter() - start_time
        totals["batches"] = batch_count

        self.metrics.observe("fragment.load_duration_seconds", elapsed)

        logger.info(
            "DDI-L FragmentInstance load complete",
            extra={
                "path": str(validated_path),
                "totals": dict(totals),
                "elapsed_seconds": round(elapsed, 3),
            },
        )

        return dict(totals)


# ============================================================================
# Utility Functions
# ============================================================================


def detect_ddi_format(path: Path | str) -> str:
    """Detect whether a DDI file is Codebook, Lifecycle, or CDI format.

    Args:
        path: Path to the DDI XML file.

    Returns:
        One of ``"codebook"``, ``"lifecycle"``, or ``"cdi"`` based on the
        root element and namespace.
    """
    # Use iterparse to only read the root element
    with open(path, "rb") as f:
        for _event, elem in etree.iterparse(f, events=("start",)):
            root_tag = strip_namespace(elem.tag)
            tag_str = str(elem.tag)
            elem.clear()
            break
        else:
            return "codebook"

    # DDI-CDI uses <Wrapper> root or ddi-cdi namespace
    if root_tag == "Wrapper" or "ddi-cdi" in tag_str.lower():
        return "cdi"

    if root_tag == "FragmentInstance":
        return "lifecycle"
    elif root_tag in ("codeBook", "codebook", "DDIInstance"):
        return "codebook"
    else:
        # Check for Fragment children as indicator of lifecycle format
        with open(path, "rb") as f:
            depth = 0
            for event, elem in etree.iterparse(f, events=("start", "end")):
                if event == "start":
                    depth += 1
                    if depth == 2 and strip_namespace(elem.tag) == "Fragment":
                        return "lifecycle"
                else:
                    depth -= 1
                    if depth <= 0:
                        break
                elem.clear()
        return "codebook"


__all__ = [
    "AsyncFragmentGraphWriter",
    "DDIFragmentLoader",
    "DDIFragmentParser",
    "Fragment",
    "FragmentBatch",
    "FragmentReference",
    "detect_ddi_format",
]

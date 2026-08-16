"""Abstract DDI ingestion graph schema definitions.

The schema models nodes and relationships independently of any backend. A
`DDIIngestGraph` is created from a `DDIBatch` and can be handed to adapters that
translate the abstract representation into backend- specific write operations.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import hints only
    from ddigraph.ingest.loader import (
        AccessConditionRecord,
        AccessPolicyRecord,
        CategoryGroupRecord,
        CategoryRecord,
        CitationRecord,
        CodeListRecord,
        CodeSchemeRecord,
        CollectionInstrumentRecord,
        ComparisonRecord,
        ConceptRecord,
        ContributorRoleRecord,
        ControlConstructRecord,
        CoverageRecord,
        DataCollectionEventRecord,
        DataFileRecord,
        DatasetRecord,
        DDIBatch,
        DocumentDescriptionRecord,
        ExPostEvaluationRecord,
        FundingRecord,
        GenericIdentifiableRecord,
        GroupRecord,
        LogicalRecord,
        MethodologyNoteRecord,
        NCubeGroupRecord,
        NCubeRecord,
        OrganizationRecord,
        OtherMaterialRecord,
        PhysicalStructureRecord,
        ProcessingEventRecord,
        QualityStatementRecord,
        QuestionFlowRecord,
        QuestionGridRecord,
        QuestionItemRecord,
        QuestionRecord,
        RepresentationRecord,
        RepresentedVariableRecord,
        SampleFrameRecord,
        SamplingProcedureRecord,
        SeriesRecord,
        SoftwareRecord,
        StudyAuthorizationRecord,
        StudyDevelopmentRecord,
        StudyRecord,
        UniverseRecord,
        VarGroupRecord,
        VariableRecord,
        WeightRecord,
    )


@dataclass(slots=True)
class Node:
    """A graph node independent of any backend."""

    label: str
    identity: dict[str, object]
    properties: dict[str, object]


@dataclass(slots=True)
class Relationship:
    """A graph relationship independent of any backend."""

    type: str
    start: Node
    end: Node
    properties: dict[str, object] | None = None


@dataclass(slots=True)
class DDIIngestGraph:
    """A DDI ingestion payload expressed as nodes and relationships."""

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
    ncubes: list[NCubeRecord]
    ncube_groups: list[NCubeGroupRecord]
    document_descriptions: list[DocumentDescriptionRecord]
    sample_frames: list[SampleFrameRecord]
    quality_statements: list[QualityStatementRecord]
    study_authorizations: list[StudyAuthorizationRecord]
    study_developments: list[StudyDevelopmentRecord]
    ex_post_evaluations: list[ExPostEvaluationRecord]
    # Concrete DDI-Codebook identifiables captured through the generic
    # path (no bespoke record class).  Exposed in the graph as
    # ``DDIGenericIdentifiable`` nodes with the XSD tag preserved on
    # ``element_tag``.
    generic_identifiables: list[GenericIdentifiableRecord]

    @classmethod
    def from_ddi_batch(cls, batch: DDIBatch) -> DDIIngestGraph:
        """Build a graph payload from a parsed :class:`~ddigraph.ingest.loader.DDIBatch`.

        Args:
            batch: Parsed DDI batch containing one dataset record plus typed record
                collections. The method expects the canonical ``DDIBatch``
                contract where each collection attribute name matches the
                ``DDIIngestGraph`` dataclass field names.

        Returns:
            DDIIngestGraph: A graph container that preserves the dataset record and
            all record collections from ``batch`` without additional transformation.

        Raises:
            TypeError: If ``batch`` is not an instance of ``DDIBatch``.
        """
        from ddigraph.ingest.loader import DDIBatch  # local import to avoid circular dependency

        if not isinstance(batch, DDIBatch):  # pragma: no cover - defensive
            raise TypeError("Expected DDIBatch when building DDIIngestGraph")

        return cls(
            dataset=batch.dataset,
            studies=batch.studies,
            data_files=batch.data_files,
            code_schemes=batch.code_schemes,
            categories=batch.categories,
            universes=batch.universes,
            concepts=batch.concepts,
            variables=batch.variables,
            questions=batch.questions,
            question_items=batch.question_items,
            organizations=batch.organizations,
            series_list=batch.series_list,
            groups=batch.groups,
            data_collection_events=batch.data_collection_events,
            logical_records=batch.logical_records,
            physical_structures=batch.physical_structures,
            other_materials=batch.other_materials,
            var_groups=batch.var_groups,
            category_groups=batch.category_groups,
            question_grids=batch.question_grids,
            question_flows=batch.question_flows,
            sampling_procedures=batch.sampling_procedures,
            weights=batch.weights,
            representations=batch.representations,
            code_lists=batch.code_lists,
            methodology_notes=batch.methodology_notes,
            processing_events=batch.processing_events,
            software=batch.software,
            access_conditions=batch.access_conditions,
            citations=batch.citations,
            coverage=batch.coverage,
            funding=batch.funding,
            contributor_roles=batch.contributor_roles,
            instruments=batch.instruments,
            control_constructs=batch.control_constructs,
            represented_variables=batch.represented_variables,
            comparisons=batch.comparisons,
            access_policies=batch.access_policies,
            ncubes=batch.ncubes,
            ncube_groups=batch.ncube_groups,
            document_descriptions=batch.document_descriptions,
            sample_frames=batch.sample_frames,
            quality_statements=batch.quality_statements,
            study_authorizations=batch.study_authorizations,
            study_developments=batch.study_developments,
            ex_post_evaluations=batch.ex_post_evaluations,
            generic_identifiables=batch.generic_identifiables,
        )

    def nodes(self) -> Iterable[Node]:
        """Yield all graph nodes represented by this batch.

        Args:
            None.

        Returns:
            Iterable[Node]: A generator that yields:
                1. Exactly one ``Dataset`` node identified by ``{"id": dataset.id}``.
                2. One node per record in each mapped collection from
                   ``_NODE_MAPPINGS`` using the configured identity key
                   (for example ``study_id``, ``file_id``, or ``name``).
                3. One ``DDIGenericIdentifiable`` node per item in
                   ``generic_identifiables``.

            Node identity keys are expected to be stable and unique within a label
            scope so downstream adapters can safely upsert by ``Node.identity``.

        Raises:
            AttributeError: If a mapped record is missing an expected identity or
                property attribute declared in ``_NODE_MAPPINGS``.
            KeyError: If downstream consumers assume identity keys that are absent
                from yielded node identities.
        """
        dataset_node = Node(
            "Dataset",
            {"id": self.dataset.id},
            {
                "id": self.dataset.id,
                "name": self.dataset.name,
                "label": self.dataset.label,
                "urn": self.dataset.urn,
                "agency": self.dataset.agency,
                "version": self.dataset.version,
                "reusable_id": self.dataset.reusable_id,
                "reusable_version": self.dataset.reusable_version,
                "reusable_urn": self.dataset.reusable_urn,
                "reusable_agency": self.dataset.reusable_agency,
                "reusable_type_of_object": self.dataset.reusable_type_of_object,
            },
        )
        yield dataset_node
        for record, label, id_field, props in _NODE_MAPPINGS:
            for item in getattr(self, record):
                identity = {id_field: getattr(item, id_field)}
                properties = {field: getattr(item, field) for field in props}
                yield Node(label, identity, properties)
        yield from self._generic_identifiable_nodes()

    def _generic_identifiable_nodes(self) -> Iterable[Node]:
        """Yield nodes for generic DDI-Codebook identifiables.

        Args:
            None.

        Returns:
            Iterable[Node]: A generator yielding ``DDIGenericIdentifiable`` nodes.
            Each yielded node uses a composite identity containing
            ``dataset_id``, ``element_tag``, and ``identifiable_id`` to avoid
            collisions across heterogeneous XML element types within the same
            dataset.

        Raises:
            AttributeError: If a generic identifiable record is missing one of the
                required identity or property attributes.
            KeyError: If downstream code expects the composite identity keys but a
                malformed record omits one.
        """
        for item in self.generic_identifiables:
            identity: dict[str, object] = {
                "dataset_id": item.dataset_id,
                "element_tag": item.element_tag,
                "identifiable_id": item.identifiable_id,
            }
            properties: dict[str, object] = {
                "dataset_id": item.dataset_id,
                "dataset_name": item.dataset_name,
                "element_tag": item.element_tag,
                "identifiable_id": item.identifiable_id,
                "description": item.description,
                "urn": item.urn,
                "agency": item.agency,
                "version": item.version,
                "name": item.name,
                "label": item.label,
                "reusable_id": item.reusable_id,
                "reusable_version": item.reusable_version,
                "reusable_urn": item.reusable_urn,
                "reusable_agency": item.reusable_agency,
                "reusable_type_of_object": item.reusable_type_of_object,
            }
            yield Node("DDIGenericIdentifiable", identity, properties)

    def relationships(self) -> Iterable[Relationship]:
        """Yield all graph relationships represented by this batch.

        Args:
            None.

        Returns:
            Iterable[Relationship]: A generator yielding:
                1. Relationships built from ``DDI_RELATIONSHIPS`` definitions.
                2. ``IN_DATASET`` edges from every generic identifiable node to the
                   dataset node.

            Relationship endpoints are represented as lightweight ``Node`` stubs
            whose identities must match the identity-key conventions used by
            :meth:`nodes` (for example ``{"study_id": ...}`` or
            ``{"id": dataset.id}``).

        Raises:
            AttributeError: If relationship definitions reference missing graph
                collections or record attributes.
            KeyError: If downstream consumers require endpoint identity keys that
                are not present in yielded node stubs.
        """
        dataset_node = Node(
            "Dataset",
            {"id": self.dataset.id},
            {
                "id": self.dataset.id,
                "name": self.dataset.name,
                "label": self.dataset.label,
                "urn": self.dataset.urn,
                "agency": self.dataset.agency,
                "version": self.dataset.version,
                "reusable_id": self.dataset.reusable_id,
                "reusable_version": self.dataset.reusable_version,
                "reusable_urn": self.dataset.reusable_urn,
                "reusable_agency": self.dataset.reusable_agency,
                "reusable_type_of_object": self.dataset.reusable_type_of_object,
            },
        )
        for rel in DDI_RELATIONSHIPS:
            yield from rel.build(dataset_node, self)
        for generic_node in self._generic_identifiable_nodes():
            yield Relationship("IN_DATASET", generic_node, dataset_node)

    def as_dict(self) -> dict[str, object]:
        """Serialize the ingestion graph records to plain dictionaries.

        Args:
            None.

        Returns:
            dict[str, object]: A mapping with one key per dataclass field in
            ``DDIIngestGraph``. ``dataset`` is serialized as a single dictionary;
            all other fields are serialized as lists of dictionaries preserving the
            source record ordering.

        Raises:
            TypeError: If ``asdict``/``as_dicts`` encounters non-serializable
                record structures.
            AttributeError: If expected dataclass-like record attributes are
                missing when converting collections.
        """
        from ddigraph.utils.chunking import as_dicts as _as_dicts

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


@dataclass(slots=True)
class RelationshipDefinition:
    """Defines how to build relationships from a graph batch."""

    type: str
    start_label: str
    start_field: str
    end_label: str
    end_field: str
    start_attr: str
    end_attr: str
    start_lookup_field: str | None = None

    def build(self, dataset_node: Node, graph: DDIIngestGraph) -> Iterable[Relationship]:
        """Build relationships for a single relationship definition.

        Args:
            dataset_node: Canonical dataset node used as relationship target when
                ``end_label`` is ``"Dataset"``. Its identity is expected to use the
                dataset key ``{"id": <dataset_id>}``.
            graph: Graph payload that provides source and target record
                collections. ``start_attr`` and ``end_attr`` must resolve to
                iterable record collections on this object.

        Returns:
            Iterable[Relationship]: A generator that yields zero or more
            relationships. Records with ``None`` start or end lookup values are
            skipped. When ``start_lookup_field`` (or ``end_field`` fallback)
            contains a list, one relationship may be yielded per list element.

        Raises:
            AttributeError: If the configured collection names or record attributes
                (for example ``start_field``, ``end_field``, or lookup fields) do
                not exist.
            KeyError: If downstream logic expects a referenced end record identity
                to exist but no matching lookup entry is found.
        """
        start_collection = getattr(graph, self.start_attr)
        end_collection = getattr(graph, self.end_attr)
        end_lookup = {}
        if self.end_label != "Dataset":
            end_lookup = {getattr(item, self.end_field): item for item in end_collection}
        lookup_field = self.start_lookup_field or self.end_field

        for record in start_collection:
            start_value = getattr(record, self.start_field)
            if start_value is None:
                continue

            start_node = Node(
                self.start_label,
                {self.start_field: start_value},
                {self.start_field: start_value},
            )

            if self.end_label == "Dataset":
                yield Relationship(self.type, start_node, dataset_node)
                continue

            lookup_value = getattr(record, lookup_field)
            lookup_values = lookup_value if isinstance(lookup_value, list) else [lookup_value]
            for value in lookup_values:
                if value is None:
                    continue

                end_record = end_lookup.get(value)
                if end_record is None:
                    continue

                end_value = getattr(end_record, self.end_field)
                if end_value is None:
                    continue

                end_node = Node(
                    self.end_label,
                    {self.end_field: end_value},
                    {self.end_field: end_value},
                )
                yield Relationship(self.type, start_node, end_node)


_NODE_MAPPINGS = (
    (
        "studies",
        "Study",
        "study_id",
        (
            "dataset_id",
            "dataset_name",
            "study_id",
            "title",
            "abstract",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "rationale",
            "language",
            "external_references",
        ),
    ),
    (
        "data_files",
        "DataFile",
        "file_id",
        (
            "dataset_id",
            "dataset_name",
            "file_id",
            "name",
            "uri",
            "urn",
            "agency",
            "version",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "code_schemes",
        "CodeScheme",
        "code_scheme_id",
        (
            "dataset_id",
            "dataset_name",
            "code_scheme_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "description",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
        ),
    ),
    (
        "categories",
        "Category",
        "category_id",
        (
            "dataset_id",
            "dataset_name",
            "category_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "code",
            "code_scheme_id",
            "description",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "rationale",
            "language",
            "external_references",
        ),
    ),
    (
        "universes",
        "Universe",
        "universe_id",
        (
            "dataset_id",
            "dataset_name",
            "universe_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "description",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "rationale",
            "language",
            "external_references",
        ),
    ),
    (
        "concepts",
        "Concept",
        "name",
        (
            "dataset_id",
            "dataset_name",
            "name",
            "urn",
            "agency",
            "version",
            "label",
            "description",
            "rationale",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "variables",
        "Variable",
        "variable_id",
        (
            "dataset_id",
            "dataset_name",
            "variable_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "description",
            "rationale",
            "language",
            "concept",
            "file_id",
            "universe_id",
            "question_id",
            "question_text",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
            "category_ids",
        ),
    ),
    (
        "questions",
        "Question",
        "question_id",
        (
            "dataset_id",
            "dataset_name",
            "question_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "text",
            "description",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "rationale",
            "language",
            "external_references",
            "control_construct_references",
        ),
    ),
    (
        "question_items",
        "QuestionItem",
        "question_item_id",
        (
            "dataset_id",
            "dataset_name",
            "question_item_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "text",
            "description",
            "parent_question_id",
            "parent_grid_id",
            "parent_flow_id",
            "variable_id",
            "rationale",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
            "control_construct_references",
        ),
    ),
    (
        "organizations",
        "Organization",
        "organization_id",
        (
            "dataset_id",
            "dataset_name",
            "organization_id",
            "name",
            "abbreviation",
            "urn",
            "agency",
            "version",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "series_list",
        "Series",
        "series_id",
        (
            "dataset_id",
            "dataset_name",
            "series_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "description",
            "rationale",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
        ),
    ),
    (
        "groups",
        "Group",
        "group_id",
        (
            "dataset_id",
            "dataset_name",
            "group_id",
            "label",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "data_collection_events",
        "DataCollectionEvent",
        "event_id",
        (
            "dataset_id",
            "dataset_name",
            "event_id",
            "label",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "logical_records",
        "LogicalRecord",
        "logical_record_id",
        (
            "dataset_id",
            "dataset_name",
            "logical_record_id",
            "label",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "physical_structures",
        "PhysicalStructure",
        "physical_structure_id",
        (
            "dataset_id",
            "dataset_name",
            "physical_structure_id",
            "label",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "other_materials",
        "OtherMaterial",
        "material_id",
        (
            "dataset_id",
            "dataset_name",
            "material_id",
            "label",
            "uri",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "var_groups",
        "VarGroup",
        "var_group_id",
        (
            "dataset_id",
            "dataset_name",
            "var_group_id",
            "label",
            "description",
            "variable_ids",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "category_groups",
        "CategoryGroup",
        "category_group_id",
        (
            "dataset_id",
            "dataset_name",
            "category_group_id",
            "label",
            "description",
            "category_ids",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "question_grids",
        "QuestionGrid",
        "question_grid_id",
        (
            "dataset_id",
            "dataset_name",
            "question_grid_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "text",
            "description",
            "rationale",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
            "control_construct_references",
        ),
    ),
    (
        "question_flows",
        "QuestionFlow",
        "question_flow_id",
        (
            "dataset_id",
            "dataset_name",
            "question_flow_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "text",
            "description",
            "rationale",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
            "control_construct_references",
        ),
    ),
    (
        "sampling_procedures",
        "SamplingProcedure",
        "sampling_id",
        (
            "dataset_id",
            "dataset_name",
            "sampling_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "weights",
        "Weight",
        "weight_id",
        (
            "dataset_id",
            "dataset_name",
            "weight_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "representations",
        "Representation",
        "representation_id",
        (
            "dataset_id",
            "dataset_name",
            "representation_id",
            "label",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "code_lists",
        "CodeList",
        "code_list_id",
        (
            "dataset_id",
            "dataset_name",
            "code_list_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "description",
            "language",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
            "external_references",
        ),
    ),
    (
        "methodology_notes",
        "MethodologyNote",
        "note_id",
        (
            "dataset_id",
            "dataset_name",
            "note_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
        ),
    ),
    (
        "processing_events",
        "ProcessingEvent",
        "processing_event_id",
        (
            "dataset_id",
            "dataset_name",
            "processing_event_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "software",
        "Software",
        "software_id",
        (
            "dataset_id",
            "dataset_name",
            "software_id",
            "name",
            "version",
            "urn",
            "agency",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "access_conditions",
        "AccessCondition",
        "access_condition_id",
        (
            "dataset_id",
            "dataset_name",
            "access_condition_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "citations",
        "Citation",
        "citation_id",
        (
            "dataset_id",
            "dataset_name",
            "citation_id",
            "title",
            "bibliographic",
            "authors",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "coverage",
        "Coverage",
        "coverage_id",
        (
            "dataset_id",
            "dataset_name",
            "coverage_id",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "coverage_type",
            "description",
            "start_date",
            "end_date",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "funding",
        "Funding",
        "funding_id",
        (
            "dataset_id",
            "dataset_name",
            "funding_id",
            "agency",
            "grant_number",
            "urn",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "contributor_roles",
        "ContributorRole",
        "contributor_id",
        (
            "dataset_id",
            "dataset_name",
            "contributor_id",
            "name",
            "role",
            "urn",
            "agency",
            "version",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "instruments",
        "CollectionInstrument",
        "instrument_id",
        (
            "dataset_id",
            "dataset_name",
            "instrument_id",
            "label",
            "instrument_type",
            "element_type",
            "urn",
            "agency",
            "id",
            "version",
            "name",
            "description",
            "external_instrument_locations",
            "control_construct_reference",
            "referenced_construct_id",
            "fielded_languages",
            "development_results_references",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "control_constructs",
        "ControlConstruct",
        "construct_id",
        (
            "dataset_id",
            "dataset_name",
            "construct_id",
            "label",
            "construct_type",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "represented_variables",
        "RepresentedVariable",
        "represented_variable_id",
        (
            "dataset_id",
            "dataset_name",
            "represented_variable_id",
            "label",
            "concept",
            "urn",
            "agency",
            "version",
            "name",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "comparisons",
        "Comparison",
        "comparison_id",
        (
            "dataset_id",
            "dataset_name",
            "comparison_id",
            "description",
            "comparison_type",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "access_policies",
        "AccessPolicy",
        "access_policy_id",
        (
            "dataset_id",
            "dataset_name",
            "access_policy_id",
            "description",
            "policy_type",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    # DDI-C 2.6
    (
        "ncubes",
        "NCube",
        "ncube_id",
        (
            "dataset_id",
            "dataset_name",
            "ncube_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "ncube_groups",
        "NCubeGroup",
        "ncube_group_id",
        (
            "dataset_id",
            "dataset_name",
            "ncube_group_id",
            "description",
            "ncube_ids",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "document_descriptions",
        "DocumentDescription",
        "doc_id",
        (
            "dataset_id",
            "dataset_name",
            "doc_id",
            "title",
            "description",
            "producer",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "sample_frames",
        "SampleFrame",
        "sample_frame_id",
        (
            "dataset_id",
            "dataset_name",
            "sample_frame_id",
            "description",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "quality_statements",
        "QualityStatement",
        "quality_id",
        (
            "dataset_id",
            "dataset_name",
            "quality_id",
            "description",
            "standard",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "study_authorizations",
        "StudyAuthorization",
        "authorization_id",
        (
            "dataset_id",
            "dataset_name",
            "authorization_id",
            "description",
            "authorization_statement",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "study_developments",
        "StudyDevelopment",
        "development_id",
        (
            "dataset_id",
            "dataset_name",
            "development_id",
            "description",
            "activity_type",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
    (
        "ex_post_evaluations",
        "ExPostEvaluation",
        "evaluation_id",
        (
            "dataset_id",
            "dataset_name",
            "evaluation_id",
            "description",
            "completion_date",
            "urn",
            "agency",
            "version",
            "name",
            "label",
            "reusable_id",
            "reusable_version",
            "reusable_urn",
            "reusable_agency",
            "reusable_type_of_object",
        ),
    ),
)


DDI_RELATIONSHIPS: tuple[RelationshipDefinition, ...] = (
    RelationshipDefinition(
        "DESCRIBES",
        "Study",
        "study_id",
        "Dataset",
        "id",
        "studies",
        "studies",
    ),
    RelationshipDefinition(
        "ASSOCIATED_WITH",
        "Organization",
        "organization_id",
        "Dataset",
        "id",
        "organizations",
        "organizations",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Series",
        "series_id",
        "Dataset",
        "id",
        "series_list",
        "series_list",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Group",
        "group_id",
        "Dataset",
        "id",
        "groups",
        "groups",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "DataCollectionEvent",
        "event_id",
        "Dataset",
        "id",
        "data_collection_events",
        "data_collection_events",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "DataFile",
        "file_id",
        "Dataset",
        "id",
        "data_files",
        "data_files",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "CodeScheme",
        "code_scheme_id",
        "Dataset",
        "id",
        "code_schemes",
        "code_schemes",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Category",
        "category_id",
        "Dataset",
        "id",
        "categories",
        "categories",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Universe",
        "universe_id",
        "Dataset",
        "id",
        "universes",
        "universes",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Concept",
        "name",
        "Dataset",
        "id",
        "concepts",
        "concepts",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Question",
        "question_id",
        "Dataset",
        "id",
        "questions",
        "questions",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Variable",
        "variable_id",
        "Dataset",
        "id",
        "variables",
        "variables",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "QuestionItem",
        "question_item_id",
        "Dataset",
        "id",
        "question_items",
        "question_items",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "LogicalRecord",
        "logical_record_id",
        "Dataset",
        "id",
        "logical_records",
        "logical_records",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "PhysicalStructure",
        "physical_structure_id",
        "Dataset",
        "id",
        "physical_structures",
        "physical_structures",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "OtherMaterial",
        "material_id",
        "Dataset",
        "id",
        "other_materials",
        "other_materials",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "VarGroup",
        "var_group_id",
        "Dataset",
        "id",
        "var_groups",
        "var_groups",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "CategoryGroup",
        "category_group_id",
        "Dataset",
        "id",
        "category_groups",
        "category_groups",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "QuestionGrid",
        "question_grid_id",
        "Dataset",
        "id",
        "question_grids",
        "question_grids",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "QuestionFlow",
        "question_flow_id",
        "Dataset",
        "id",
        "question_flows",
        "question_flows",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "SamplingProcedure",
        "sampling_id",
        "Dataset",
        "id",
        "sampling_procedures",
        "sampling_procedures",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Weight",
        "weight_id",
        "Dataset",
        "id",
        "weights",
        "weights",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Representation",
        "representation_id",
        "Dataset",
        "id",
        "representations",
        "representations",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "CodeList",
        "code_list_id",
        "Dataset",
        "id",
        "code_lists",
        "code_lists",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "MethodologyNote",
        "note_id",
        "Dataset",
        "id",
        "methodology_notes",
        "methodology_notes",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "ProcessingEvent",
        "processing_event_id",
        "Dataset",
        "id",
        "processing_events",
        "processing_events",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "Software",
        "software_id",
        "Dataset",
        "id",
        "software",
        "software",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "AccessCondition",
        "access_condition_id",
        "Dataset",
        "id",
        "access_conditions",
        "access_conditions",
    ),
    RelationshipDefinition(
        "DESCRIBES",
        "Citation",
        "citation_id",
        "Dataset",
        "id",
        "citations",
        "citations",
    ),
    RelationshipDefinition(
        "COVERS",
        "Coverage",
        "coverage_id",
        "Dataset",
        "id",
        "coverage",
        "coverage",
    ),
    RelationshipDefinition(
        "FUNDS",
        "Funding",
        "funding_id",
        "Dataset",
        "id",
        "funding",
        "funding",
    ),
    RelationshipDefinition(
        "CONTRIBUTES_TO",
        "Contributor",
        "contributor_id",
        "Dataset",
        "id",
        "contributor_roles",
        "contributor_roles",
    ),
    RelationshipDefinition(
        "INSTRUMENT_FOR",
        "CollectionInstrument",
        "instrument_id",
        "Dataset",
        "id",
        "instruments",
        "instruments",
    ),
    RelationshipDefinition(
        "USES_CONSTRUCT",
        "ControlConstruct",
        "construct_id",
        "Dataset",
        "id",
        "control_constructs",
        "control_constructs",
    ),
    RelationshipDefinition(
        "REPRESENTS",
        "RepresentedVariable",
        "represented_variable_id",
        "Dataset",
        "id",
        "represented_variables",
        "represented_variables",
    ),
    RelationshipDefinition(
        "HAS_COMPARISON",
        "Comparison",
        "comparison_id",
        "Dataset",
        "id",
        "comparisons",
        "comparisons",
    ),
    RelationshipDefinition(
        "GOVERNED_BY",
        "AccessPolicy",
        "access_policy_id",
        "Dataset",
        "id",
        "access_policies",
        "access_policies",
    ),
    RelationshipDefinition(
        "IN_SCHEME",
        "Category",
        "category_id",
        "CodeScheme",
        "code_scheme_id",
        "categories",
        "code_schemes",
        start_lookup_field="code_scheme_id",
    ),
    RelationshipDefinition(
        "USES_CONCEPT",
        "Variable",
        "variable_id",
        "Concept",
        "name",
        "variables",
        "concepts",
        start_lookup_field="concept",
    ),
    RelationshipDefinition(
        "IN_FILE",
        "Variable",
        "variable_id",
        "DataFile",
        "file_id",
        "variables",
        "data_files",
        start_lookup_field="file_id",
    ),
    RelationshipDefinition(
        "IN_UNIVERSE",
        "Variable",
        "variable_id",
        "Universe",
        "universe_id",
        "variables",
        "universes",
        start_lookup_field="universe_id",
    ),
    RelationshipDefinition(
        "ASKED_AS",
        "Variable",
        "variable_id",
        "Question",
        "question_id",
        "variables",
        "questions",
        start_lookup_field="question_id",
    ),
    RelationshipDefinition(
        "USES_CATEGORY",
        "Variable",
        "variable_id",
        "Category",
        "category_id",
        "variables",
        "categories",
        start_lookup_field="category_ids",
    ),
    RelationshipDefinition(
        "USES_QUESTION_ITEM",
        "Variable",
        "variable_id",
        "QuestionItem",
        "question_item_id",
        "question_items",
        "question_items",
    ),
    RelationshipDefinition(
        "PART_OF",
        "QuestionItem",
        "question_item_id",
        "Question",
        "question_id",
        "question_items",
        "questions",
        start_lookup_field="parent_question_id",
    ),
    RelationshipDefinition(
        "IN_GRID",
        "QuestionItem",
        "question_item_id",
        "QuestionGrid",
        "question_grid_id",
        "question_items",
        "question_grids",
        start_lookup_field="parent_grid_id",
    ),
    RelationshipDefinition(
        "IN_FLOW",
        "QuestionItem",
        "question_item_id",
        "QuestionFlow",
        "question_flow_id",
        "question_items",
        "question_flows",
        start_lookup_field="parent_flow_id",
    ),
    RelationshipDefinition(
        "GROUPS",
        "VarGroup",
        "var_group_id",
        "Variable",
        "variable_id",
        "var_groups",
        "variables",
        start_lookup_field="variable_ids",
    ),
    RelationshipDefinition(
        "GROUPS",
        "CategoryGroup",
        "category_group_id",
        "Category",
        "category_id",
        "category_groups",
        "categories",
        start_lookup_field="category_ids",
    ),
    RelationshipDefinition(
        "USES_CONSTRUCT",
        "CollectionInstrument",
        "instrument_id",
        "ControlConstruct",
        "construct_id",
        "instruments",
        "control_constructs",
        start_lookup_field="referenced_construct_id",
    ),
    RelationshipDefinition(
        "USES_CONSTRUCT",
        "Question",
        "question_id",
        "ControlConstruct",
        "construct_id",
        "questions",
        "control_constructs",
        start_lookup_field="control_construct_references",
    ),
    RelationshipDefinition(
        "USES_CONSTRUCT",
        "QuestionItem",
        "question_item_id",
        "ControlConstruct",
        "construct_id",
        "question_items",
        "control_constructs",
        start_lookup_field="control_construct_references",
    ),
    RelationshipDefinition(
        "USES_CONSTRUCT",
        "QuestionGrid",
        "question_grid_id",
        "ControlConstruct",
        "construct_id",
        "question_grids",
        "control_constructs",
        start_lookup_field="control_construct_references",
    ),
    RelationshipDefinition(
        "USES_CONSTRUCT",
        "QuestionFlow",
        "question_flow_id",
        "ControlConstruct",
        "construct_id",
        "question_flows",
        "control_constructs",
        start_lookup_field="control_construct_references",
    ),
    RelationshipDefinition(
        "USES_CONCEPT",
        "RepresentedVariable",
        "represented_variable_id",
        "Concept",
        "name",
        "represented_variables",
        "concepts",
        start_lookup_field="concept",
    ),
    # DDI-C 2.6 relationships
    RelationshipDefinition(
        "IN_DATASET",
        "NCube",
        "ncube_id",
        "Dataset",
        "id",
        "ncubes",
        "ncubes",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "NCubeGroup",
        "ncube_group_id",
        "Dataset",
        "id",
        "ncube_groups",
        "ncube_groups",
    ),
    RelationshipDefinition(
        "GROUPS",
        "NCubeGroup",
        "ncube_group_id",
        "NCube",
        "ncube_id",
        "ncube_groups",
        "ncubes",
        start_lookup_field="ncube_ids",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "DocumentDescription",
        "doc_id",
        "Dataset",
        "id",
        "document_descriptions",
        "document_descriptions",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "SampleFrame",
        "sample_frame_id",
        "Dataset",
        "id",
        "sample_frames",
        "sample_frames",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "QualityStatement",
        "quality_id",
        "Dataset",
        "id",
        "quality_statements",
        "quality_statements",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "StudyAuthorization",
        "authorization_id",
        "Dataset",
        "id",
        "study_authorizations",
        "study_authorizations",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "StudyDevelopment",
        "development_id",
        "Dataset",
        "id",
        "study_developments",
        "study_developments",
    ),
    RelationshipDefinition(
        "IN_DATASET",
        "ExPostEvaluation",
        "evaluation_id",
        "Dataset",
        "id",
        "ex_post_evaluations",
        "ex_post_evaluations",
    ),
)


# Label -> (identity attribute, property attributes) on the *record*, as
# ``nodes()`` reads them. This is not the same as ``NodeDefinition``, which
# describes the Neo4j side: there ``id_field`` is the node property the
# Cypher merges on -- 44 of the 45 codebook mappings call it ``id`` -- while
# the record attribute is ``study_id``, ``file_id`` and so on. Anything
# consuming the graph view (RDF export, SHACL, the RDF reader) needs the
# record-side names, so the derivation lives here beside the table it comes
# from rather than being repeated per consumer.
NODE_RECORD_FIELDS: dict[str, tuple[str, tuple[str, ...]]] = {
    label: (id_field, properties) for _attr, label, id_field, properties in _NODE_MAPPINGS
} | {
    # ``Dataset`` is built directly by ``nodes()`` rather than through
    # ``_NODE_MAPPINGS``; its record attribute genuinely is ``id``.
    "Dataset": ("id", ("id", "name", "label", "urn", "agency", "version")),
}


__all__ = [
    "DDI_RELATIONSHIPS",
    "NODE_RECORD_FIELDS",
    "DDIIngestGraph",
    "Node",
    "Relationship",
    "RelationshipDefinition",
]

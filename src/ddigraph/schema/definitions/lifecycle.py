"""Auto-extracted from the former ``definitions.py`` monolith.

Holds one flavor's literal ``NodeDefinition`` / ``RelationshipDefinition``
data. A follow-up commit will route this data through
``ddigraph.schema._generated`` plus the override file in
``ddigraph.schema._overrides``; for now the literals are the source of
truth and live here unchanged.
"""

from __future__ import annotations

from ddigraph.schema._overrides._loader import fragment_relationships
from ddigraph.schema.definitions._dataclasses import NodeDefinition

FRAGMENT_NODES: tuple[NodeDefinition, ...] = (
    NodeDefinition(
        label="Instrument",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        indexes=("name", "label"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Sequence",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "construct_count",
        ),
        indexes=("name", "label"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="IfThenElse",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "condition",
        ),
        indexes=("condition",),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Loop",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QuestionConstruct",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        indexes=("name",),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QuestionItem",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "question_text",
            "response_type",
        ),
        indexes=("name", "question_text"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QuestionGrid",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "response_type",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CodeList",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "code_count",
        ),
        indexes=("name", "label"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Category",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "category_label",
        ),
        indexes=("name", "category_label"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="StatementItem",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ComputationItem",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RepeatWhile",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RepeatUntil",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Universe",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Concept",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Variable",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="StudyUnit",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DataCollection",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="MeasurementConstruct",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="MeasurementItem",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "measurement_text",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ResourcePackage",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "title",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PhysicalInstance",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DataRelationship",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LogicalRecord",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ConceptualVariable",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RepresentedVariable",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RepresentedVariableGroup",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CategoryScheme",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CategoryGroup",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Methodology",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="OtherMaterial",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "url",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RepresentedVariableScheme",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DataCollectionMethodology",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "description",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SamplingProcedure",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "description",
        ),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Scheme types (datacollection.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="QuestionScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ControlConstructScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="InstrumentScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="InterviewerInstructionScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ProcessingEventScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ProcessingInstructionScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DevelopmentActivityScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="MeasurementScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SamplingInformationScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Scheme types (logicalproduct.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="CodeListScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="NCubeScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="VariableScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Scheme types (conceptualcomponent.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="ConceptScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="UniverseScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ConceptualVariableScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeographicStructureScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeographicLocationScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="UnitTypeScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Control construct subtypes (datacollection.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="Split",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SplitJoin",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DevelopmentStep",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SamplingStage",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SampleStep",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Development activities (datacollection.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="DevelopmentActivity",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "description",
            "activity_type",
        ),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Archive types (archive.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="Organization",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Individual",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "name",
            "given_name",
            "family_name",
        ),
        indexes=("name",),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Access",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "description"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Collection",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Module-level maintainables (DDI-L top-level wrappers)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="ConceptualComponent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LogicalProduct",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PhysicalDataProduct",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Archive",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DDIProfile",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LocalHoldingPackage",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Group",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Classification types (logicalproduct.xsd / comparative.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="ClassificationFamily",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="StatisticalClassification",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "description",
        ),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ClassificationItem",
        id_field="fragment_id",
        properties=(
            "fragment_id",
            "agency",
            "version",
            "urn",
            "label",
            "name",
            "code",
        ),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Geographic types (conceptualcomponent.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="GeographicStructure",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeographicLocation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Group types (conceptualcomponent.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="ConceptGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="UniverseGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ConceptualVariableGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Unit type group (conceptualcomponent.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="UnitType",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="UnitTypeGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Variable group (logicalproduct.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="VariableGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="NCube",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="NCubeGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Physical data (physicaldataproduct.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="PhysicalStructure",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RecordLayout",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Complex question type (datacollection.xsd)
    # ---------------------------------------------------------------
    NodeDefinition(
        label="QuestionBlock",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    # ---------------------------------------------------------------
    # Auto-extended concrete identifiables (real XSD coverage).
    # These cover every concrete Maintainable / Versionable /
    # Identifiable element declared in DDI-L 3.x that is not already
    # registered above.  All use the uniform fragment identity + name
    # schema; type-specific properties can be added incrementally.
    # ---------------------------------------------------------------
    NodeDefinition(
        label="ActionToMinimizeLosses",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="AggregationVariables",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ApprovalReview",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ApprovalReviewDocument",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Attribute",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="AuthorizedSource",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CategoryMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ClassificationCorrespondenceTable",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ClassificationIndex",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ClassificationLevel",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ClassificationSeries",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Code",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CodeListGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CognitiveExpertReviewActivity",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CognitiveInterviewActivity",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CollectionEvent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CollectionSituation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Comparison",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ConceptMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ContentReviewActivity",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ControlConstructGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="CoordinateRegion",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DDIInstance",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DataCaptureDevelopment",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DataSet",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DefaultAccess",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DevelopmentActivityGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DevelopmentImplementation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DevelopmentPlan",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DevelopmentResults",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="DeviationFromSampleDesign",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Embargo",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="FocusGroupActivity",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="FundingDocument",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeneralInstruction",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GenerationInstruction",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeographicLevel",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeographicLocationGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GeographicStructureGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GrossFileStructure",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="GrossRecordStructure",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="InParameter",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="InformationClassification",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Instruction",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="InstructionGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="InstrumentGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ItemMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LifecycleEvent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LocalGroupContent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LocalResourcePackageContent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LocalStudyUnitContent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="LocationValue",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedDateTimeRepresentation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedItemMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedMissingValuesRepresentation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedNumericRepresentation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedRepresentationGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedRepresentationScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedScaleRepresentation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ManagedTextRepresentation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="MeasureDefinition",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="MeasurementGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ModeOfCollection",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="NCubeInstance",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="OrganizationGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="OrganizationScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="OtherMaterialGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="OtherMaterialScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="OutParameter",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PhysicalInstanceGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PhysicalRecordSegment",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PhysicalStructureGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PhysicalStructureScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="PretestActivity",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ProcessingEvent",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ProcessingEventGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="ProcessingInstructionGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QualityScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QualityStandard",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QualityStandardGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QualityStatement",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QualityStatementGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QuestionGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="QuestionMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RecordLayoutGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RecordLayoutScheme",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RecordRelationship",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Relation",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="RepresentationMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Sample",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SampleFrame",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SampleFrameAccess",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SamplingInformationGroup",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SamplingPlan",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SpatialCoverage",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="StandardWeight",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="SubUniverseClass",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="TemporalCoverage",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="TimeMethod",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="TopicalCoverage",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="TranslationActivity",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="UniverseMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="VariableMap",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="VariableStatistics",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="Weighting",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
    NodeDefinition(
        label="WeightingMethodology",
        id_field="fragment_id",
        properties=("fragment_id", "agency", "version", "urn", "label", "name"),
        is_fragment=True,
    ),
)

# =========================================================================
# DDI-L Fragment Relationship Types
# =========================================================================

# Derived from FRAGMENT_GENERATED_REFERENCES (282 *Reference elements in the
# DDI-L XSDs) via schema/_overrides/_loader.py. Curated rel_type names live
# in [ddi_l.relationship_overrides]; every other reference falls back to
# ``tag.removesuffix("Reference").upper()``.
FRAGMENT_RELATIONSHIP_TYPES: dict[str, str] = fragment_relationships()


__all__ = ["FRAGMENT_NODES", "FRAGMENT_RELATIONSHIP_TYPES"]

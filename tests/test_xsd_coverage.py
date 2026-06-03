"""Tests that verify XSD schema coverage in the ddigraph package.

These tests ensure:
1. All new scheme types are registered as FRAGMENT_NODES in DDISchema.
2. Every FRAGMENT_NODES label has a corresponding NAME_TAGS entry in DDIFragmentLoader.
3. All new control construct subtypes are registered.
4. All new CDI node types are registered in CDI_NODES.
5. New CDI relationships are present in _CDI_RELATIONSHIP_MAP.
6. CDIBatch holds collections for all new CDI record types.
7. Real XSD-driven coverage holds at 100% for DDI-L, DDI-Codebook, and DDI-CDI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ddigraph.ingest.cdi_loader import (  # noqa: E402
    _CDI_RELATIONSHIP_MAP,
    _CDI_TAG_MAP,
    CDIBatch,
)
from ddigraph.ingest.fragment_loader import DDIFragmentParser  # noqa: E402
from ddigraph.schema.definitions import DDISchema  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FRAGMENT_LABELS = {n.label for n in DDISchema.FRAGMENT_NODES}
_CDI_LABELS = {n.label for n in DDISchema.CDI_NODES}
_CODEBOOK_LABELS = {n.label for n in DDISchema.CODEBOOK_NODES}


# ---------------------------------------------------------------------------
# Fragment node coverage
# ---------------------------------------------------------------------------


class TestFragmentNodeSchemes:
    """All DDI-L scheme types must be registered as FRAGMENT_NODES."""

    _DATACOLLECTION_SCHEMES: ClassVar[list[str]] = [
        "QuestionScheme",
        "ControlConstructScheme",
        "InstrumentScheme",
        "InterviewerInstructionScheme",
        "ProcessingEventScheme",
        "ProcessingInstructionScheme",
        "DevelopmentActivityScheme",
        "MeasurementScheme",
        "SamplingInformationScheme",
    ]
    _LOGICALPRODUCT_SCHEMES: ClassVar[list[str]] = [
        "CodeListScheme",
        "NCubeScheme",
        "VariableScheme",
    ]
    _CONCEPTUALCOMPONENT_SCHEMES: ClassVar[list[str]] = [
        "ConceptScheme",
        "UniverseScheme",
        "ConceptualVariableScheme",
        "GeographicStructureScheme",
        "GeographicLocationScheme",
        "UnitTypeScheme",
    ]

    @pytest.mark.parametrize("label", _DATACOLLECTION_SCHEMES)
    def test_datacollection_scheme_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"

    @pytest.mark.parametrize("label", _LOGICALPRODUCT_SCHEMES)
    def test_logicalproduct_scheme_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"

    @pytest.mark.parametrize("label", _CONCEPTUALCOMPONENT_SCHEMES)
    def test_conceptualcomponent_scheme_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"


class TestFragmentNodeControlConstructs:
    """All DDI-L control construct subtypes must be registered as FRAGMENT_NODES."""

    _CONSTRUCTS: ClassVar[list[str]] = [
        "Split",
        "SplitJoin",
        "DevelopmentStep",
        "SamplingStage",
        "SampleStep",
    ]

    @pytest.mark.parametrize("label", _CONSTRUCTS)
    def test_control_construct_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"


class TestFragmentNodeArchiveTypes:
    """Archive and development types must be registered as FRAGMENT_NODES."""

    _TYPES: ClassVar[list[str]] = ["DevelopmentActivity", "Individual", "Access", "Collection"]

    @pytest.mark.parametrize("label", _TYPES)
    def test_archive_type_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"


class TestFragmentNodeModuleMaintainables:
    """DDI-L module-level maintainables must be in FRAGMENT_NODES."""

    _MAINTAINABLES: ClassVar[list[str]] = [
        "ConceptualComponent",
        "LogicalProduct",
        "PhysicalDataProduct",
        "Archive",
        "DDIProfile",
        "ClassificationFamily",
        "StatisticalClassification",
        "ClassificationItem",
        "GeographicStructure",
        "GeographicLocation",
        "ConceptGroup",
        "UniverseGroup",
        "ConceptualVariableGroup",
        "UnitType",
        "UnitTypeGroup",
        "VariableGroup",
        "RecordLayout",
        "QuestionBlock",
    ]

    @pytest.mark.parametrize("label", _MAINTAINABLES)
    def test_maintainable_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"


class TestPreviouslyMissingFragmentNodes:
    """Fragment nodes that were in definitions.py but absent from NAME_TAGS."""

    _LABELS: ClassVar[list[str]] = [
        "SamplingProcedure",
        "DataCollectionMethodology",
        "RepresentedVariableScheme",
    ]

    @pytest.mark.parametrize("label", _LABELS)
    def test_label_in_fragment_nodes(self, label: str) -> None:
        assert label in _FRAGMENT_LABELS, f"{label} missing from FRAGMENT_NODES"


# ---------------------------------------------------------------------------
# NAME_TAGS completeness
# ---------------------------------------------------------------------------


class TestNameTagsCompleteness:
    """Every FRAGMENT_NODES label must have a NAME_TAGS entry in DDIFragmentLoader."""

    def test_all_fragment_node_labels_have_name_tags(self) -> None:
        name_tags_keys = set(DDIFragmentParser.NAME_TAGS.keys())
        missing = _FRAGMENT_LABELS - name_tags_keys
        assert not missing, f"Fragment node labels missing NAME_TAGS entries: {sorted(missing)}"

    def test_fragment_node_labels_unique(self) -> None:
        labels = [n.label for n in DDISchema.FRAGMENT_NODES]
        assert len(labels) == len(set(labels)), "Duplicate labels in FRAGMENT_NODES"


# ---------------------------------------------------------------------------
# Fragment relationship types
# ---------------------------------------------------------------------------


class TestFragmentRelationshipTypes:
    """New scheme-containment and other references must be in FRAGMENT_RELATIONSHIP_TYPES."""

    _NEW_REF_TYPES: ClassVar[list[str]] = [
        "QuestionSchemeReference",
        "ControlConstructSchemeReference",
        "InstrumentSchemeReference",
        "InterviewerInstructionSchemeReference",
        "ProcessingEventSchemeReference",
        "ProcessingInstructionSchemeReference",
        "DevelopmentActivitySchemeReference",
        "MeasurementSchemeReference",
        "SamplingInformationSchemeReference",
        "ClassificationFamilyReference",
        "OrganizationReference",
        "IndividualReference",
        "DevelopmentActivityReference",
        "ConceptSchemeReference",
        "UniverseSchemeReference",
        "ConceptualVariableSchemeReference",
        "GeographicStructureSchemeReference",
        "GeographicLocationSchemeReference",
        "UnitTypeSchemeReference",
    ]

    @pytest.mark.parametrize("ref_type", _NEW_REF_TYPES)
    def test_relationship_type_registered(self, ref_type: str) -> None:
        assert ref_type in DDISchema.FRAGMENT_RELATIONSHIP_TYPES, (
            f"{ref_type} missing from FRAGMENT_RELATIONSHIP_TYPES"
        )


# ---------------------------------------------------------------------------
# CDI node coverage
# ---------------------------------------------------------------------------


class TestCDINodeDefinitions:
    """New CDI node types must be in DDISchema.CDI_NODES."""

    _NEW_CDI_NODES: ClassVar[list[str]] = [
        "CDIVariableRelationship",
        "CDIConceptMap",
        "CDIConceptSystemCorrespondence",
        "CDIPhysicalRecordSegment",
        "CDIClassificationFamily",
        "CDIClassificationIndex",
        "CDIClassificationSeries",
    ]

    @pytest.mark.parametrize("label", _NEW_CDI_NODES)
    def test_cdi_node_in_definitions(self, label: str) -> None:
        assert label in _CDI_LABELS, f"{label} missing from CDI_NODES"

    def test_cdi_node_labels_unique(self) -> None:
        labels = [n.label for n in DDISchema.CDI_NODES]
        assert len(labels) == len(set(labels)), "Duplicate labels in CDI_NODES"


class TestCDITagMap:
    """New CDI entity tag names must be in _CDI_TAG_MAP."""

    _NEW_TAGS: ClassVar[list[str]] = [
        "VariableRelationship",
        "ConceptMap",
        "ConceptSystemCorrespondence",
        "PhysicalRecordSegment",
        "ClassificationFamily",
        "ClassificationIndex",
        "ClassificationSeries",
    ]

    @pytest.mark.parametrize("tag", _NEW_TAGS)
    def test_tag_in_cdi_tag_map(self, tag: str) -> None:
        assert tag in _CDI_TAG_MAP, f"CDI tag '{tag}' missing from _CDI_TAG_MAP"


# ---------------------------------------------------------------------------
# CDI relationship coverage
# ---------------------------------------------------------------------------


class TestCDIRelationshipMap:
    """New CDI relationship patterns must be in _CDI_RELATIONSHIP_MAP."""

    _NEW_RELS: ClassVar[list[str]] = [
        "DataStructureComponent_isDefinedBy_RepresentedVariable",
        "Activity_hasSubActivity_Activity",
        "PhysicalDataSet_formats_DataStore",
        "PhysicalDataSet_has_PhysicalRecordSegment",
        "PhysicalRecordSegment_mapsTo_LogicalRecord",
        "VariableRelationship_hasSource_ConceptualVariable",
        "VariableRelationship_hasTarget_ConceptualVariable",
        "ConceptMap_hasSource_Concept",
        "ConceptMap_hasTarget_Concept",
        "ConceptSystemCorrespondence_has_ConceptMap",
        "ConceptSystemCorrespondence_maps_ConceptSystem",
        "ClassificationFamily_groups_ClassificationSeries",
        "ClassificationFamily_uses_ClassificationIndex",
        "ClassificationSeries_has_StatisticalClassification",
    ]

    @pytest.mark.parametrize("rel_key", _NEW_RELS)
    def test_relationship_in_map(self, rel_key: str) -> None:
        assert rel_key in _CDI_RELATIONSHIP_MAP, (
            f"CDI relationship '{rel_key}' missing from _CDI_RELATIONSHIP_MAP"
        )


# ---------------------------------------------------------------------------
# CDIBatch collections
# ---------------------------------------------------------------------------


class TestCDIBatchCollections:
    """CDIBatch must expose collections for all new CDI record types."""

    def test_variable_relationships_field_exists(self) -> None:
        batch = CDIBatch()
        assert hasattr(batch, "variable_relationships")
        assert isinstance(batch.variable_relationships, list)

    def test_concept_maps_field_exists(self) -> None:
        batch = CDIBatch()
        assert hasattr(batch, "concept_maps")
        assert isinstance(batch.concept_maps, list)

    def test_concept_system_correspondences_field_exists(self) -> None:
        batch = CDIBatch()
        assert hasattr(batch, "concept_system_correspondences")
        assert isinstance(batch.concept_system_correspondences, list)

    def test_physical_record_segments_field_exists(self) -> None:
        batch = CDIBatch()
        assert hasattr(batch, "physical_record_segments")
        assert isinstance(batch.physical_record_segments, list)

    def test_as_dict_includes_new_collections(self) -> None:
        batch = CDIBatch()
        d = batch.as_dict()
        for key in (
            "variable_relationships",
            "concept_maps",
            "concept_system_correspondences",
            "physical_record_segments",
        ):
            assert key in d, f"CDIBatch.as_dict() missing key '{key}'"

    def test_total_records_counts_new_collections(self) -> None:
        from ddigraph.ingest.cdi_loader import CDIRecord

        batch = CDIBatch()
        # Baseline
        base = batch.total_records()
        batch.variable_relationships.append(
            CDIRecord(cdi_id="vr-1", name="VR1", entity_type="VariableRelationship")
        )
        batch.concept_maps.append(CDIRecord(cdi_id="cm-1", name="CM1", entity_type="ConceptMap"))
        assert batch.total_records() == base + 2


# ---------------------------------------------------------------------------
# Bootstrap constraint generation
# ---------------------------------------------------------------------------


class TestBootstrapCoversNewNodes:
    """generate_constraint_queries must produce constraints for new node types."""

    def test_new_fragment_schemes_have_constraints(self) -> None:
        queries = DDISchema.generate_constraint_queries(include_fragments=True, include_cdi=False)
        queries_str = "\n".join(queries)
        for label in ("QuestionScheme", "CodeListScheme", "ConceptScheme", "Split"):
            assert label in queries_str, (
                f"No constraint query generated for fragment node '{label}'"
            )

    def test_new_cdi_nodes_have_constraints(self) -> None:
        queries = DDISchema.generate_constraint_queries(include_fragments=False, include_cdi=True)
        queries_str = "\n".join(queries)
        for label in (
            "CDIVariableRelationship",
            "CDIConceptMap",
            "CDIConceptSystemCorrespondence",
            "CDIPhysicalRecordSegment",
        ):
            assert label in queries_str, f"No constraint query generated for CDI node '{label}'"


# ---------------------------------------------------------------------------
# Real XSD-driven coverage (parses the bundled schemas directly)
# ---------------------------------------------------------------------------


class TestRealXSDCoverage:
    """Every concrete identifiable / entity in the shipped XSDs must be covered.

    These tests parse the actual schemas under ``/schemas`` and assert that the
    package registers a handler for every concrete, non-abstract element that
    can be encountered in a real DDI payload.
    """

    def test_ddi_l_fragment_nodes_cover_all_concrete_identifiables(self) -> None:
        import xsd_coverage as xc

        scope = xc._ddi_l_identifiables(xc.SCHEMAS_DIR / "ddi" / "v3_3")
        target = scope["maintainables"] | scope["versionables"] | scope["identifiables"]
        covered = {n.label for n in DDISchema.FRAGMENT_NODES}
        missing = sorted(target - covered)
        assert not missing, (
            f"DDI-L 3.3 concrete identifiables missing FRAGMENT_NODES entries: {missing}"
        )

    def test_ddi_c_codebook_elements_have_handlers(self) -> None:
        import xsd_coverage as xc

        target = (
            xc._ddi_c_identifiable_elements(xc.SCHEMAS_DIR / "ddi-c") - xc.DDI_C_LAYOUT_EXCLUDES
        )
        target_lower = {t.lower() for t in target}
        covered = xc._load_package_coverage()["codebook_tag_keys"]
        missing = sorted(target_lower - covered)
        assert not missing, f"DDI-Codebook elements with GLOBALS/ID missing handlers: {missing}"

    def test_ddi_cdi_concrete_entities_have_tag_map_entries(self) -> None:
        import xsd_coverage as xc

        entities, _, _ = xc._ddi_cdi_extract(xc.SCHEMAS_DIR / "ddi-cdi" / "xml-schema")
        covered = set(_CDI_TAG_MAP.keys())
        missing = sorted(entities - covered)
        assert not missing, f"DDI-CDI concrete entities missing _CDI_TAG_MAP entries: {missing}"

    def test_audit_script_exits_clean_at_threshold(self) -> None:
        """The packaged audit helper must exit 0 (clean) at the 100% threshold."""

        import xsd_coverage as xc

        rc = xc.run_audit(json_output=True, threshold=100.0)
        assert rc == 0, "scripts/xsd_coverage.py reports coverage below 100%"

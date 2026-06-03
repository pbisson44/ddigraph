"""Tests for DDI-C 2.6 and DDI-CDI 1.0 schema support."""

from pathlib import Path

import pytest

from ddigraph.ingest.cdi_loader import (
    is_cdi_format,
    parse_cdi_batches,
)
from ddigraph.ingest.fragment_loader import detect_ddi_format
from ddigraph.ingest.loader import (
    parse_ddi_batches,
)
from ddigraph.schema.ddi_graph import DDIIngestGraph
from ddigraph.schema.definitions import DDISchema

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_ddi_c26(tmp_path: Path) -> Path:
    """DDI Codebook XML with DDI-C 2.6 elements."""
    xml = tmp_path / "codebook_c26.xml"
    xml.write_text(
        """
        <codeBook>
            <stdyDscr ID="s1">
                <citation><titlStmt><titl>Study</titl></titlStmt></citation>
            </stdyDscr>
            <nCube ID="nc1">
                <labl>Income by Age</labl>
                <txt>A data cube of income by age</txt>
            </nCube>
            <nCubeGrp ID="ncg1">
                <labl>Demographic Cubes</labl>
                <txt>Group of demographic cubes</txt>
                <nCubeRef>nc1</nCubeRef>
            </nCubeGrp>
            <docDscr ID="doc1">
                <citation><titlStmt><titl>Codebook Document</titl></titlStmt></citation>
                <prodStmt><producer>Statistics Canada</producer></prodStmt>
            </docDscr>
            <sampleFrame ID="sf1">
                <labl>Population Frame 2020</labl>
                <txt>Frame description</txt>
            </sampleFrame>
            <qualityStatement ID="qs1">
                <labl>ISO Quality</labl>
                <txt>Quality description</txt>
                <standard>ISO 8000</standard>
            </qualityStatement>
            <studyAuthorization ID="sa1">
                <labl>Ethics Board</labl>
                <txt>Authorization description</txt>
                <authorizationStatement>Approved</authorizationStatement>
            </studyAuthorization>
            <studyDevelopment ID="sd1">
                <labl>Pilot Phase</labl>
                <txt>Development description</txt>
                <developmentActivity>pilot_testing</developmentActivity>
            </studyDevelopment>
            <exPostEvaluation ID="epe1">
                <labl>Post-collection Review</labl>
                <txt>Evaluation description</txt>
                <completionDate>2024-01-01</completionDate>
            </exPostEvaluation>
        </codeBook>
        """,
        encoding="utf-8",
    )
    return xml


@pytest.fixture
def sample_cdi_xml(tmp_path: Path) -> Path:
    """DDI-CDI 1.0 XML with Wrapper root and core entity types."""
    xml = tmp_path / "cdi.xml"
    xml.write_text(
        """
        <Wrapper xmlns="http://ddi-cdi/1.0">
            <Concept>
                <Identifier><StringValue>concept-001</StringValue></Identifier>
                <ObjectName>Employment Status</ObjectName>
                <LabelForDisplay>Employment Status</LabelForDisplay>
                <Description>Current employment status</Description>
            </Concept>
            <Organization>
                <Identifier><StringValue>org-001</StringValue></Identifier>
                <ObjectName>Statistics Canada</ObjectName>
                <LabelForDisplay>StatCan</LabelForDisplay>
            </Organization>
            <Individual>
                <Identifier><StringValue>ind-001</StringValue></Identifier>
                <ObjectName>John Doe</ObjectName>
            </Individual>
            <Category>
                <Identifier><StringValue>cat-001</StringValue></Identifier>
                <ObjectName>Employed</ObjectName>
                <LabelForDisplay>Employed</LabelForDisplay>
            </Category>
            <CodeList>
                <Identifier><StringValue>cl-001</StringValue></Identifier>
                <ObjectName>Employment Codes</ObjectName>
                <CodeList_has_Code>
                    <Identifier><StringValue>code-001</StringValue></Identifier>
                </CodeList_has_Code>
            </CodeList>
            <Code>
                <Identifier><StringValue>code-001</StringValue></Identifier>
                <ObjectName>EMP01</ObjectName>
                <Notation>1</Notation>
                <Code_denotes_Category>
                    <Identifier><StringValue>cat-001</StringValue></Identifier>
                </Code_denotes_Category>
            </Code>
            <StatisticalClassification>
                <Identifier><StringValue>sc-001</StringValue></Identifier>
                <ObjectName>ISCO-08</ObjectName>
                <LabelForDisplay>International Standard Classification</LabelForDisplay>
                <Version>2008</Version>
            </StatisticalClassification>
            <InstanceVariable>
                <Identifier><StringValue>iv-001</StringValue></Identifier>
                <ObjectName>emp_status</ObjectName>
                <LabelForDisplay>Employment Status</LabelForDisplay>
            </InstanceVariable>
            <WideDataStructure>
                <Identifier><StringValue>ds-001</StringValue></Identifier>
                <ObjectName>Survey Structure</ObjectName>
            </WideDataStructure>
            <WideDataSet>
                <Identifier><StringValue>dset-001</StringValue></Identifier>
                <ObjectName>Labour Force Survey 2024</ObjectName>
                <DataSet_isStructuredBy_DataStructure>
                    <Identifier><StringValue>ds-001</StringValue></Identifier>
                </DataSet_isStructuredBy_DataStructure>
            </WideDataSet>
        </Wrapper>
        """,
        encoding="utf-8",
    )
    return xml


# ============================================================================
# DDI-C 2.6 Parsing Tests
# ============================================================================


class TestDDIC26Parsing:
    """Tests for DDI-C 2.6 element parsing."""

    def test_ncube_parsing(self, sample_ddi_c26: Path) -> None:
        """NCube elements are parsed from DDI-C 2.6 XML."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        assert len(batches) == 1
        batch = batches[0]
        assert len(batch.ncubes) == 1
        assert batch.ncubes[0].ncube_id == "nc1"
        assert batch.ncubes[0].label == "Income by Age"

    def test_ncube_group_parsing(self, sample_ddi_c26: Path) -> None:
        """NCubeGroup elements are parsed with nCubeRef references."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.ncube_groups) == 1
        assert batch.ncube_groups[0].ncube_group_id == "ncg1"
        assert "nc1" in batch.ncube_groups[0].ncube_ids

    def test_document_description_parsing(self, sample_ddi_c26: Path) -> None:
        """DocumentDescription elements are parsed from DDI-C 2.6 XML."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.document_descriptions) == 1
        assert batch.document_descriptions[0].doc_id == "doc1"
        assert batch.document_descriptions[0].title == "Codebook Document"

    def test_sample_frame_parsing(self, sample_ddi_c26: Path) -> None:
        """SampleFrame elements are parsed."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.sample_frames) == 1
        assert batch.sample_frames[0].sample_frame_id == "sf1"

    def test_quality_statement_parsing(self, sample_ddi_c26: Path) -> None:
        """QualityStatement elements are parsed with standard field."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.quality_statements) == 1
        assert batch.quality_statements[0].quality_id == "qs1"
        assert batch.quality_statements[0].standard == "ISO 8000"

    def test_study_authorization_parsing(self, sample_ddi_c26: Path) -> None:
        """StudyAuthorization elements are parsed."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.study_authorizations) == 1
        assert batch.study_authorizations[0].authorization_id == "sa1"
        assert batch.study_authorizations[0].authorization_statement == "Approved"

    def test_study_development_parsing(self, sample_ddi_c26: Path) -> None:
        """StudyDevelopment elements are parsed with activity type."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.study_developments) == 1
        assert batch.study_developments[0].development_id == "sd1"
        assert batch.study_developments[0].activity_type == "pilot_testing"

    def test_ex_post_evaluation_parsing(self, sample_ddi_c26: Path) -> None:
        """ExPostEvaluation elements are parsed with completion date."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        batch = batches[0]
        assert len(batch.ex_post_evaluations) == 1
        assert batch.ex_post_evaluations[0].evaluation_id == "epe1"
        assert batch.ex_post_evaluations[0].completion_date == "2024-01-01"

    def test_graph_node_labels(self, sample_ddi_c26: Path) -> None:
        """DDI-C 2.6 records produce correctly labeled graph nodes."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        graph = DDIIngestGraph.from_ddi_batch(batches[0])
        labels = {n.label for n in graph.nodes()}
        for label in (
            "NCube",
            "NCubeGroup",
            "DocumentDescription",
            "SampleFrame",
            "QualityStatement",
            "StudyAuthorization",
            "StudyDevelopment",
            "ExPostEvaluation",
        ):
            assert label in labels, f"{label} not in node labels"

    def test_graph_in_dataset_relationships(self, sample_ddi_c26: Path) -> None:
        """DDI-C 2.6 entities have IN_DATASET relationships to the Dataset."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        graph = DDIIngestGraph.from_ddi_batch(batches[0])
        in_dataset_labels = set()
        for rel in graph.relationships():
            if rel.type == "IN_DATASET" and rel.end.label == "Dataset":
                in_dataset_labels.add(rel.start.label)
        for label in (
            "NCube",
            "NCubeGroup",
            "DocumentDescription",
            "SampleFrame",
            "QualityStatement",
            "StudyAuthorization",
            "StudyDevelopment",
            "ExPostEvaluation",
        ):
            assert label in in_dataset_labels, f"Missing IN_DATASET for {label}"

    def test_ncube_group_groups_relationship(self, sample_ddi_c26: Path) -> None:
        """NCubeGroup -> NCube GROUPS relationship is built."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        graph = DDIIngestGraph.from_ddi_batch(batches[0])
        groups_rels = [
            r for r in graph.relationships() if r.type == "GROUPS" and r.start.label == "NCubeGroup"
        ]
        assert len(groups_rels) == 1
        assert groups_rels[0].end.label == "NCube"

    def test_total_records_includes_c26(self, sample_ddi_c26: Path) -> None:
        """DDIBatch.total_records includes DDI-C 2.6 entities."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        total = batches[0].total_records()
        # 1 study + 1 ncube + 1 ncube_group + 1 doc_desc + 1 sample_frame
        # + 1 quality + 1 auth + 1 dev + 1 eval + 1 doc_description org producer
        assert total >= 9

    def test_as_dict_includes_c26_keys(self, sample_ddi_c26: Path) -> None:
        """DDIBatch.as_dict includes DDI-C 2.6 keys."""
        batches = list(parse_ddi_batches(sample_ddi_c26, "ds1", None, 500))
        d = batches[0].as_dict()
        for key in (
            "ncubes",
            "ncube_groups",
            "document_descriptions",
            "sample_frames",
            "quality_statements",
            "study_authorizations",
            "study_developments",
            "ex_post_evaluations",
        ):
            assert key in d, f"Missing key {key} in as_dict"


# ============================================================================
# DDI-CDI 1.0 Parsing Tests
# ============================================================================


class TestCDIParsing:
    """Tests for DDI-CDI 1.0 XML parsing."""

    def test_cdi_format_detection(self, sample_cdi_xml: Path, sample_ddi_c26: Path) -> None:
        """CDI format is detected by Wrapper root element."""
        assert is_cdi_format(sample_cdi_xml) is True
        assert is_cdi_format(sample_ddi_c26) is False

    def test_detect_ddi_format_cdi(self, sample_cdi_xml: Path) -> None:
        """detect_ddi_format returns 'cdi' for DDI-CDI files."""
        assert detect_ddi_format(sample_cdi_xml) == "cdi"

    def test_detect_ddi_format_codebook(self, sample_ddi_c26: Path) -> None:
        """detect_ddi_format returns 'codebook' for DDI-C files."""
        assert detect_ddi_format(sample_ddi_c26) == "codebook"

    def test_concept_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI Concept entities are parsed."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        assert len(batches) >= 1
        all_concepts = []
        for batch in batches:
            all_concepts.extend(batch.concepts)
        assert len(all_concepts) == 1
        assert all_concepts[0].cdi_id == "concept-001"
        assert all_concepts[0].name == "Employment Status"

    def test_agent_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI Agent entities are parsed with correct agent_type."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_agents = []
        for batch in batches:
            all_agents.extend(batch.agents)
        assert len(all_agents) == 2
        types = {a.agent_type for a in all_agents}
        assert "Organization" in types
        assert "Individual" in types

    def test_code_and_category_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI Code and Category entities are parsed."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_codes = []
        all_categories = []
        for batch in batches:
            all_codes.extend(batch.codes)
            all_categories.extend(batch.categories)
        assert len(all_codes) == 1
        assert all_codes[0].cdi_id == "code-001"
        assert len(all_categories) == 1
        assert all_categories[0].cdi_id == "cat-001"

    def test_data_structure_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI DataStructure entities are parsed with structure_type."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_structures = []
        for batch in batches:
            all_structures.extend(batch.data_structures)
        assert len(all_structures) == 1
        assert all_structures[0].structure_type == "wide"

    def test_dataset_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI DataSet entities are parsed with dataset_type."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_datasets = []
        for batch in batches:
            all_datasets.extend(batch.datasets)
        assert len(all_datasets) == 1
        assert all_datasets[0].dataset_type == "wide"

    def test_statistical_classification_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI StatisticalClassification entities are parsed."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_classifications = []
        for batch in batches:
            all_classifications.extend(batch.statistical_classifications)
        assert len(all_classifications) == 1
        assert all_classifications[0].cdi_id == "sc-001"
        assert all_classifications[0].name == "ISCO-08"

    def test_instance_variable_parsing(self, sample_cdi_xml: Path) -> None:
        """CDI InstanceVariable entities are parsed."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_vars = []
        for batch in batches:
            all_vars.extend(batch.instance_variables)
        assert len(all_vars) == 1
        assert all_vars[0].cdi_id == "iv-001"
        assert all_vars[0].name == "emp_status"

    def test_relationships_parsed(self, sample_cdi_xml: Path) -> None:
        """CDI relationships are extracted from association elements."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_rels = []
        for batch in batches:
            all_rels.extend(batch.relationships)
        rel_types = {r.rel_type for r in all_rels}
        # Code_denotes_Category -> DENOTES
        assert "DENOTES" in rel_types

    def test_is_structured_by_relationship(self, sample_cdi_xml: Path) -> None:
        """DataSet_isStructuredBy_DataStructure creates IS_STRUCTURED_BY."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        all_rels = []
        for batch in batches:
            all_rels.extend(batch.relationships)
        structured_rels = [r for r in all_rels if r.rel_type == "IS_STRUCTURED_BY"]
        assert len(structured_rels) == 1
        assert structured_rels[0].source_id == "dset-001"
        assert structured_rels[0].target_id == "ds-001"

    def test_batch_as_dict(self, sample_cdi_xml: Path) -> None:
        """CDI batch serialization produces expected keys."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        d = batches[0].as_dict()
        assert "concepts" in d
        assert "agents" in d
        assert "categories" in d
        assert "codes" in d
        assert "relationships" in d
        assert "data_structures" in d
        assert "datasets" in d

    def test_total_records(self, sample_cdi_xml: Path) -> None:
        """total_records counts all entity records in the batch."""
        batches = list(parse_cdi_batches(sample_cdi_xml, chunk_size=500))
        total = batches[0].total_records()
        # 1 concept + 2 agents + 1 category + 1 code_list + 1 code
        # + 1 classification + 1 instance_var + 1 data_structure + 1 dataset = 10
        assert total == 10

    def test_empty_cdi_file(self, tmp_path: Path) -> None:
        """Empty Wrapper produces no batches."""
        xml = tmp_path / "empty_cdi.xml"
        xml.write_text('<Wrapper xmlns="http://ddi-cdi/1.0"></Wrapper>')
        batches = list(parse_cdi_batches(xml, chunk_size=500))
        assert len(batches) == 0

    def test_chunking(self, tmp_path: Path) -> None:
        """CDI parser respects chunk_size for batching."""
        # Generate many entities to trigger multiple batches
        entities = ""
        for i in range(15):
            entities += f"""
            <Concept>
                <Identifier><StringValue>c-{i:03d}</StringValue></Identifier>
                <ObjectName>Concept {i}</ObjectName>
            </Concept>"""
        xml = tmp_path / "many_cdi.xml"
        xml.write_text(f'<Wrapper xmlns="http://ddi-cdi/1.0">{entities}</Wrapper>')
        batches = list(parse_cdi_batches(xml, chunk_size=5))
        assert len(batches) == 3  # 15 entities / 5 per batch

    def test_duplicate_ids_deduped(self, tmp_path: Path) -> None:
        """Duplicate CDI entity IDs are deduplicated."""
        xml = tmp_path / "dup_cdi.xml"
        xml.write_text(
            """
            <Wrapper xmlns="http://ddi-cdi/1.0">
                <Concept>
                    <Identifier><StringValue>dup-001</StringValue></Identifier>
                    <ObjectName>First</ObjectName>
                </Concept>
                <Concept>
                    <Identifier><StringValue>dup-001</StringValue></Identifier>
                    <ObjectName>Duplicate</ObjectName>
                </Concept>
            </Wrapper>
            """
        )
        batches = list(parse_cdi_batches(xml, chunk_size=500))
        all_concepts = []
        for batch in batches:
            all_concepts.extend(batch.concepts)
        assert len(all_concepts) == 1
        assert all_concepts[0].name == "First"


# ============================================================================
# Schema Definition Tests
# ============================================================================


class TestSchemaDefinitions:
    """Tests for DDI-C 2.6 and DDI-CDI schema definitions."""

    def test_ddi_c26_node_definitions_in_schema(self) -> None:
        """DDI-C 2.6 node definitions exist in DDISchema.CODEBOOK_NODES."""
        labels = {n.label for n in DDISchema.CODEBOOK_NODES}
        for label in (
            "NCube",
            "NCubeGroup",
            "DocumentDescription",
            "SampleFrame",
            "QualityStatement",
            "StudyAuthorization",
            "StudyDevelopment",
            "ExPostEvaluation",
        ):
            assert label in labels, f"Missing CODEBOOK_NODES label: {label}"

    def test_cdi_node_definitions_in_schema(self) -> None:
        """DDI-CDI node definitions exist in DDISchema.CDI_NODES."""
        labels = {n.label for n in DDISchema.CDI_NODES}
        for label in (
            "CDIConcept",
            "CDIAgent",
            "CDICategory",
            "CDICodeList",
            "CDIStatisticalClassification",
            "CDIInstanceVariable",
            "CDIDataStructure",
            "CDIDataSet",
            "CDIDataStore",
            "CDILogicalRecord",
            "CDIActivity",
            "CDIProcessingAgent",
            "CDICorrespondenceTable",
        ):
            assert label in labels, f"Missing CDI_NODES label: {label}"
        assert len(DDISchema.CDI_NODES) == 32

    def test_get_all_nodes_includes_cdi(self) -> None:
        """get_all_nodes returns CDI nodes when include_cdi=True."""
        with_cdi = DDISchema.get_all_nodes(include_fragments=False, include_cdi=True)
        without_cdi = DDISchema.get_all_nodes(include_fragments=False, include_cdi=False)
        assert len(with_cdi) > len(without_cdi)
        assert len(with_cdi) - len(without_cdi) == 32

    def test_get_all_nodes_default_includes_all(self) -> None:
        """Default get_all_nodes includes codebook, fragment, and CDI nodes."""
        all_nodes = DDISchema.get_all_nodes()
        codebook_count = len(DDISchema.CODEBOOK_NODES)
        fragment_count = len(DDISchema.FRAGMENT_NODES)
        cdi_count = len(DDISchema.CDI_NODES)
        assert len(all_nodes) == codebook_count + fragment_count + cdi_count

    def test_schema_queries_include_cdi(self) -> None:
        """Schema queries include DDI-CDI constraints and indexes."""
        queries_with = DDISchema.generate_all_schema_queries(include_cdi=True)
        queries_without = DDISchema.generate_all_schema_queries(include_cdi=False)
        assert len(queries_with) > len(queries_without)
        cdi_queries = [q for q in queries_with if "CDI" in q]
        assert len(cdi_queries) > 0

    def test_cdi_nodes_use_cdi_id_field(self) -> None:
        """All CDI node definitions use 'cdi_id' as identity field."""
        for node in DDISchema.CDI_NODES:
            assert node.id_field == "cdi_id", f"{node.label} uses {node.id_field} instead of cdi_id"

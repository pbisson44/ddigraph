from pathlib import Path

import pytest

from ddigraph.ingest.loader import (
    AccessConditionRecord,
    AccessPolicyRecord,
    CategoryGroupRecord,
    CategoryRecord,
    CitationRecord,
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
    DocumentDescriptionRecord,
    ExPostEvaluationRecord,
    FundingRecord,
    GroupRecord,
    LogicalRecord,
    MethodologyNoteRecord,
    NCubeGroupRecord,
    NCubeRecord,
    OrganizationRecord,
    OtherMaterialRecord,
    PhysicalStructureRecord,
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
    parse_ddi_batches,
)
from ddigraph.schema.ddi_graph import DDIIngestGraph


def _relationship_signatures(
    graph: DDIIngestGraph,
) -> set[tuple[str, str, object, str, object]]:
    signatures: set[tuple[str, str, object, str, object]] = set()
    for rel in graph.relationships():
        _start_id_key, start_id_value = next(iter(rel.start.identity.items()))
        _end_id_key, end_id_value = next(iter(rel.end.identity.items()))
        signatures.add((rel.type, rel.start.label, start_id_value, rel.end.label, end_id_value))
    return signatures


def test_relationships_cover_all_reference_fields() -> None:
    dataset = DatasetRecord("ds", "Dataset")
    study = StudyRecord("ds", "Dataset", "study1", None, None)
    org = OrganizationRecord("ds", "Dataset", "org1", None, None)
    series = SeriesRecord("ds", "Dataset", "series1", None)
    group = GroupRecord("ds", "Dataset", "group1", None)
    event = DataCollectionEventRecord("ds", "Dataset", "event1", None)
    data_file = DataFileRecord("ds", "Dataset", "file1", "file", None)
    scheme = CodeSchemeRecord("ds", "Dataset", "scheme1", None)
    category = CategoryRecord("ds", "Dataset", "cat1", "Category", "1", "scheme1")
    universe = UniverseRecord("ds", "Dataset", "univ1", None)
    concept = ConceptRecord("ds", "Dataset", "concept1", None)
    question = QuestionRecord("ds", "Dataset", "q1", "Q?")
    question.control_construct_references = ["cc1"]
    variable = VariableRecord(
        dataset_id="ds",
        dataset_name="Dataset",
        variable_id="var1",
        label="Var",
        concept="concept1",
        file_id="file1",
        question_id="q1",
        question_text="Q?",
        universe_id="univ1",
        category_ids=["cat1"],
    )
    question_item = QuestionItemRecord(
        dataset_id="ds",
        dataset_name="Dataset",
        question_item_id="qi1",
        text="QI",
        parent_question_id="q1",
        parent_grid_id="grid1",
        parent_flow_id="flow1",
        variable_id="var1",
    )
    question_item.control_construct_references = ["cc1"]
    question_grid = QuestionGridRecord("ds", "Dataset", "grid1", None)
    question_grid.control_construct_references = ["cc1"]
    question_flow = QuestionFlowRecord("ds", "Dataset", "flow1", None)
    question_flow.control_construct_references = ["cc1"]
    var_group = VarGroupRecord("ds", "Dataset", "vg1", None, None)
    var_group.variable_ids = ["var1"]
    category_group = CategoryGroupRecord("ds", "Dataset", "cg1", None, None)
    category_group.category_ids = ["cat1"]
    sampling = SamplingProcedureRecord("ds", "Dataset", "sample1", None)
    weight = WeightRecord("ds", "Dataset", "weight1", None)
    representation = RepresentationRecord("ds", "Dataset", "rep1", None)
    method_note = MethodologyNoteRecord("ds", "Dataset", "note1", None)
    other_material = OtherMaterialRecord("ds", "Dataset", "mat1", None, None)
    software = SoftwareRecord("ds", "Dataset", "soft1", None, None)
    collection_instrument = CollectionInstrumentRecord("ds", "Dataset", "instr1", None, None)
    collection_instrument.referenced_construct_id = "cc1"
    control_construct = ControlConstructRecord("ds", "Dataset", "cc1", "CC", "type")
    represented_variable = RepresentedVariableRecord("ds", "Dataset", "rv1", None, "concept1")
    comparison = ComparisonRecord("ds", "Dataset", "cmp1", None, None)
    access_policy = AccessPolicyRecord("ds", "Dataset", "policy1", None, None)
    access_condition = AccessConditionRecord("ds", "Dataset", "access1", None)
    citation = CitationRecord("ds", "Dataset", "cit1", None, None, None)
    coverage = CoverageRecord("ds", "Dataset", "cov1", None, None, None, None)
    funding = FundingRecord("ds", "Dataset", "fund1", "agency", None)
    contributor = ContributorRoleRecord("ds", "Dataset", "cont1", None, None)
    logical_record = LogicalRecord("ds", "Dataset", "lr1", None)
    physical_structure = PhysicalStructureRecord("ds", "Dataset", "ps1", None)
    ncube = NCubeRecord("ds", "Dataset", "nc1", None)
    ncube_group = NCubeGroupRecord("ds", "Dataset", "ncg1", None, ncube_ids=["nc1"])
    doc_desc = DocumentDescriptionRecord("ds", "Dataset", "doc1", None, None)
    sample_frame = SampleFrameRecord("ds", "Dataset", "sf1", None)
    quality_stmt = QualityStatementRecord("ds", "Dataset", "qs1", None)
    study_auth = StudyAuthorizationRecord("ds", "Dataset", "sa1", None)
    study_dev = StudyDevelopmentRecord("ds", "Dataset", "sd1", None)
    ex_post_eval = ExPostEvaluationRecord("ds", "Dataset", "epe1", None)

    graph = DDIIngestGraph(
        dataset=dataset,
        studies=[study],
        data_files=[data_file],
        code_schemes=[scheme],
        categories=[category],
        universes=[universe],
        concepts=[concept],
        variables=[variable],
        questions=[question],
        question_items=[question_item],
        organizations=[org],
        series_list=[series],
        groups=[group],
        data_collection_events=[event],
        logical_records=[logical_record],
        physical_structures=[physical_structure],
        other_materials=[other_material],
        var_groups=[var_group],
        category_groups=[category_group],
        question_grids=[question_grid],
        question_flows=[question_flow],
        sampling_procedures=[sampling],
        weights=[weight],
        representations=[representation],
        code_lists=[],
        methodology_notes=[method_note],
        processing_events=[],
        software=[software],
        access_conditions=[access_condition],
        citations=[citation],
        coverage=[coverage],
        funding=[funding],
        contributor_roles=[contributor],
        instruments=[collection_instrument],
        control_constructs=[control_construct],
        represented_variables=[represented_variable],
        comparisons=[comparison],
        access_policies=[access_policy],
        ncubes=[ncube],
        ncube_groups=[ncube_group],
        document_descriptions=[doc_desc],
        sample_frames=[sample_frame],
        quality_statements=[quality_stmt],
        study_authorizations=[study_auth],
        study_developments=[study_dev],
        ex_post_evaluations=[ex_post_eval],
        generic_identifiables=[],
    )

    relationships = _relationship_signatures(graph)

    expected = {
        ("DESCRIBES", "Study", "study1", "Dataset", "ds"),
        ("ASSOCIATED_WITH", "Organization", "org1", "Dataset", "ds"),
        ("IN_DATASET", "Series", "series1", "Dataset", "ds"),
        ("IN_DATASET", "Group", "group1", "Dataset", "ds"),
        ("IN_DATASET", "DataCollectionEvent", "event1", "Dataset", "ds"),
        ("IN_DATASET", "DataFile", "file1", "Dataset", "ds"),
        ("IN_DATASET", "CodeScheme", "scheme1", "Dataset", "ds"),
        ("IN_DATASET", "Category", "cat1", "Dataset", "ds"),
        ("IN_SCHEME", "Category", "cat1", "CodeScheme", "scheme1"),
        ("IN_DATASET", "Universe", "univ1", "Dataset", "ds"),
        ("IN_DATASET", "Concept", "concept1", "Dataset", "ds"),
        ("IN_DATASET", "Question", "q1", "Dataset", "ds"),
        ("USES_CONSTRUCT", "Question", "q1", "ControlConstruct", "cc1"),
        ("IN_DATASET", "Variable", "var1", "Dataset", "ds"),
        ("USES_CONCEPT", "Variable", "var1", "Concept", "concept1"),
        ("IN_FILE", "Variable", "var1", "DataFile", "file1"),
        ("IN_UNIVERSE", "Variable", "var1", "Universe", "univ1"),
        ("ASKED_AS", "Variable", "var1", "Question", "q1"),
        ("USES_CATEGORY", "Variable", "var1", "Category", "cat1"),
        ("USES_QUESTION_ITEM", "Variable", "var1", "QuestionItem", "qi1"),
        ("IN_DATASET", "QuestionItem", "qi1", "Dataset", "ds"),
        ("PART_OF", "QuestionItem", "qi1", "Question", "q1"),
        ("IN_GRID", "QuestionItem", "qi1", "QuestionGrid", "grid1"),
        ("IN_FLOW", "QuestionItem", "qi1", "QuestionFlow", "flow1"),
        ("USES_CONSTRUCT", "QuestionItem", "qi1", "ControlConstruct", "cc1"),
        ("IN_DATASET", "QuestionGrid", "grid1", "Dataset", "ds"),
        ("USES_CONSTRUCT", "QuestionGrid", "grid1", "ControlConstruct", "cc1"),
        ("IN_DATASET", "QuestionFlow", "flow1", "Dataset", "ds"),
        ("USES_CONSTRUCT", "QuestionFlow", "flow1", "ControlConstruct", "cc1"),
        ("IN_DATASET", "VarGroup", "vg1", "Dataset", "ds"),
        ("GROUPS", "VarGroup", "vg1", "Variable", "var1"),
        ("IN_DATASET", "CategoryGroup", "cg1", "Dataset", "ds"),
        ("GROUPS", "CategoryGroup", "cg1", "Category", "cat1"),
        ("IN_DATASET", "SamplingProcedure", "sample1", "Dataset", "ds"),
        ("IN_DATASET", "Weight", "weight1", "Dataset", "ds"),
        ("IN_DATASET", "Representation", "rep1", "Dataset", "ds"),
        ("IN_DATASET", "MethodologyNote", "note1", "Dataset", "ds"),
        ("IN_DATASET", "OtherMaterial", "mat1", "Dataset", "ds"),
        ("IN_DATASET", "Software", "soft1", "Dataset", "ds"),
        ("INSTRUMENT_FOR", "CollectionInstrument", "instr1", "Dataset", "ds"),
        ("USES_CONSTRUCT", "CollectionInstrument", "instr1", "ControlConstruct", "cc1"),
        ("USES_CONSTRUCT", "ControlConstruct", "cc1", "Dataset", "ds"),
        ("REPRESENTS", "RepresentedVariable", "rv1", "Dataset", "ds"),
        ("USES_CONCEPT", "RepresentedVariable", "rv1", "Concept", "concept1"),
        ("HAS_COMPARISON", "Comparison", "cmp1", "Dataset", "ds"),
        ("GOVERNED_BY", "AccessPolicy", "policy1", "Dataset", "ds"),
        ("IN_DATASET", "AccessCondition", "access1", "Dataset", "ds"),
        ("DESCRIBES", "Citation", "cit1", "Dataset", "ds"),
        ("COVERS", "Coverage", "cov1", "Dataset", "ds"),
        ("FUNDS", "Funding", "fund1", "Dataset", "ds"),
        ("CONTRIBUTES_TO", "Contributor", "cont1", "Dataset", "ds"),
        ("IN_DATASET", "LogicalRecord", "lr1", "Dataset", "ds"),
        ("IN_DATASET", "PhysicalStructure", "ps1", "Dataset", "ds"),
        ("IN_DATASET", "NCube", "nc1", "Dataset", "ds"),
        ("IN_DATASET", "NCubeGroup", "ncg1", "Dataset", "ds"),
        ("GROUPS", "NCubeGroup", "ncg1", "NCube", "nc1"),
        ("IN_DATASET", "DocumentDescription", "doc1", "Dataset", "ds"),
        ("IN_DATASET", "SampleFrame", "sf1", "Dataset", "ds"),
        ("IN_DATASET", "QualityStatement", "qs1", "Dataset", "ds"),
        ("IN_DATASET", "StudyAuthorization", "sa1", "Dataset", "ds"),
        ("IN_DATASET", "StudyDevelopment", "sd1", "Dataset", "ds"),
        ("IN_DATASET", "ExPostEvaluation", "epe1", "Dataset", "ds"),
    }

    assert expected <= relationships


def test_relationships_skip_missing_targets_in_fixture() -> None:
    fixture = Path(__file__).resolve().parent.parent / "demo" / "Ireland_LabourSurvey.xml"
    # Demo data lives in Git LFS; CI checkout does not fetch LFS
    # objects. Skip when the file is an unmaterialised pointer or
    # absent (this is a demo-data smoke check, not a unit test).
    if not fixture.exists() or fixture.read_bytes()[:40].startswith(
        b"version https://git-lfs.github.com/spec"
    ):
        pytest.skip("demo/Ireland_LabourSurvey.xml not materialised (Git LFS pointer)")
    batches = list(
        parse_ddi_batches(
            fixture,
            "ie-lfs",
            "Ireland Labour Survey",
            chunk_size=50,
        )
    )
    graph = DDIIngestGraph.from_ddi_batch(batches[11])

    relationships = _relationship_signatures(graph)

    assert (
        "IN_DATASET",
        "QuestionItem",
        "ie-lfs:question_item_1",
        "Dataset",
        "ie-lfs",
    ) in relationships
    assert (
        "IN_DATASET",
        "QuestionItem",
        "ie-lfs:question_item_2",
        "Dataset",
        "ie-lfs",
    ) in relationships
    assert all(rel[3] != "ControlConstruct" for rel in relationships)


def test_every_ddi_batch_collection_is_exposed_in_graph() -> None:
    """Every collection on DDIBatch must be exposed on DDIIngestGraph.

    If a new record type is added to :class:`DDIBatch` without being
    wired through :meth:`DDIIngestGraph.from_ddi_batch`, the records
    would be silently dropped at graph-build time.  This audit enforces
    coverage: every batch field (besides ``dataset``) must have a
    matching graph field populated with the same list.
    """

    from dataclasses import fields

    from ddigraph.ingest.loader import DatasetRecord, DDIBatch
    from ddigraph.schema.ddi_graph import DDIIngestGraph

    dataset = DatasetRecord("ds", None)
    batch = DDIBatch(
        dataset=dataset,
        studies=[],
        data_files=[],
        code_schemes=[],
        categories=[],
        universes=[],
        concepts=[],
        variables=[],
        questions=[],
        question_items=[],
        organizations=[],
        series_list=[],
        groups=[],
        data_collection_events=[],
        logical_records=[],
        physical_structures=[],
        other_materials=[],
        var_groups=[],
        category_groups=[],
        question_grids=[],
        question_flows=[],
        sampling_procedures=[],
        weights=[],
        representations=[],
        code_lists=[],
        methodology_notes=[],
        processing_events=[],
        software=[],
        access_conditions=[],
        citations=[],
        coverage=[],
        funding=[],
        contributor_roles=[],
        instruments=[],
        control_constructs=[],
        represented_variables=[],
        comparisons=[],
        access_policies=[],
    )
    graph = DDIIngestGraph.from_ddi_batch(batch)

    batch_fields = {f.name for f in fields(DDIBatch)}
    graph_fields = {f.name for f in fields(DDIIngestGraph)}
    missing = batch_fields - graph_fields
    assert not missing, f"DDIBatch fields not exposed on DDIIngestGraph: {missing}"
    # dataset is scalar; every other field must be a list on both sides.
    for name in batch_fields - {"dataset"}:
        assert isinstance(getattr(graph, name), list), f"{name} is not a list on DDIIngestGraph"


def test_every_graph_collection_is_anchored_to_dataset() -> None:
    """Every non-dataset graph collection must anchor to Dataset.

    Without a Dataset-anchored relationship a node type is orphaned in
    the ingest graph; this guard surfaces such regressions.
    """

    from dataclasses import fields

    from ddigraph.schema.ddi_graph import DDI_RELATIONSHIPS, DDIIngestGraph

    # ``generic_identifiables`` is anchored through a bespoke code path
    # in ``DDIIngestGraph.relationships`` (not via ``DDI_RELATIONSHIPS``),
    # so it's excluded from this static audit but covered separately by
    # ``test_generic_capture.py``.
    anchored = {rel.start_attr for rel in DDI_RELATIONSHIPS if rel.end_label == "Dataset"}
    expected = {f.name for f in fields(DDIIngestGraph)} - {
        "dataset",
        "generic_identifiables",
    }
    missing = expected - anchored
    assert not missing, f"Collections without a Dataset-anchoring relationship: {missing}"


def test_every_graph_collection_has_a_cypher_template() -> None:
    """Every non-dataset graph collection must have a Cypher write template.

    Without a template registered in ``_DDI_CYPHER_QUERIES``, records
    reach ``DDIIngestGraph.as_dict()`` but are silently dropped by
    ``Neo4jGraphAdapter.write_batch`` because the write loop only
    iterates over registered templates. This audit enforces coverage so
    a new collection on :class:`DDIIngestGraph` cannot regress to a
    dataset-only write.
    """

    from dataclasses import fields

    from ddigraph.schema.ddi_graph import DDIIngestGraph
    from ddigraph.schema.neo4j_adapter import _DDI_CYPHER_QUERIES

    graph_fields = {f.name for f in fields(DDIIngestGraph)} - {"dataset"}
    cypher_keys = {key for key, _ in _DDI_CYPHER_QUERIES}
    missing = graph_fields - cypher_keys
    assert not missing, f"Graph collections without a Cypher template: {missing}"

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import pytest
from lxml import etree
from neo4j import AsyncDriver
from neo4j.exceptions import TransientError

try:
    import psutil  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

from ddigraph.config import Settings
from ddigraph.ingest.loader import (
    DRY_RUN_MESSAGE,
    CodeListRecord,
    DatasetRecord,
    DDIBatch,
    DDIBatchStream,
    DDILoader,
    QuestionGridRecord,
    QuestionItemRecord,
    RepresentationRecord,
    StudyRecord,
    VariableRecord,
    parse_ddi_batches,
    parse_ddi_variables,
)
from ddigraph.schema.adapter import GraphWriteAdapter
from ddigraph.schema.ddi_graph import DDIIngestGraph


class FakeTx:
    def __init__(
        self,
        recorder: list[dict[str, Any]],
        *,
        session_config: dict[str, Any],
        transaction_config: dict[str, Any],
    ) -> None:
        self.recorder = recorder
        self.session_config = session_config
        self.transaction_config = transaction_config

    class _Result:
        @staticmethod
        def consume() -> None:  # pragma: no cover - trivial
            return None

    def run(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> FakeTx._Result:
        entry: dict[str, Any] = {"query": query.strip(), "parameters": parameters}
        if self.session_config:
            entry["session_config"] = self.session_config
        if self.transaction_config:
            entry["transaction_config"] = self.transaction_config
        self.recorder.append(entry)
        return FakeTx._Result()


class FakeSession:
    def __init__(self, recorder: list[dict[str, Any]], session_config: dict[str, Any]) -> None:
        self.recorder = recorder
        self.session_config = session_config

    def __enter__(self) -> FakeSession:  # pragma: no cover - trivial
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - trivial
        return None

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def execute_write(self, fn: Callable[[FakeTx], Any], **config: Any) -> None:
        tx = FakeTx(self.recorder, session_config=self.session_config, transaction_config=config)
        fn(tx)


class FakeDriver:
    def __init__(self) -> None:
        self.recorder: list[dict[str, Any]] = []

    def session(
        self, database: str | None = None, **config: Any
    ) -> FakeSession:  # pragma: no cover - trivial
        session_config: dict[str, Any] = {"database": database}
        session_config.update(config)
        return FakeSession(self.recorder, session_config)


class AwaitingRunResult:
    def __init__(self, tx: AwaitingRunTx) -> None:
        self.tx = tx

    async def consume(self) -> None:
        self.tx.consumed_results += 1


class AwaitingRunTx:
    def __init__(self) -> None:
        self.run_calls = 0
        self.parameters: dict[str, Any] | None = None
        self.consumed_results = 0

    async def run(self, query: str, parameters: dict[str, Any] | None = None) -> AwaitingRunResult:
        self.run_calls += 1
        self.parameters = parameters or {}
        return AwaitingRunResult(self)


class AwaitingRunSession:
    def __init__(self, tx: AwaitingRunTx, session_config: dict[str, Any]) -> None:
        self.tx = tx
        self.session_config = session_config

    async def __aenter__(self) -> AwaitingRunSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def execute_write(self, fn: Callable[[AwaitingRunTx], Any], **config: Any) -> None:
        tx = self.tx
        result = fn(tx)
        if asyncio.iscoroutine(result):
            await result


class AwaitingRunDriver:
    def __init__(self) -> None:
        self.tx = AwaitingRunTx()

    def session(self, database: str | None = None, **config: Any) -> AwaitingRunSession:
        session_config: dict[str, Any] = {"database": database}
        session_config.update(config)
        return AwaitingRunSession(self.tx, session_config)


class RecordingMetrics:
    def __init__(self) -> None:
        self.counts: list[tuple[str, int]] = []
        self.observations: list[tuple[str, float]] = []

    def increment(self, name: str, value: int = 1) -> None:
        self.counts.append((name, value))

    def observe(self, name: str, value: float) -> None:
        self.observations.append((name, value))


class FlakyAdapter:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0
        self.graphs: list[Any] = []

    async def write_batch(
        self,
        graph: Any,
        *,
        session_config: dict[str, Any] | None = None,
        transaction_config: dict[str, Any] | None = None,
    ) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TransientError("temporary")
        self.graphs.append(graph)


class PurgeRecordingAdapter:
    def __init__(self) -> None:
        self.store: dict[str, set[str]] = defaultdict(set)
        self.events: list[tuple[str, object]] = []

    async def purge_dataset(
        self,
        dataset_id: str,
        *,
        session_config: dict[str, Any] | None = None,
        transaction_config: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(("purge", dataset_id))
        self.store.pop(dataset_id, None)

    async def write_batch(
        self,
        graph: Any,
        *,
        session_config: dict[str, Any] | None = None,
        transaction_config: dict[str, Any] | None = None,
    ) -> None:
        variable_ids = {variable.variable_id for variable in graph.variables}
        dataset_id = graph.dataset.id
        self.store[dataset_id].update(variable_ids)
        self.events.append(("write", list(variable_ids)))


@pytest.fixture
def sample_ddi(tmp_path: Path) -> Path:
    xml = tmp_path / "codebook.xml"
    xml.write_text(
        """
        <codeBook xmlns:l="ddi:logicalproduct:3_3" xmlns:p="ddi:physicaldataproduct:3_3">
            <docDscr>
                <citation>
                    <prodStmt>
                        <producer ID="org1">
                            <abbr>NSO</abbr>
                            <producerName>National Statistics Office</producerName>
                        </producer>
                    </prodStmt>
                </citation>
            </docDscr>
            <stdyDscr ID="s1">
                <citation><titlStmt><titl>Demo Study</titl></titlStmt></citation>
                <stdyInfo><abstract>Study abstract</abstract></stdyInfo>
                <stdyInfo><universe ID="u1">Adults 18+</universe></stdyInfo>
                <stdyInfo><serName ID="series1">Household Panel</serName></stdyInfo>
                <stdyInfo><group ID="grp1"><labl>Urban Cohort</labl></group></stdyInfo>
                <method><dataColl><collDate ID="dc1">2020-01-01</collDate></dataColl></method>
            </stdyDscr>
            <fileDscr ID="f1">
                <fileTxt>
                    <fileName>data.csv</fileName>
                    <fileURI>https://example.com/data.csv</fileURI>
                </fileTxt>
            </fileDscr>
            <catgryScheme ID="cs1">
                <labl>Age categories</labl>
                <catgry ID="c1"><labl>18-25</labl></catgry>
            </catgryScheme>
            <qstnItem ID="qi1" agency="NSO" URN="urn:ddi:qi1" version="2.0" name="Standalone">
                <qstnLit>Standalone question?</qstnLit>
            </qstnItem>
            <qstnGrid ID="qg1" agency="NSO" URN="urn:ddi:qg1">
                <qstnLit>Grid question?</qstnLit>
                <qstnItem ID="q1"><qstnLit>Grid item detail</qstnLit></qstnItem>
            </qstnGrid>
            <qstnFlow ID="qf1">Skip if not applicable</qstnFlow>
            <sampProc ID="sp1">Random sampling</sampProc>
            <weight ID="wt1">Household weight</weight>
            <representation ID="rep1"><labl>Numeric</labl></representation>
            <codeList ID="cl1"><labl>Yes/No</labl></codeList>
            <methodology ID="mn1">Descriptive methodology note</methodology>
            <processingEvent ID="pe1">Imputed missing values</processingEvent>
            <software ID="sw1" version="1.0"><name>DDI Tool</name></software>
            <accessConditions ID="ac1">Public use file</accessConditions>
            <l:logicalProduct>
                <l:logicalRecord ID="lr1"><l:labl>Logical record</l:labl></l:logicalRecord>
            </l:logicalProduct>
            <p:physicalDataProduct>
                <p:physicalStructure ID="ps1">
                    <p:labl>Physical structure</p:labl>
                </p:physicalStructure>
            </p:physicalDataProduct>
            <otherMat ID="mat1">
                <labl>Codebook PDF</labl>
                <URI>https://example.com/codebook.pdf</URI>
            </otherMat>
        <varGrp ID="vg1" var="v1 v2"><labl>Core Variables</labl></varGrp>
            <catgryGrp ID="cg1"><labl>Age buckets</labl><catgryRef IDREF="c1" /></catgryGrp>
            <dataDscr>
                <var ID="v1" agency="NSO" URN="urn:ddi:v1" version="1.0" name="Age variable">
                    <labl>Age</labl>
                    <concept>Demographics</concept>
                    <qstn ID="q1"><qstnLit>How old are you?</qstnLit></qstn>
                    <universe ID="u1">Adults 18+</universe>
                    <location fileid="f1" />
                    <catgry ID="c1"><catValu>1</catValu><labl>18-25</labl></catgry>
                    <catgry ID="c2"><catValu>2</catValu><labl>26-35</labl></catgry>
                </var>
                <var ID="v2">
                    <labl>Income</labl>
                    <concept>Economics</concept>
                    <qstn><qstnLit>What is your income?</qstnLit></qstn>
                    <location fileid="f1" />
                    <qstnItem ID="qi_var"><qstnLit>Income detail</qstnLit></qstnItem>
                </var>
                <var ID="v3">
                    <labl>Zip</labl>
                    <concept>Location</concept>
                    <universe ID="u2">All households</universe>
                </var>
            </dataDscr>
        </codeBook>
        """,
        encoding="utf-8",
    )
    return xml


@pytest.fixture
def lifecycle_ddi(tmp_path: Path) -> Path:
    xml = tmp_path / "lifecycle.xml"
    xml.write_text(
        """
        <DDIInstance xmlns:c="ddi:conceptualcomponent:3_3" xmlns:l="ddi:logicalproduct:3_3">
            <Fragment>
                <CategoryScheme ID="csL">
                    <labl>Lifecycle categories</labl>
                    <Category ID="cL"><labl>Yes</labl><catValu>1</catValu></Category>
                </CategoryScheme>
                <c:Universe ID="uL">Lifecycle universe</c:Universe>
                <c:Concept ID="conceptL"><labl>Lifecycle concept</labl></c:Concept>
                <CategoryGroup ID="cgL"><labl>Lifecycle group</labl></CategoryGroup>
                <VarGroup ID="vgL" var="vL"><labl>Lifecycle var group</labl></VarGroup>
                <QuestionGrid ID="qgL">
                    <qstnLit>Grid question</qstnLit>
                    <QuestionItem ID="qi_child"><qstnLit>Child question</qstnLit></QuestionItem>
                </QuestionGrid>
                <QuestionFlow ID="qfL">
                    <QuestionItem ID="qi_flow"><qstnLit>Flow question</qstnLit></QuestionItem>
                </QuestionFlow>
                <QuestionItem ID="qiL"><qstnLit>Standalone question</qstnLit></QuestionItem>
                <SamplingProcedure ID="spL">Sample procedure</SamplingProcedure>
                <Weight ID="wtL">Weight text</Weight>
                <OtherMaterial ID="omL">
                    <labl>Attachment</labl>
                    <URI>https://example.com</URI>
                </OtherMaterial>
                <Representation ID="repL"><labl>Numeric</labl></Representation>
                <CodeList ID="clL"><labl>Lifecycle codes</labl></CodeList>
                <Methodology ID="mnL">Lifecycle methodology</Methodology>
                <ProcessingEvent ID="peL">Lifecycle processing</ProcessingEvent>
                <Software ID="swL"><name>LifecycleSoft</name></Software>
                <AccessConditions ID="acL">Lifecycle access</AccessConditions>
                <BibliographicCitation ID="bcL">
                    <title>Lifecycle citation</title>
                </BibliographicCitation>
                <FundingInformation ID="fiL">Lifecycle funding</FundingInformation>
                <Contributor ID="conL"><abbr>Lifecycle contributor</abbr></Contributor>
                <Organization ID="orgL"><abbr>Lifecycle org</abbr></Organization>
                <Series ID="serL"><labl>Lifecycle series</labl></Series>
                <Group ID="grpL"><labl>Lifecycle group</labl></Group>
                <LogicalRecord ID="lrL"><labl>Lifecycle logical</labl></LogicalRecord>
                <PhysicalStructure ID="psL"><labl>Lifecycle physical</labl></PhysicalStructure>
                <RepresentedVariable ID="rvL">
                    <labl>Lifecycle represented variable</labl>
                </RepresentedVariable>
                <Sequence ID="seqL"><labl>Lifecycle sequence</labl></Sequence>
                <Loop ID="loopL"><labl>Lifecycle loop</labl></Loop>
                <StatementItem ID="stmtL"><labl>Lifecycle statement</labl></StatementItem>
            </Fragment>
        </DDIInstance>
        """,
        encoding="utf-8",
    )
    return xml


def write_simple_ddi(tmp_path: Path, variable_ids: list[str], filename: str) -> Path:
    variables = "".join(
        f'<var ID="{var_id}"><labl>{var_id}</labl></var>' for var_id in variable_ids
    )
    xml = tmp_path / filename
    xml.write_text(f"<codeBook><dataDscr>{variables}</dataDscr></codeBook>", encoding="utf-8")
    return xml


def _count_open_file_handles(target: Path) -> int:
    """Count open file handles for a given path.

    Returns -1 if unable to count (no psutil and no /proc).
    """
    target_resolved = target.resolve()

    if psutil is not None:
        process = psutil.Process()
        return sum(
            1
            for file_info in process.open_files()
            if Path(file_info.path).resolve() == target_resolved
        )

    fd_dir = Path("/proc/self/fd")
    if fd_dir.exists():
        count = 0
        for fd in fd_dir.iterdir():
            try:
                if fd.resolve() == target_resolved:
                    count += 1
            except FileNotFoundError:
                continue
        return count

    return -1  # Unable to count


def test_question_metadata_and_text_fallback(sample_ddi: Path, tmp_path: Path) -> None:
    batches = list(parse_ddi_batches(sample_ddi, "ds1", "Dataset", chunk_size=10))
    question_items = [qi for batch in batches for qi in batch.question_items]
    assert question_items
    qi = question_items[0]
    assert qi.urn == "urn:ddi:qi1"
    assert qi.agency == "NSO"
    assert qi.version == "2.0"
    assert qi.name == "Standalone"

    fallback_xml = tmp_path / "fallback.xml"
    fallback_xml.write_text(
        """
        <codeBook>
            <qstnItem ID="qi_fallback"><labl>Label text only</labl></qstnItem>
        </codeBook>
        """,
        encoding="utf-8",
    )

    fallback_batches = list(parse_ddi_batches(fallback_xml, "ds-fallback", "Dataset", chunk_size=5))
    fallback_item = fallback_batches[0].question_items[0]
    assert fallback_item.text == "Label text only"


def test_collection_instrument_metadata(tmp_path: Path) -> None:
    xml = tmp_path / "instrument.xml"
    xml.write_text(
        """
        <DDIInstance xmlns:r="ddi:reusable:3_3">
            <Fragment>
                <Instrument>
                    <r:URN>urn:ddi:instrument:1</r:URN>
                    <r:Agency>ACME</r:Agency>
                    <r:ID>inst-reusable</r:ID>
                    <r:Version>1.1</r:Version>
                    <InstrumentName><r:String>Household Questionnaire</r:String></InstrumentName>
                    <TypeOfInstrument>Computer-assisted interview</TypeOfInstrument>
                    <ExternalInstrumentLocation>
                        https://example.org/form.pdf
                    </ExternalInstrumentLocation>
                    <ExternalInstrumentLocation>
                        https://example.org/form_fr.pdf
                    </ExternalInstrumentLocation>
                    <ControlConstructReference>
                        <r:URN>urn:ddi:sequence:1</r:URN>
                    </ControlConstructReference>
                    <FieldedLanguages>en-US</FieldedLanguages>
                    <FieldedLanguages>fr-CA</FieldedLanguages>
                    <DevelopmentResultsReference>
                        <r:Agency>ACME</r:Agency>
                        <r:ID>dev-1</r:ID>
                        <r:Version>2.0</r:Version>
                        <r:TypeOfObject>DevelopmentResults</r:TypeOfObject>
                    </DevelopmentResultsReference>
                    <DevelopmentResultsReference>
                        <r:URN>urn:ddi:dev:2</r:URN>
                        <r:TypeOfObject>DevelopmentResults</r:TypeOfObject>
                    </DevelopmentResultsReference>
                    <r:Description>
                        <r:Content>Baseline wave</r:Content>
                    </r:Description>
                </Instrument>
            </Fragment>
        </DDIInstance>
        """,
        encoding="utf-8",
    )

    batches = list(parse_ddi_batches(xml, "ds-inst", "Dataset", chunk_size=5))
    instruments = [inst for batch in batches for inst in batch.instruments]

    assert instruments
    instrument = instruments[0]
    assert instrument.instrument_id == "ds-inst:instrument_1"
    assert instrument.instrument_type == "Computer-assisted interview"
    assert instrument.element_type == "Instrument"
    assert instrument.urn == "urn:ddi:instrument:1"
    assert instrument.agency == "ACME"
    assert instrument.id == "inst-reusable"
    assert instrument.version == "1.1"
    assert instrument.name == "Household Questionnaire"
    assert instrument.description == "Baseline wave"
    assert instrument.external_instrument_locations == [
        "https://example.org/form.pdf",
        "https://example.org/form_fr.pdf",
    ]
    assert instrument.control_construct_reference == "urn:ddi:sequence:1"
    assert instrument.fielded_languages == ["en-US", "fr-CA"]
    assert instrument.development_results_references == [
        "ACME:dev-1:2.0",
        "urn:ddi:dev:2",
    ]


@pytest.mark.skipif(
    psutil is None and not Path("/proc/self/fd").exists(),
    reason="Counting open file handles requires psutil or /proc access",
)
def test_ddi_batch_stream_closes_file_handles(tmp_path: Path) -> None:
    xml = tmp_path / "codebook.xml"
    xml.write_text(
        (
            '<codeBook><stdyDscr ID="s1"><citation><titlStmt><titl>Demo</titl>'
            "</titlStmt></citation></stdyDscr></codeBook>"
        ),
        encoding="utf-8",
    )

    for _ in range(3):
        stream = DDIBatchStream(
            path=xml, dataset_id="ds1", dataset_name=None, chunk_size=10, recover=False
        )
        list(stream)
        assert _count_open_file_handles(xml) == 0


def minimal_batch(dataset_id: str = "ds1") -> DDIBatch:
    return DDIBatch(
        dataset=DatasetRecord(id=dataset_id, name=None),
        studies=[
            StudyRecord(
                dataset_id=dataset_id,
                dataset_name=None,
                study_id="s1",
                title=None,
                abstract=None,
            )
        ],
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


def test_loader_awaits_tx_run_and_counts_nodes(tmp_path: Path) -> None:
    driver = AwaitingRunDriver()
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=Settings(chunk_size=10, writer_concurrency=1),
    )

    batch = minimal_batch("ds-demo")
    batch.variables.append(
        VariableRecord(
            dataset_id="ds-demo",
            dataset_name=None,
            variable_id="v1",
            label="Variable 1",
            concept=None,
            file_id=None,
            question_id=None,
            question_text=None,
            universe_id=None,
            category_ids=[],
        )
    )

    asyncio.run(loader._write_batch(batch))

    tx = driver.tx
    # With separate queries: 1 dataset + N entity types that have data
    # This batch has: dataset + studies + variables = 3 queries minimum
    assert tx.run_calls >= 1  # At least dataset query runs
    assert tx.consumed_results == tx.run_calls  # All results consumed
    assert tx.parameters is not None
    # The last query's parameters are stored; verify we got some parameters
    assert len(tx.parameters) > 0


def test_loader_loads_batches_with_async_run(tmp_path: Path) -> None:
    driver = AwaitingRunDriver()
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=Settings(chunk_size=10, writer_concurrency=1),
    )

    xml = write_simple_ddi(tmp_path, ["v1", "v2"], "simple.xml")

    totals = asyncio.run(
        loader.load(
            xml,
            dataset_id="ds-load",
            dataset_name="Load test",
        )
    )

    tx = driver.tx
    assert tx.run_calls >= 1
    assert tx.consumed_results == tx.run_calls
    assert sum(totals.values()) >= 2

    node_count = 1 + sum(
        len(value) for value in (tx.parameters or {}).values() if isinstance(value, list)
    )
    assert node_count > 1


async def test_async_write_batch_tracks_params_and_loads_counts(tmp_path: Path) -> None:
    driver = AwaitingRunDriver()
    settings = Settings(chunk_size=10, writer_concurrency=1)
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=settings,
    )

    rich_batch = DDIBatch(
        dataset=DatasetRecord(id="ds-rich", name="Rich dataset"),
        studies=[],
        data_files=[],
        code_schemes=[],
        categories=[],
        universes=[],
        concepts=[],
        variables=[],
        questions=[],
        question_items=[
            QuestionItemRecord(
                dataset_id="ds-rich",
                dataset_name="Rich dataset",
                question_item_id="qi-rich",
                text="Rich question item",
                parent_grid_id="qg-parent",
            )
        ],
        organizations=[],
        series_list=[],
        groups=[],
        data_collection_events=[],
        logical_records=[],
        physical_structures=[],
        other_materials=[],
        var_groups=[],
        category_groups=[],
        question_grids=[
            QuestionGridRecord(
                dataset_id="ds-rich",
                dataset_name="Rich dataset",
                question_grid_id="qg-parent",
                text="Parent grid",
            )
        ],
        question_flows=[],
        sampling_procedures=[],
        weights=[],
        representations=[
            RepresentationRecord(
                dataset_id="ds-rich",
                dataset_name="Rich dataset",
                representation_id="rep-rich",
                label="Representation",
            )
        ],
        code_lists=[
            CodeListRecord(
                dataset_id="ds-rich",
                dataset_name="Rich dataset",
                code_list_id="cl-rich",
                label="Rich code list",
            )
        ],
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

    await loader._write_batch(rich_batch)

    tx = driver.tx
    # With separate queries: 1 dataset + 4 entity types with data
    # (question_items, question_grids, representations, code_lists) = 5 queries
    assert tx.run_calls >= 1  # At least dataset query
    assert tx.consumed_results == tx.run_calls  # All results consumed

    # Note: tx.parameters only contains the LAST query's parameters
    # since AwaitingRunTx overwrites on each run() call
    assert tx.parameters is not None
    # The last query will have dataset reference
    assert "dataset" in tx.parameters

    xml = write_simple_ddi(tmp_path, ["v1", "v2"], "rich-load.xml")
    initial_calls = tx.run_calls

    totals = await loader.load(xml, dataset_id="ds-rich", dataset_name="Rich dataset")

    assert sum(totals.values()) >= 2
    # Multiple queries executed: dataset + variables at minimum
    assert driver.tx.run_calls > initial_calls
    assert driver.tx.consumed_results == driver.tx.run_calls


def test_parse_ddi_variables_batches(sample_ddi: Path) -> None:
    batches = list(parse_ddi_batches(sample_ddi, "ds", "Dataset", chunk_size=3))
    assert len(batches) >= 2
    assert isinstance(batches[0], DDIBatch)
    merged_variables = [v.variable_id for batch in batches for v in batch.variables]
    assert merged_variables[0] == "v1"
    assert set(merged_variables) == {"v1", "v2", "v3"}
    categories = [cat.category_id for batch in batches for cat in batch.categories]
    assert {"c1", "c2"}.issubset(set(categories))
    organizations = [org.organization_id for batch in batches for org in batch.organizations]
    assert "org1" in organizations
    series = [series.series_id for batch in batches for series in batch.series_list]
    assert "series1" in series
    groups = [group.group_id for batch in batches for group in batch.groups]
    assert "grp1" in groups
    logical_records = [rec.logical_record_id for batch in batches for rec in batch.logical_records]
    assert "lr1" in logical_records
    physical_structures = [
        rec.physical_structure_id for batch in batches for rec in batch.physical_structures
    ]
    assert "ps1" in physical_structures
    question_items = [rec.question_item_id for batch in batches for rec in batch.question_items]
    assert {"qi1", "q1", "qi_var"}.issubset(set(question_items))
    materials = [rec.material_id for batch in batches for rec in batch.other_materials]
    assert "mat1" in materials
    var_groups = [rec.var_group_id for batch in batches for rec in batch.var_groups]
    assert "vg1" in var_groups
    category_groups = [rec.category_group_id for batch in batches for rec in batch.category_groups]
    assert "cg1" in category_groups
    question_grids = [rec.question_grid_id for batch in batches for rec in batch.question_grids]
    assert "qg1" in question_grids
    question_flows = [rec.question_flow_id for batch in batches for rec in batch.question_flows]
    assert "qf1" in question_flows
    samplings = [rec.sampling_id for batch in batches for rec in batch.sampling_procedures]
    assert "sp1" in samplings
    weights = [rec.weight_id for batch in batches for rec in batch.weights]
    assert "wt1" in weights
    representations = [rec.representation_id for batch in batches for rec in batch.representations]
    assert "rep1" in representations
    code_lists = [rec.code_list_id for batch in batches for rec in batch.code_lists]
    assert "cl1" in code_lists
    notes = [rec.note_id for batch in batches for rec in batch.methodology_notes]
    assert "mn1" in notes
    processing_events = [
        rec.processing_event_id for batch in batches for rec in batch.processing_events
    ]
    assert "pe1" in processing_events
    software = [rec.software_id for batch in batches for rec in batch.software]
    assert "sw1" in software
    access_conditions = [
        rec.access_condition_id for batch in batches for rec in batch.access_conditions
    ]
    assert "ac1" in access_conditions


def test_parse_ddi_batches_strips_dataset_ids(sample_ddi: Path) -> None:
    batches = list(parse_ddi_batches(sample_ddi, "  ds  ", "Dataset", chunk_size=3))

    assert batches
    assert all(batch.dataset.id == "ds" for batch in batches)


def test_question_items_preserve_relationships(sample_ddi: Path) -> None:
    batches = list(parse_ddi_batches(sample_ddi, "ds", "Dataset", chunk_size=10))
    all_items = [rec for batch in batches for rec in batch.question_items]
    item_ids = [rec.question_item_id for rec in all_items]

    assert len(item_ids) == len(set(item_ids))

    items_by_id = {rec.question_item_id: rec for rec in all_items}
    assert items_by_id["qi_var"].variable_id == "v2"
    assert items_by_id["q1"].parent_grid_id == "qg1"

    questions = [q.question_id for batch in batches for q in batch.questions]
    assert "q1" in questions
    assert "q1" in items_by_id


def test_question_items_count_in_demo_dataset() -> None:
    demo_path = Path(__file__).resolve().parents[1] / "demo" / "Ireland_LFS_Series.xml"
    # Demo data lives in Git LFS; CI checkout does not fetch LFS objects
    # (and should not -- it would burn the bandwidth quota the LFS move
    # was meant to save). When the file is an unmaterialised pointer or
    # absent, skip: this assertion is a demo-data smoke check, not a
    # unit test (those use tests/fixtures/).
    if not demo_path.exists() or demo_path.read_bytes()[:40].startswith(
        b"version https://git-lfs.github.com/spec"
    ):
        pytest.skip("demo/Ireland_LFS_Series.xml not materialised (Git LFS pointer)")
    stream = DDIBatchStream(demo_path, "demo", "Demo dataset", chunk_size=200)

    batches = list(stream)
    total_question_items = sum(len(batch.question_items) for batch in batches)

    assert total_question_items > 0
    assert stream.totals["question_items"] == total_question_items


def test_instrument_control_construct_relationship(tmp_path: Path) -> None:
    xml = tmp_path / "instrument_construct.xml"
    xml.write_text(
        """
        <codeBook>
            <stdyDscr ID="s1">
                <citation><titlStmt><titl>Study</titl></titlStmt></citation>
            </stdyDscr>
            <instrument ID="instr1">
                <ControlConstructReference>
                    <ID>seq1</ID>
                </ControlConstructReference>
            </instrument>
            <sequence ID="seq1">
                <labl>Primary sequence</labl>
            </sequence>
        </codeBook>
        """
    )

    batches = list(parse_ddi_batches(xml, "ds", "Dataset", chunk_size=5))

    assert batches
    batch = batches[0]

    assert batch.instruments[0].referenced_construct_id == "seq1"
    assert batch.control_constructs[0].construct_id == "seq1"

    graph = DDIIngestGraph.from_ddi_batch(batch)
    relationships = list(graph.relationships())

    assert any(
        rel.type == "USES_CONSTRUCT"
        and rel.start.label == "CollectionInstrument"
        and rel.start.identity.get("instrument_id") == "instr1"
        and rel.end.label == "ControlConstruct"
        and rel.end.identity.get("construct_id") == "seq1"
        for rel in relationships
    )


def test_reusable_fragment_metadata() -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "reusable_fragments.xml"

    batches = list(parse_ddi_batches(fixture, "frag-ds", "Fragment dataset", chunk_size=50))

    assert len(batches) == 1
    batch = batches[0]

    study = batch.studies[0]
    assert study.study_id == "study-reuse"
    assert study.reusable_id == "study-reuse"
    assert study.label == "Reusable Study Title"
    assert study.description == "Reusable study abstract"

    code_scheme = batch.code_schemes[0]
    assert code_scheme.code_scheme_id == "scheme1"
    assert code_scheme.reusable_id == "scheme-reuse"
    assert code_scheme.reusable_version == "2.0"
    assert code_scheme.reusable_agency == "ACME"
    assert code_scheme.reusable_urn == "urn:ddi:scheme:1"

    category = batch.categories[0]
    assert category.category_id == "cat1"
    assert category.reusable_id == "cat-reuse"
    assert category.code == "10"
    assert category.label == "Category label"

    variable = batch.variables[0]
    assert variable.variable_id == "var-reuse"
    assert variable.reusable_id == "var-reuse"
    assert variable.category_ids == ["cat1"]
    assert variable.concept == "Category label"

    series = batch.series_list[0]
    assert series.series_id == "series1"
    assert series.reusable_id == "series-reuse"
    assert series.label == "Series label"
    assert series.description == "Series description"

    group = batch.groups[0]
    assert group.group_id == "group1"
    assert group.reusable_id == "group-reuse"
    assert group.reusable_version == "0.9"

    question_item = batch.question_items[0]
    assert question_item.question_item_id == "qi1"
    assert question_item.reusable_id == "qi-reuse"
    assert question_item.text == "Question text"

    question_grid = batch.question_grids[0]
    assert question_grid.question_grid_id == "qg1"
    assert question_grid.reusable_id == "qg-reuse"
    assert question_grid.text == "Grid text"

    code_list = batch.code_lists[0]
    assert code_list.code_list_id == "cl1"
    assert code_list.reusable_id == "cl-reuse"
    assert code_list.label == "Code list label"

    representation = batch.representations[0]
    assert representation.representation_id == "rep1"
    assert representation.reusable_id == "rep-reuse"
    assert representation.label == "Representation label"

    graph = DDIIngestGraph.from_ddi_batch(batch)
    nodes = list(graph.nodes())

    def find_node(label: str, identity_key: str, identity_value: str) -> dict[str, object]:
        for node in nodes:
            if node.label == label and node.identity.get(identity_key) == identity_value:
                return node.properties
        raise AssertionError(f"Node {label} with {identity_key}={identity_value} not found")

    category_props = find_node("Category", "category_id", "cat1")
    assert category_props["reusable_id"] == "cat-reuse"
    assert category_props["code"] == "10"
    assert category_props["reusable_agency"] == "ACME"

    series_props = find_node("Series", "series_id", "series1")
    assert series_props["reusable_version"] == "1.2"
    assert series_props["description"] == "Series description"

    variable_props = find_node("Variable", "variable_id", "var-reuse")
    assert variable_props["reusable_id"] == "var-reuse"
    assert variable_props["concept"] == "Category label"

    question_props = find_node("QuestionItem", "question_item_id", "qi1")
    assert question_props["reusable_id"] == "qi-reuse"
    assert question_props["text"] == "Question text"

    code_list_props = find_node("CodeList", "code_list_id", "cl1")
    assert code_list_props["reusable_urn"] == "urn:ddi:cl:1"
    assert code_list_props["label"] == "Code list label"

    representation_props = find_node("Representation", "representation_id", "rep1")
    assert representation_props["reusable_id"] == "rep-reuse"
    assert representation_props["label"] == "Representation label"


def test_lifecycle_tags_are_handled(lifecycle_ddi: Path) -> None:
    stream = DDIBatchStream(lifecycle_ddi, "lifecycle", None, 10)
    batches = list(stream)
    totals = stream.totals

    assert totals["code_schemes"] == 1
    assert totals["categories"] == 1
    assert totals["universes"] == 1
    assert totals["concepts"] == 1
    assert totals["category_groups"] == 1
    assert totals["var_groups"] == 1
    assert totals["question_grids"] == 1
    assert totals["question_items"] == 3
    assert totals["question_flows"] == 1
    assert totals["sampling_procedures"] == 1
    assert totals["weights"] == 1
    assert totals["other_materials"] == 1
    assert totals["representations"] == 1
    assert totals["code_lists"] == 1
    assert totals["methodology_notes"] == 1
    assert totals["processing_events"] == 1
    assert totals["software"] == 1
    assert totals["access_conditions"] == 1
    assert totals["citations"] == 1
    assert totals["funding"] == 1
    assert totals["contributor_roles"] == 1
    assert totals["organizations"] == 1
    assert totals.get("series_list") == 1
    assert totals["groups"] == 1
    assert totals["logical_records"] == 1
    assert totals["physical_structures"] == 1
    assert totals["represented_variables"] == 1
    assert totals["control_constructs"] == 3

    question_items = {
        rec.question_item_id: rec for batch in batches for rec in batch.question_items
    }
    assert question_items["qi_child"].parent_grid_id == "qgL"
    assert question_items["qi_flow"].parent_flow_id == "qfL"

    universes = [rec.universe_id for batch in batches for rec in batch.universes]
    assert universes == ["uL"]

    concepts = [rec.name for batch in batches for rec in batch.concepts]
    assert concepts == ["conceptL"]

    categories = [rec.category_id for batch in batches for rec in batch.categories]
    assert categories == ["cL"]

    constructs = {rec.construct_id: rec for batch in batches for rec in batch.control_constructs}
    assert constructs["seqL"].construct_type == "Sequence"
    assert constructs["loopL"].construct_type == "Loop"
    assert constructs["stmtL"].construct_type == "StatementItem"


def test_parse_ddi_variables_assigns_surrogate_ids(tmp_path: Path) -> None:
    xml = tmp_path / "missing_id.xml"
    xml.write_text(
        """
        <codeBook>
            <dataDscr>
                <var>
                    <labl>No ID</labl>
                </var>
                <var ID="v1">
                    <labl>Has ID</labl>
                </var>
            </dataDscr>
        </codeBook>
        """,
        encoding="utf-8",
    )

    batches = list(parse_ddi_variables(xml, "ds", "Dataset", chunk_size=10))
    all_variables = [var for batch in batches for var in batch]

    assert all_variables[0].variable_id == "ds:var_1"
    assert all_variables[1].variable_id == "v1"


def test_parse_ddi_variables_rejects_duplicate_ids(tmp_path: Path) -> None:
    xml = tmp_path / "duplicate_id.xml"
    xml.write_text(
        """
        <codeBook>
            <dataDscr>
                <var ID="dup"><labl>First</labl></var>
                <var ID="dup"><labl>Second</labl></var>
            </dataDscr>
        </codeBook>
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate variable ID 'dup'"):
        list(parse_ddi_variables(xml, "ds", "Dataset", chunk_size=10))


def test_parse_ddi_batches_strict_mode_raises(tmp_path: Path) -> None:
    xml = tmp_path / "malformed.xml"
    xml.write_text('<codeBook><dataDscr><var ID="v1"><labl>Open', encoding="utf-8")

    with pytest.raises(etree.XMLSyntaxError):
        list(
            parse_ddi_batches(
                xml,
                "ds",
                "Dataset",
                chunk_size=5,
                recover=False,
            )
        )


def test_parse_ddi_batches_recovery_logs_and_metrics(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    xml = tmp_path / "recoverable.xml"
    xml.write_text(
        """
        <codeBook>
            <dataDscr>
                <var ID="v1"><labl>Broken
                <var ID="v2"><labl>Valid</labl></var>
            </dataDscr>
        </codeBook>
        """,
        encoding="utf-8",
    )
    metrics = RecordingMetrics()

    with caplog.at_level(logging.WARNING):
        batches = list(
            parse_ddi_batches(
                xml,
                "ds",
                "Dataset",
                chunk_size=5,
                recover=True,
                metrics=metrics,
            )
        )

    parse_error_counts = [value for name, value in metrics.counts if name == "ingest.parse_errors"]
    assert parse_error_counts and parse_error_counts[0] >= 1
    assert "Recovered DDI XML parse error" in caplog.text
    merged_variables = [v.variable_id for batch in batches for v in batch.variables]
    assert "v2" in merged_variables


def test_parse_ddi_batches_rejects_blank_dataset_id(sample_ddi: Path) -> None:
    with pytest.raises(ValueError, match="dataset_id must be a non-empty string"):
        list(parse_ddi_batches(sample_ddi, "   ", "Dataset", chunk_size=3))


def test_loader_writes_batches(sample_ddi: Path) -> None:
    driver = FakeDriver()
    loader = DDILoader(cast(AsyncDriver, driver), settings=Settings(chunk_size=50, queue_maxsize=1))

    asyncio.run(loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo"))

    assert len(driver.recorder) >= 1
    dataset_params = driver.recorder[0]["parameters"]
    assert dataset_params["dataset"]["id"] == "ds1"

    parameters_by_key: dict[str, list[dict[str, object]]] = {}
    for record in driver.recorder:
        params = record["parameters"] or {}
        for key in (
            "studies",
            "data_files",
            "organizations",
            "series_list",
            "groups",
            "data_collection_events",
            "question_items",
            "logical_records",
            "physical_structures",
            "other_materials",
            "var_groups",
            "category_groups",
            "question_grids",
            "question_flows",
            "sampling_procedures",
            "weights",
            "representations",
            "code_lists",
            "methodology_notes",
            "processing_events",
            "software",
            "access_conditions",
            "variables",
        ):
            if key in params:
                parameters_by_key[key] = params[key]

    assert parameters_by_key["studies"][0]["title"] == "Demo Study"
    assert parameters_by_key["data_files"][0]["file_id"] == "f1"
    assert parameters_by_key["organizations"][0]["organization_id"] == "org1"
    assert parameters_by_key["series_list"][0]["series_id"] == "series1"
    assert parameters_by_key["groups"][0]["group_id"] == "grp1"
    assert parameters_by_key["data_collection_events"][0]["event_id"] == "dc1"
    question_items = {
        item["question_item_id"]: item for item in parameters_by_key["question_items"]
    }
    assert set(question_items) == {"qi1", "q1", "qi_var"}
    assert question_items["qi_var"]["variable_id"] == "v2"
    assert question_items["q1"]["parent_grid_id"] == "qg1"
    assert parameters_by_key["logical_records"][0]["logical_record_id"] == "lr1"
    assert parameters_by_key["physical_structures"][0]["physical_structure_id"] == "ps1"
    assert parameters_by_key["other_materials"][0]["material_id"] == "mat1"
    assert parameters_by_key["var_groups"][0]["var_group_id"] == "vg1"
    assert parameters_by_key["category_groups"][0]["category_group_id"] == "cg1"
    assert parameters_by_key["question_grids"][0]["question_grid_id"] == "qg1"
    assert parameters_by_key["question_flows"][0]["question_flow_id"] == "qf1"
    assert parameters_by_key["sampling_procedures"][0]["sampling_id"] == "sp1"
    assert parameters_by_key["weights"][0]["weight_id"] == "wt1"
    assert parameters_by_key["representations"][0]["representation_id"] == "rep1"
    assert parameters_by_key["code_lists"][0]["code_list_id"] == "cl1"
    assert parameters_by_key["methodology_notes"][0]["note_id"] == "mn1"
    assert parameters_by_key["processing_events"][0]["processing_event_id"] == "pe1"
    assert parameters_by_key["software"][0]["software_id"] == "sw1"
    assert parameters_by_key["access_conditions"][0]["access_condition_id"] == "ac1"
    variable_rows = parameters_by_key["variables"]
    assert {row["variable_id"] for row in variable_rows} == {"v1", "v2", "v3"}
    queries = [record["query"] for record in driver.recorder]
    assert any("Category" in query for query in queries)
    assert any("QuestionItem" in query for query in queries)
    assert any("USES_QUESTION_ITEM" in query for query in queries)
    assert any("HAS_ITEM" in query for query in queries)
    assert any("PART_OF" in query for query in queries)


def test_loader_applies_timeouts() -> None:
    driver = FakeDriver()
    settings = Settings(
        session_timeout=12.5,
        transaction_timeout=3.5,
        chunk_size=1,
        queue_maxsize=1,
    )
    loader = DDILoader(cast(AsyncDriver, driver), settings=settings)
    batch = minimal_batch()

    asyncio.run(loader._write_batch(batch))

    assert driver.recorder
    record = driver.recorder[0]
    assert record["session_config"]["session_timeout"] == settings.session_timeout
    assert record["transaction_config"]["timeout"] == settings.transaction_timeout


def test_loader_retries_transient_errors(caplog: pytest.LogCaptureFixture) -> None:
    adapter = FlakyAdapter(fail_times=2)
    metrics = RecordingMetrics()
    settings = Settings(
        write_retry_attempts=3,
        write_retry_base_delay=0.0,
        write_retry_jitter=0.0,
        chunk_size=1,
        queue_maxsize=1,
    )
    loader = DDILoader(
        cast(AsyncDriver, FakeDriver()),
        settings=settings,
        metrics=metrics,
        adapter=cast(GraphWriteAdapter, adapter),
    )

    with caplog.at_level(logging.WARNING):
        asyncio.run(loader._write_batch(minimal_batch()))

    assert adapter.calls == 3
    assert adapter.graphs
    retry_count = sum(
        value for name, value in metrics.counts if name == "ingest.batch_write_retries"
    )
    assert retry_count == 2
    assert "Retrying batch write after transient error" in caplog.text


def test_loader_bubbles_up_after_exhausting_retries(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = FlakyAdapter(fail_times=5)
    metrics = RecordingMetrics()
    settings = Settings(
        write_retry_attempts=2,
        write_retry_base_delay=0.0,
        write_retry_jitter=0.0,
        chunk_size=1,
        queue_maxsize=1,
    )
    loader = DDILoader(
        cast(AsyncDriver, FakeDriver()),
        settings=settings,
        metrics=metrics,
        adapter=cast(GraphWriteAdapter, adapter),
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(TransientError):
            asyncio.run(loader._write_batch(minimal_batch()))

    retry_count = sum(
        value for name, value in metrics.counts if name == "ingest.batch_write_retries"
    )
    assert retry_count == 1
    assert "Batch write failed after retries" in caplog.text


def test_loader_rejects_blank_dataset_id(sample_ddi: Path) -> None:
    loader = DDILoader(cast(AsyncDriver, FakeDriver()), settings=Settings(chunk_size=10))

    with pytest.raises(ValueError, match="dataset_id must be a non-empty string"):
        asyncio.run(loader.load(sample_ddi, dataset_id="   "))


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    driver = FakeDriver()
    loader = DDILoader(cast(AsyncDriver, driver))

    with pytest.raises(ValueError, match="DDI XML path must reference a readable file"):
        asyncio.run(loader.load(tmp_path / "missing.xml", dataset_id="ds1"))


def test_loader_rejects_unreadable_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    driver = FakeDriver()
    loader = DDILoader(cast(AsyncDriver, driver))
    unreadable = tmp_path / "unreadable.xml"
    unreadable.write_text("<codeBook />")
    unreadable.chmod(0)

    monkeypatch.setattr(os, "access", lambda path, mode: False)

    try:
        with pytest.raises(ValueError, match="DDI XML path must reference a readable file"):
            asyncio.run(loader.load(unreadable, dataset_id="ds1"))
    finally:
        unreadable.chmod(0o644)


def test_loader_handles_multiple_consumers(sample_ddi: Path) -> None:
    driver = FakeDriver()
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=Settings(chunk_size=1, queue_maxsize=1, writer_concurrency=3),
    )

    asyncio.run(loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo"))

    # With separate queries, each entity type has its own query
    # Find all variable queries by looking for "variables" key in parameters
    variable_ids = []
    for row in driver.recorder:
        params = row.get("parameters", {})
        if params.get("variables"):
            for vid in params["variables"]:
                variable_ids.append(vid["variable_id"])

    assert sorted(variable_ids) == ["v1", "v2", "v3"]
    # Multiple queries: dataset + entity queries per chunk
    assert len(driver.recorder) >= 3


def test_loader_emits_batch_metrics(sample_ddi: Path) -> None:
    driver = FakeDriver()
    metrics = RecordingMetrics()
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=Settings(chunk_size=3, queue_maxsize=1, writer_concurrency=1, batch_metrics=True),
        metrics=metrics,
    )

    asyncio.run(loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo"))

    assert len(metrics.counts) >= 2
    observed = {name for name, _ in metrics.observations}
    assert {"ingest.batch_duration_seconds", "ingest.batch_size"}.issubset(observed)


def test_loader_honors_queue_maxsize_and_batch_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xml = write_simple_ddi(tmp_path, ["v1", "v2", "v3"], "tiny.xml")
    settings = Settings(chunk_size=1, queue_maxsize=1, writer_concurrency=1)

    class RecordingAdapter:
        def __init__(self) -> None:
            self.batch_variable_ids: list[list[str]] = []

        async def write_batch(
            self,
            graph: Any,
            *,
            session_config: dict[str, Any] | None = None,
            transaction_config: dict[str, Any] | None = None,
        ) -> None:
            self.batch_variable_ids.append([var.variable_id for var in graph.variables])

    adapter = RecordingAdapter()
    loader = DDILoader(
        cast(AsyncDriver, FakeDriver()),
        settings=settings,
        adapter=cast(GraphWriteAdapter, adapter),
    )

    queue_holder: dict[str, asyncio.Queue[DDIBatch | None]] = {}

    class RecordingQueue(asyncio.Queue[DDIBatch | None]):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.max_observed = 0
            self.put_waits = 0
            self.blocked_event = asyncio.Event()
            self.allow_get = asyncio.Event()
            queue_holder["queue"] = self

        async def put(self, item: DDIBatch | None) -> None:
            if self.full():
                self.put_waits += 1
                self.blocked_event.set()
            await super().put(item)
            self.max_observed = max(self.max_observed, self.qsize())

        async def get(self) -> DDIBatch | None:
            if not self.allow_get.is_set():
                await self.allow_get.wait()
            return await super().get()

    monkeypatch.setattr("ddigraph.ingest.loader.asyncio.Queue", RecordingQueue)

    async def run_loader() -> None:
        task = asyncio.create_task(
            loader.load(xml, dataset_id="ds-queue", dataset_name="Tiny dataset")
        )
        try:
            while "queue" not in queue_holder:
                await asyncio.sleep(0)
            queue = cast(RecordingQueue, queue_holder["queue"])
            await asyncio.wait_for(queue.blocked_event.wait(), timeout=1)
            queue.allow_get.set()
            await task
        finally:
            cleanup_queue = cast(RecordingQueue | None, queue_holder.get("queue"))
            if cleanup_queue is not None:
                cleanup_queue.allow_get.set()
            if not task.done():
                await task

    asyncio.run(run_loader())

    queue = cast(RecordingQueue, queue_holder["queue"])
    assert queue.put_waits >= 1
    assert queue.max_observed <= settings.queue_maxsize
    # Ignore trailing batches that only carry generic identifiable records
    # (e.g. the ``dataDscr`` wrapper captured as a generic identifiable):
    # they have no variables, so filtering preserves the intent of the test.
    variable_batches = [b for b in adapter.batch_variable_ids if b]
    assert variable_batches == [["v1"], ["v2"], ["v3"]]
    written_ids = [var_id for batch in variable_batches for var_id in batch]
    assert written_ids == ["v1", "v2", "v3"]


def test_loader_blocks_producer_when_queue_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xml = write_simple_ddi(tmp_path, ["v1", "v2", "v3"], "blocking.xml")
    settings = Settings(chunk_size=1, queue_maxsize=1, writer_concurrency=1)

    class SlowAdapter:
        def __init__(self) -> None:
            self.batch_variable_ids: list[list[str]] = []

        async def write_batch(
            self,
            graph: Any,
            *,
            session_config: dict[str, Any] | None = None,
            transaction_config: dict[str, Any] | None = None,
        ) -> None:
            await asyncio.sleep(0.05)
            self.batch_variable_ids.append([var.variable_id for var in graph.variables])

    adapter = SlowAdapter()
    loader = DDILoader(
        cast(AsyncDriver, FakeDriver()),
        settings=settings,
        adapter=cast(GraphWriteAdapter, adapter),
    )

    queue_holder: dict[str, asyncio.Queue[DDIBatch | None]] = {}

    class BlockingQueue(asyncio.Queue[DDIBatch | None]):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.max_observed = 0
            self.blocked_durations: list[float] = []
            self.blocked_event = asyncio.Event()
            self.allow_get = asyncio.Event()
            queue_holder["queue"] = self

        async def put(self, item: DDIBatch | None) -> None:
            start: float | None = None
            if self.full():
                start = asyncio.get_running_loop().time()
                self.blocked_event.set()
            await super().put(item)
            if start is not None:
                self.blocked_durations.append(asyncio.get_running_loop().time() - start)
            self.max_observed = max(self.max_observed, self.qsize())

        async def get(self) -> DDIBatch | None:
            if not self.allow_get.is_set():
                await self.allow_get.wait()
            return await super().get()

    monkeypatch.setattr("ddigraph.ingest.loader.asyncio.Queue", BlockingQueue)

    async def run_loader() -> None:
        task = asyncio.create_task(
            loader.load(xml, dataset_id="ds-block", dataset_name="Blocking dataset")
        )
        try:
            while "queue" not in queue_holder:
                await asyncio.sleep(0)
            queue = cast(BlockingQueue, queue_holder["queue"])
            await asyncio.wait_for(queue.blocked_event.wait(), timeout=1)
            await asyncio.sleep(0.05)
            queue.allow_get.set()
            await task
        finally:
            cleanup_queue = cast(BlockingQueue | None, queue_holder.get("queue"))
            if cleanup_queue is not None:
                cleanup_queue.allow_get.set()
            if not task.done():
                await task

    asyncio.run(run_loader())

    queue = cast(BlockingQueue, queue_holder["queue"])
    assert queue.blocked_durations
    assert any(duration >= 0.02 for duration in queue.blocked_durations)
    assert queue.max_observed <= settings.queue_maxsize
    variable_batches = [b for b in adapter.batch_variable_ids if b]
    assert variable_batches == [["v1"], ["v2"], ["v3"]]
    written_ids = [var_id for batch in variable_batches for var_id in batch]
    assert written_ids == ["v1", "v2", "v3"]


def test_loader_reports_totals(sample_ddi: Path, caplog: pytest.LogCaptureFixture) -> None:
    driver = FakeDriver()
    metrics = RecordingMetrics()
    settings = Settings(chunk_size=2, queue_maxsize=1, writer_concurrency=1)
    expected_stream = parse_ddi_batches(sample_ddi, "ds1", "Demo", chunk_size=settings.chunk_size)
    list(expected_stream)
    expected_totals = cast(dict[str, int], getattr(expected_stream, "totals", {}))

    loader = DDILoader(cast(AsyncDriver, driver), settings=settings, metrics=metrics)

    with caplog.at_level(logging.INFO):
        asyncio.run(loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo"))

    totals_counts: dict[str, int] = defaultdict(int)
    for name, value in metrics.counts:
        totals_counts[name] += value

    for key in ("variables", "questions", "data_files", "batches"):
        metric_name = f"ingest.total.{key}"
        assert totals_counts[metric_name] == expected_totals[key]

    finish_records = [
        rec for rec in caplog.records if rec.message.startswith("DDI ingestion finished")
    ]
    assert finish_records
    assert str(expected_totals) in finish_records[-1].message


def test_loader_dry_run_reports_metrics_without_writes(
    sample_ddi: Path, caplog: pytest.LogCaptureFixture
) -> None:
    driver = FakeDriver()
    metrics = RecordingMetrics()
    settings = Settings(
        chunk_size=2,
        queue_maxsize=1,
        writer_concurrency=2,
        batch_metrics=True,
        dry_run=True,
    )

    expected_stream = parse_ddi_batches(sample_ddi, "ds1", "Demo", chunk_size=settings.chunk_size)
    list(expected_stream)
    expected_totals = cast(dict[str, int], getattr(expected_stream, "totals", {}))

    loader = DDILoader(cast(AsyncDriver, driver), settings=settings, metrics=metrics)

    with caplog.at_level(logging.INFO):
        totals = asyncio.run(loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo"))

    assert driver.recorder == []
    assert totals == expected_totals
    assert any(DRY_RUN_MESSAGE in rec.message for rec in caplog.records)

    totals_counts: defaultdict[str, int] = defaultdict(int)
    for name, value in metrics.counts:
        totals_counts[name] += value

    assert totals_counts["ingest.total.batches"] == expected_totals["batches"]
    assert totals_counts["ingest.total.variables"] == expected_totals["variables"]
    assert any(name == "ingest.batches" for name, _ in metrics.counts)
    assert {name for name, _ in metrics.observations} >= {
        "ingest.batch_duration_seconds",
        "ingest.batch_size",
    }


def test_loader_cleans_up_on_producer_error(
    monkeypatch: pytest.MonkeyPatch, sample_ddi: Path
) -> None:
    driver = FakeDriver()
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=Settings(queue_maxsize=1, writer_concurrency=2),
    )

    def explode(*args: Any, **kwargs: Any) -> list[DDIBatch]:  # pragma: no cover - used in test
        raise ValueError("boom")

    monkeypatch.setattr("ddigraph.ingest.loader.parse_ddi_batches", explode)

    async def run_loader() -> None:
        with pytest.raises(ValueError, match="boom"):
            await loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo")

        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        assert not pending

    asyncio.run(run_loader())


def test_loader_surfaces_consumer_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, sample_ddi: Path
) -> None:
    driver = FakeDriver()
    metrics = RecordingMetrics()
    loader = DDILoader(
        cast(AsyncDriver, driver),
        settings=Settings(queue_maxsize=1, writer_concurrency=2),
        metrics=metrics,
    )

    async def explode(batch: DDIBatch) -> None:  # pragma: no cover - used in test
        raise RuntimeError("write exploded")

    monkeypatch.setattr(loader, "_write_batch", explode)

    async def run_loader() -> None:
        with caplog.at_level(logging.ERROR):
            with pytest.raises(RuntimeError, match="write exploded"):
                await loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo")

        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task() and not task.done()
        ]
        assert not pending

    asyncio.run(run_loader())

    assert ("ingest.failures", 1) in metrics.counts
    assert "DDI ingestion failed" in caplog.text


def test_loader_offloads_parsing(monkeypatch: pytest.MonkeyPatch, sample_ddi: Path) -> None:
    driver = FakeDriver()
    metrics = RecordingMetrics()
    settings = Settings(chunk_size=1, queue_maxsize=1, writer_concurrency=1)
    loader = DDILoader(cast(AsyncDriver, driver), settings=settings, metrics=metrics)

    write_times: list[float] = []

    async def recording_write(batch: DDIBatch) -> None:
        write_times.append(asyncio.get_running_loop().time())
        await asyncio.sleep(0.01)

    monkeypatch.setattr(loader, "_write_batch", recording_write)

    original_parse = parse_ddi_batches

    class SlowBatches:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.stream = original_parse(*args, **kwargs)
            self.totals = getattr(self.stream, "totals", {})

        def __iter__(self) -> Iterable[DDIBatch]:  # pragma: no cover - used in test
            for batch in self.stream:
                time.sleep(0.05)
                yield batch

    monkeypatch.setattr("ddigraph.ingest.loader.parse_ddi_batches", SlowBatches)

    async def run_loader() -> tuple[float, int]:
        tick_count = 0
        done = asyncio.Event()

        async def ticker() -> None:
            nonlocal tick_count
            while not done.is_set():
                await asyncio.sleep(0.01)
                tick_count += 1

        ticker_task = asyncio.create_task(ticker())
        start = asyncio.get_running_loop().time()
        await loader.load(sample_ddi, dataset_id="ds1", dataset_name="Demo")
        done.set()
        await ticker_task
        return start, tick_count

    start, tick_count = asyncio.run(run_loader())

    assert tick_count >= 5
    assert write_times
    assert min(write_times) - start < 0.15


def test_loader_merge_mode_preserves_existing_data(tmp_path: Path) -> None:
    adapter = PurgeRecordingAdapter()
    loader = DDILoader(
        cast(AsyncDriver, FakeDriver()),
        settings=Settings(chunk_size=2),
        adapter=adapter,
    )

    first_xml = write_simple_ddi(tmp_path, ["v1"], "first.xml")
    second_xml = write_simple_ddi(tmp_path, ["v2"], "second.xml")

    asyncio.run(loader.load(first_xml, dataset_id="ds1", dataset_name="Dataset"))
    asyncio.run(loader.load(second_xml, dataset_id="ds1", dataset_name="Dataset"))

    assert adapter.store["ds1"] == {"v1", "v2"}
    assert ("purge", "ds1") not in adapter.events


def test_loader_replace_mode_purges_before_writing(tmp_path: Path) -> None:
    adapter = PurgeRecordingAdapter()
    loader = DDILoader(
        cast(AsyncDriver, FakeDriver()),
        settings=Settings(chunk_size=2),
        adapter=adapter,
    )

    first_xml = write_simple_ddi(tmp_path, ["old_var"], "first.xml")
    second_xml = write_simple_ddi(tmp_path, ["new_var"], "second.xml")

    asyncio.run(loader.load(first_xml, dataset_id="ds1", dataset_name="Dataset"))
    asyncio.run(
        loader.load(
            second_xml,
            dataset_id="ds1",
            dataset_name="Dataset",
            replace=True,
        )
    )

    assert adapter.store["ds1"] == {"new_var"}
    assert adapter.events == [
        ("write", ["old_var"]),
        ("purge", "ds1"),
        ("write", ["new_var"]),
    ]

from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest
from neo4j import AsyncDriver

from ddigraph.config import Settings
from ddigraph.ingest.loader import DatasetRecord, GenericIdentifiableRecord
from ddigraph.schema.ddi_graph import DDIIngestGraph
from ddigraph.schema.neo4j_adapter import Neo4jGraphAdapter


def make_graph(dataset_id: str = "ds1") -> DDIIngestGraph:
    dataset = DatasetRecord(dataset_id, None)
    return DDIIngestGraph(
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
        ncubes=[],
        ncube_groups=[],
        document_descriptions=[],
        sample_frames=[],
        quality_statements=[],
        study_authorizations=[],
        study_developments=[],
        ex_post_evaluations=[],
        generic_identifiables=[],
    )


class FakeTx:
    def __init__(self) -> None:
        self.run_calls = 0
        self.parameters: dict[str, Any] | None = None
        self.history: list[tuple[str, dict[str, Any]]] = []

    class _Result:
        @staticmethod
        def consume() -> None:  # pragma: no cover - trivial
            return None

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeTx._Result:
        self.run_calls += 1
        self.parameters = parameters or {}
        self.history.append((query, parameters or {}))
        return FakeTx._Result()


class FakeSession:
    def __init__(self, tx: FakeTx, session_config: dict[str, Any]) -> None:
        self.tx = tx
        self.session_config = session_config

    def __enter__(self) -> FakeSession:  # pragma: no cover - trivial
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: BaseException | None,
    ) -> None:  # pragma: no cover - trivial
        return None

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: BaseException | None,
    ) -> None:
        return None

    def execute_write(self, fn: Any, **config: Any) -> None:
        result = fn(self.tx)
        if asyncio.iscoroutine(result):
            asyncio.get_event_loop().run_until_complete(result)


class FakeDriver:
    def __init__(self) -> None:
        self.tx = FakeTx()

    def session(self, database: str | None = None, **config: Any) -> FakeSession:
        session_config: dict[str, Any] = {"database": database}
        session_config.update(config)
        return FakeSession(self.tx, session_config)


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
        tb: BaseException | None,
    ) -> None:
        return None

    async def execute_write(self, fn: Any, **config: Any) -> None:
        result = fn(self.tx)
        if asyncio.iscoroutine(result):
            await result


class AwaitingRunDriver:
    def __init__(self) -> None:
        self.tx = AwaitingRunTx()

    def session(self, database: str | None = None, **config: Any) -> AwaitingRunSession:
        session_config: dict[str, Any] = {"database": database}
        session_config.update(config)
        return AwaitingRunSession(self.tx, session_config)


@pytest.mark.asyncio
async def test_write_batch_handles_sync_run_returning_none() -> None:
    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(cast(AsyncDriver, driver), settings=Settings())

    await adapter.write_batch(make_graph())

    assert driver.tx.run_calls == 1
    assert driver.tx.parameters is not None
    assert driver.tx.parameters["dataset"]["id"] == "ds1"


@pytest.mark.asyncio
async def test_write_batch_handles_awaitable_run_and_consume() -> None:
    driver = AwaitingRunDriver()
    adapter = Neo4jGraphAdapter(cast(AsyncDriver, driver), settings=Settings())

    await adapter.write_batch(make_graph())

    assert driver.tx.run_calls == 1
    assert driver.tx.consumed_results == 1
    assert driver.tx.parameters is not None
    assert driver.tx.parameters["dataset"]["id"] == "ds1"


@pytest.mark.asyncio
async def test_write_batch_emits_cypher_for_generic_identifiables() -> None:
    """Generic-only graphs must still emit the DDIGenericIdentifiable write.

    A graph that carries only generic_identifiables must actually run
    the DDIGenericIdentifiable Cypher write -- not silently degrade to
    a dataset-only write.
    """

    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(cast(AsyncDriver, driver), settings=Settings())

    graph = make_graph()
    graph.generic_identifiables.append(
        GenericIdentifiableRecord(
            dataset_id="ds1",
            dataset_name=None,
            identifiable_id="gi-1",
            element_tag="exPostEvaluation",
            description="hi",
        )
    )

    await adapter.write_batch(graph)

    generic_runs = [(q, params) for q, params in driver.tx.history if "DDIGenericIdentifiable" in q]
    assert generic_runs, "DDIGenericIdentifiable Cypher was not executed"
    _, params = generic_runs[0]
    rows = params["generic_identifiables"]
    assert len(rows) == 1
    assert rows[0]["identifiable_id"] == "gi-1"
    assert rows[0]["element_tag"] == "exPostEvaluation"


@pytest.mark.asyncio
async def test_purge_handles_sync_session() -> None:
    driver = FakeDriver()
    adapter = Neo4jGraphAdapter(cast(AsyncDriver, driver), settings=Settings())

    await adapter.purge_dataset("ds1")

    assert driver.tx.run_calls == 1
    assert driver.tx.parameters == {"dataset_id": "ds1"}


@pytest.mark.asyncio
async def test_purge_handles_async_session() -> None:
    driver = AwaitingRunDriver()
    adapter = Neo4jGraphAdapter(cast(AsyncDriver, driver), settings=Settings())

    await adapter.purge_dataset("ds1")

    assert driver.tx.run_calls == 1
    assert driver.tx.consumed_results == 1
    assert driver.tx.parameters == {"dataset_id": "ds1"}

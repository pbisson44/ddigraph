from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

import pytest
from neo4j import AsyncDriver
from neo4j.exceptions import Forbidden

from ddigraph.graph.bootstrap import bootstrap_queries, ensure_schema

T = TypeVar("T")


class FakeTx:
    def __init__(self, recorder: list[str]) -> None:
        self.recorder = recorder

    def run(self, query: str) -> None:
        self.recorder.append(query)


class FakeSession:
    def __init__(self, recorder: list[str], *, fail: bool = False) -> None:
        self.recorder = recorder
        self.fail = fail

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: BaseException | None,
    ) -> None:
        return None

    async def execute_write(self, fn: Callable[[FakeTx], T | Awaitable[T]]) -> T:
        tx = FakeTx(self.recorder)
        if self.fail:
            raise Forbidden("schema writes not permitted")

        result = fn(tx)
        if asyncio.iscoroutine(result):
            return await cast(Awaitable[T], result)
        return cast(T, result)


class FakeDriver:
    def __init__(self, *, fail: bool = False) -> None:
        self.recorder: list[str] = []
        self.fail = fail

    def session(self, database: str | None = None) -> FakeSession:  # pragma: no cover - trivial
        return FakeSession(self.recorder, fail=self.fail)


def test_ensure_schema_executes_all_bootstrap_queries() -> None:
    driver = FakeDriver()

    asyncio.run(ensure_schema(cast(AsyncDriver, driver)))

    assert driver.recorder == list(bootstrap_queries())


def test_ensure_schema_surfaces_permission_errors() -> None:
    driver = FakeDriver(fail=True)

    with pytest.raises(PermissionError) as excinfo:
        asyncio.run(ensure_schema(cast(AsyncDriver, driver)))

    assert str(excinfo.value) == (
        "Schema bootstrap failed because the Neo4j user lacks permission "
        "to create constraints or indexes. Use a user with the schema "
        "privileges (e.g., `schema_admin` or `admin`), supply the correct "
        "database via DDIGRAPH_NEO4J_DATABASE (legacy compatibility alias: "
        "NEO4DDI_NEO4J_DATABASE; also accepted: NEO4J_DATABASE), or "
        "pre-provision the schema manually before running ddigraph."
    )


def test_bootstrap_queries_cover_all_labels() -> None:
    labels = {
        "Dataset",
        "Variable",
        "Concept",
        "Study",
        "DataFile",
        "Universe",
        "CodeScheme",
        "Category",
        "Question",
        "QuestionItem",
        "QuestionGrid",
        "QuestionFlow",
        "Organization",
        "Series",
        "Group",
        "VarGroup",
        "CategoryGroup",
        "DataCollectionEvent",
        "LogicalRecord",
        "PhysicalStructure",
        "OtherMaterial",
        "SamplingProcedure",
        "Weight",
        "Representation",
        "CodeList",
        "MethodologyNote",
        "ProcessingEvent",
        "Software",
        "AccessCondition",
        "Citation",
        "Coverage",
        "Funding",
        "Contributor",
        "CollectionInstrument",
        "ControlConstruct",
        "RepresentedVariable",
        "Comparison",
        "AccessPolicy",
    }

    queries = list(bootstrap_queries())

    missing = {
        label
        for label in labels
        if not any(f":{label}" in query and "REQUIRE" in query for query in queries)
    }
    assert not missing, f"Missing constraints for: {sorted(missing)}"

    index_labels = {
        "Dataset",
        "Variable",
        "QuestionItem",
        "QuestionGrid",
        "QuestionFlow",
        "VarGroup",
        "CategoryGroup",
        "SamplingProcedure",
        "Weight",
        "Representation",
        "CodeList",
        "MethodologyNote",
        "ProcessingEvent",
        "Software",
        "AccessCondition",
        "Citation",
        "Coverage",
        "Funding",
        "Contributor",
        "CollectionInstrument",
        "ControlConstruct",
        "RepresentedVariable",
        "Comparison",
        "AccessPolicy",
    }

    # Index queries use (n:Label) format
    missing_indexes = {
        label
        for label in index_labels
        if not any(f"(n:{label})" in query and "INDEX" in query for query in queries)
    }

    assert not missing_indexes, f"Missing indexes for: {sorted(missing_indexes)}"

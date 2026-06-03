"""Neo4j implementation of the graph write adapter."""

from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import Any, cast

from neo4j import AsyncDriver, Driver

from ddigraph.config import Settings
from ddigraph.schema.adapter import GraphWriteAdapter
from ddigraph.schema.ddi_graph import DDIIngestGraph


class Neo4jGraphAdapter(GraphWriteAdapter):
    """Generate Cypher for a ``DDIIngestGraph`` and execute it."""

    def __init__(self, driver: Driver | AsyncDriver, settings: Settings) -> None:
        """Initialize the adapter with a Neo4j driver and runtime settings.

        Args:
            driver: Neo4j driver instance used to open sessions. The adapter supports
                both synchronous ``Driver`` and asynchronous ``AsyncDriver`` objects.
            settings: Application settings containing Neo4j write options, including
                target database and chunk size.
        """
        self.driver = driver
        self.settings = settings

    async def write_batch(
        self,
        graph: DDIIngestGraph,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> None:
        """Write a ``DDIIngestGraph`` to Neo4j in chunked transactions.

        The method always exposes an async interface but branches internally based
        on session type:

        * If ``driver.session(...)`` yields an async session, it executes an async
          write callback and awaits query execution/consumption.
        * If it yields a sync session, it executes a sync write callback directly
          within the surrounding async method.

        Args:
            graph: Graph payload to persist. ``graph.as_dict()`` must include a
                ``"dataset"`` object and optional list-valued entity keys expected by
                ``_DDI_CYPHER_QUERIES``.
            session_config: Extra keyword arguments merged into
                ``driver.session(...)`` after the default ``database`` value.
            transaction_config: Extra keyword arguments forwarded to
                ``session.execute_write(...)``.

        Raises:
            neo4j.exceptions.Neo4jError: Propagated when Neo4j query execution fails.
            Exception: Propagates driver/session/transaction errors raised by the
                underlying Neo4j client.
        """
        params = graph.as_dict()
        session_kwargs: dict[str, Any] = {"database": self.settings.neo4j_database}
        session_kwargs.update(session_config or {})
        tx_kwargs = transaction_config or {}

        parameter_sets = _build_chunked_params(params, self.settings.chunk_size)

        def _write(tx: Any) -> None:
            for chunk_params in parameter_sets:
                # First create/update the dataset node
                tx.run(
                    _DATASET_ONLY_CYPHER,
                    parameters={"dataset": chunk_params["dataset"]},
                ).consume()

                # Then run each entity query separately within the same transaction
                # This avoids CALL {} subquery issues with Neo4j 5.x write semantics
                for key, query in _DDI_CYPHER_QUERIES:
                    entity_params = {
                        "dataset": chunk_params["dataset"],
                        key: chunk_params.get(key, []),
                    }
                    # Only run if there are entities of this type
                    if entity_params[key]:
                        tx.run(query, parameters=entity_params).consume()

        async def _write_async(tx: Any) -> None:
            for chunk_params in parameter_sets:
                # First create/update the dataset node
                await _run_and_consume_async(
                    tx,
                    _DATASET_ONLY_CYPHER,
                    {"dataset": chunk_params["dataset"]},
                )

                # Then run each entity query separately
                for key, query in _DDI_CYPHER_QUERIES:
                    entity_params = {
                        "dataset": chunk_params["dataset"],
                        key: chunk_params.get(key, []),
                    }
                    if entity_params[key]:
                        await _run_and_consume_async(tx, query, entity_params)

        session = self.driver.session(**session_kwargs)
        if _is_async_session(session):
            async with cast(Any, session) as async_session:
                result = async_session.execute_write(_write_async, **tx_kwargs)
                if inspect.isawaitable(result):
                    await result
        else:
            with cast(Any, session) as sync_session:
                sync_session.execute_write(_write, **tx_kwargs)

    async def purge_dataset(
        self,
        dataset_id: str,
        *,
        session_config: dict[str, object] | None = None,
        transaction_config: dict[str, object] | None = None,
    ) -> None:
        """Delete all graph content associated with a dataset id.

        The method follows the same sync/async branching as ``write_batch``:

        * For async sessions, it runs an async write callback and awaits results.
        * For sync sessions, it runs a sync callback through ``execute_write``.

        Args:
            dataset_id: Identifier of the dataset whose subgraph should be removed.
            session_config: Extra keyword arguments merged into
                ``driver.session(...)`` after the default ``database`` value.
            transaction_config: Extra keyword arguments forwarded to
                ``session.execute_write(...)``.

        Raises:
            neo4j.exceptions.Neo4jError: Propagated when purge query execution fails.
            Exception: Propagates driver/session/transaction errors raised by the
                underlying Neo4j client.
        """
        params = {"dataset_id": dataset_id}
        session_kwargs: dict[str, Any] = {"database": self.settings.neo4j_database}
        session_kwargs.update(session_config or {})
        tx_kwargs = transaction_config or {}

        def _purge(tx: Any) -> None:
            tx.run(_PURGE_DATASET_CYPHER, parameters=params).consume()

        async def _purge_async(tx: Any) -> None:
            await _run_and_consume_async(tx, _PURGE_DATASET_CYPHER, params)

        session = self.driver.session(**session_kwargs)
        if _is_async_session(session):
            async with cast(Any, session) as async_session:
                result = async_session.execute_write(_purge_async, **tx_kwargs)
                if inspect.isawaitable(result):
                    await result
        else:
            with cast(Any, session) as sync_session:
                sync_session.execute_write(_purge, **tx_kwargs)


def _chunk(items: list[object], size: int) -> Iterable[list[object]]:
    """Yield fixed-size slices from a list.

    Args:
        items: Sequence to split into consecutive chunks.
        size: Maximum number of items per chunk. Must be greater than zero.

    Returns:
        An iterator of list slices preserving original order.
    """
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _build_chunked_params(params: dict[str, Any], chunk_size: int) -> list[dict[str, Any]]:
    """Build per-chunk Cypher parameter dictionaries for batched writes.

    ``params`` is expected to contain:

    * ``"dataset"``: a mapping-like value used in every returned parameter set.
    * Zero or more list-valued keys matching entries in ``_DDI_CYPHER_QUERIES``
      (for example ``"studies"``, ``"organizations"``, etc.).

    Each list-valued entity key is chunked independently. Returned parameter sets
    align by chunk index and fill missing chunks with empty lists.

    Args:
        params: Source parameter dictionary from ``DDIIngestGraph.as_dict()`` with a
            required ``"dataset"`` key and optional list values for entity keys.
        chunk_size: Maximum number of entities from each list to include in one
            chunk.

    Returns:
        A list of dictionaries ready for query execution, where each dictionary has
        ``"dataset"`` and every entity key referenced by ``_DDI_CYPHER_QUERIES``.

    Raises:
        KeyError: If ``params`` does not contain the required ``"dataset"`` key.
    """
    chunked: dict[str, list[list[object]]] = {}
    for key, _ in _DDI_CYPHER_QUERIES:
        values = params.get(key, [])
        chunks = list(_chunk(values, chunk_size)) if values else []
        chunked[key] = chunks or [[]]

    max_chunks = max(len(chunks) for chunks in chunked.values()) if chunked else 1
    parameter_sets: list[dict[str, Any]] = []
    for index in range(max_chunks):
        chunk_params: dict[str, Any] = {"dataset": params["dataset"]}
        for key, chunks in chunked.items():
            chunk_params[key] = chunks[index] if index < len(chunks) else []
        parameter_sets.append(chunk_params)

    return parameter_sets


def _is_async_session(session: Any) -> bool:
    """Return whether a session uses coroutine-based ``execute_write``.

    Args:
        session: Neo4j session object (sync or async) returned from
            ``driver.session(...)``.

    Returns:
        ``True`` when ``session.execute_write`` is a coroutine function (async
        session), otherwise ``False`` (sync session).
    """
    return inspect.iscoroutinefunction(getattr(session, "execute_write", None))


async def _run_and_consume_async(tx: Any, query: str, parameters: dict[str, Any]) -> None:
    """Run a transaction query and fully consume results in async-compatible mode.

    This helper tolerates either sync-like or awaitable return values from
    ``tx.run(...)`` and ``result.consume()`` so it can be reused across Neo4j driver
    variants that expose asynchronous transaction objects.

    Args:
        tx: Transaction object supporting ``run(query, parameters=...)``.
        query: Cypher statement to execute.
        parameters: Parameter mapping passed to ``tx.run``. Expected shape matches
            the target query, typically including ``"dataset"`` and one entity-list
            key for chunked writes.

    Returns:
        ``None`` after the query result has been consumed.

    Raises:
        neo4j.exceptions.Neo4jError: Propagated for query execution failures.
        Exception: Propagates transaction/result errors raised by the driver.
    """
    result = tx.run(query, parameters=parameters)
    if inspect.isawaitable(result):
        result = await result
    consume_result = result.consume()
    if inspect.isawaitable(consume_result):
        await consume_result


_DATASET_ONLY_CYPHER = """
    MERGE (d:Dataset {id: $dataset.id})
        SET d.id = coalesce($dataset.id, d.id),
            d.name = coalesce($dataset.name, d.name),
            d.label = coalesce($dataset.label, d.label),
            d.urn = coalesce($dataset.urn, d.urn),
            d.agency = coalesce($dataset.agency, d.agency),
            d.version = coalesce($dataset.version, d.version),
            d.reusable_id = coalesce($dataset.reusable_id, d.reusable_id),
            d.reusable_version = coalesce($dataset.reusable_version, d.reusable_version),
            d.reusable_urn = coalesce($dataset.reusable_urn, d.reusable_urn),
            d.reusable_agency = coalesce($dataset.reusable_agency, d.reusable_agency),
            d.reusable_type_of_object = coalesce(
                $dataset.reusable_type_of_object,
                d.reusable_type_of_object
            )
"""

_DDI_CYPHER_QUERIES = (
    (
        "studies",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $studies AS studies
        UNWIND studies AS row
        MERGE (s:Study {id: row.study_id})
        SET s.dataset_id = coalesce(row.dataset_id, s.dataset_id),
            s.dataset_name = coalesce(row.dataset_name, s.dataset_name),
            s.id = coalesce(row.study_id, s.id),
            s.title = coalesce(row.title, s.title),
            s.abstract = coalesce(row.abstract, s.abstract),
            s.description = coalesce(row.description, s.description),
            s.urn = coalesce(row.urn, s.urn),
            s.agency = coalesce(row.agency, s.agency),
            s.version = coalesce(row.version, s.version),
            s.name = coalesce(row.name, s.name),
            s.label = coalesce(row.label, s.label),
            s.reusable_id = coalesce(row.reusable_id, s.reusable_id),
            s.reusable_version = coalesce(row.reusable_version, s.reusable_version),
            s.reusable_urn = coalesce(row.reusable_urn, s.reusable_urn),
            s.reusable_agency = coalesce(row.reusable_agency, s.reusable_agency),
            s.reusable_type_of_object = coalesce(
                row.reusable_type_of_object,
                s.reusable_type_of_object
            ),
            s.rationale = coalesce(row.rationale, s.rationale),
            s.language = coalesce(row.language, s.language),
            s.external_references = coalesce(row.external_references, s.external_references)
        MERGE (s)-[:DESCRIBES]->(d)
        """,
    ),
    (
        "organizations",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $organizations AS organizations
        UNWIND organizations AS row
        MERGE (o:Organization {id: row.organization_id})
        SET o.dataset_id = coalesce(row.dataset_id, o.dataset_id),
            o.dataset_name = coalesce(row.dataset_name, o.dataset_name),
            o.id = coalesce(row.organization_id, o.id),
            o.name = coalesce(row.name, o.name),
            o.abbreviation = coalesce(row.abbreviation, o.abbreviation),
            o.urn = coalesce(row.urn, o.urn),
            o.agency = coalesce(row.agency, o.agency),
            o.version = coalesce(row.version, o.version),
            o.label = coalesce(row.label, o.label),
            o.reusable_id = coalesce(row.reusable_id, o.reusable_id),
            o.reusable_version = coalesce(row.reusable_version, o.reusable_version),
            o.reusable_urn = coalesce(row.reusable_urn, o.reusable_urn),
            o.reusable_agency = coalesce(row.reusable_agency, o.reusable_agency),
            o.reusable_type_of_object = coalesce(
                row.reusable_type_of_object,
                o.reusable_type_of_object
            )
        MERGE (o)-[:ASSOCIATED_WITH]->(d)
        """,
    ),
    (
        "series_list",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $series_list AS series_list
        UNWIND series_list AS row
        MERGE (srs:Series {id: row.series_id})
        SET srs += row
        MERGE (srs)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "groups",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $groups AS groups
        UNWIND groups AS row
        MERGE (g:Group {id: row.group_id})
        SET g += row
        MERGE (g)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "data_collection_events",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $data_collection_events AS events
        UNWIND events AS row
        MERGE (e:DataCollectionEvent {id: row.event_id})
        SET e += row
        MERGE (e)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "data_files",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $data_files AS data_files
        UNWIND data_files AS row
        MERGE (f:DataFile {id: row.file_id})
        SET f += row
        MERGE (f)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "code_schemes",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $code_schemes AS code_schemes
        UNWIND code_schemes AS row
        MERGE (cs:CodeScheme {id: row.code_scheme_id})
        SET cs += row
        MERGE (cs)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "categories",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $categories AS categories
        UNWIND categories AS row
        MERGE (cat:Category {id: row.category_id})
        SET cat += row
        MERGE (cat)-[:IN_DATASET]->(d)
        FOREACH (
            schemeId IN CASE
                WHEN row.code_scheme_id IS NULL THEN []
                ELSE [row.code_scheme_id]
            END |
            MERGE (cs:CodeScheme {id: schemeId})
            MERGE (cs)-[:IN_DATASET]->(d)
            MERGE (cat)-[:IN_SCHEME]->(cs)
        )
        """,
    ),
    (
        "universes",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $universes AS universes
        UNWIND universes AS row
        MERGE (u:Universe {id: row.universe_id})
        SET u += row
        MERGE (u)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "concepts",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $concepts AS concepts
        UNWIND concepts AS row
        MERGE (c:Concept {name: row.name})
        SET c += row
        MERGE (c)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "questions",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $questions AS questions
        UNWIND questions AS row
        MERGE (q:Question {id: row.question_id})
        SET q += row
        MERGE (q)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "variables",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $variables AS rows
        UNWIND rows AS row
        MERGE (v:Variable {id: row.variable_id})
        SET v += row
        MERGE (v)-[:IN_DATASET]->(d)
        FOREACH (concept IN CASE WHEN row.concept IS NULL THEN [] ELSE [row.concept] END |
            MERGE (c:Concept {name: concept})
            MERGE (c)-[:IN_DATASET]->(d)
            MERGE (v)-[:USES_CONCEPT]->(c)
        )
        FOREACH (fileId IN CASE WHEN row.file_id IS NULL THEN [] ELSE [row.file_id] END |
            MERGE (f:DataFile {id: fileId})
            MERGE (f)-[:IN_DATASET]->(d)
            MERGE (v)-[:IN_FILE]->(f)
        )
        FOREACH (
            universeId IN CASE
                WHEN row.universe_id IS NULL THEN []
                ELSE [row.universe_id]
            END |
            MERGE (u:Universe {id: universeId})
            MERGE (u)-[:IN_DATASET]->(d)
            MERGE (v)-[:IN_UNIVERSE]->(u)
        )
        FOREACH (
            questionId IN CASE
                WHEN row.question_id IS NULL THEN []
                ELSE [row.question_id]
            END |
            MERGE (q:Question {id: questionId})
            MERGE (q)-[:IN_DATASET]->(d)
            FOREACH (
                questionText IN CASE
                    WHEN row.question_text IS NULL THEN []
                    ELSE [row.question_text]
                END |
                SET q.text = coalesce(questionText, q.text)
            )
            MERGE (v)-[:ASKED_AS]->(q)
        )
        FOREACH (
            categoryId IN CASE
                WHEN size(row.category_ids) = 0 THEN []
                ELSE row.category_ids
            END |
            MERGE (cat:Category {id: categoryId})
            MERGE (cat)-[:IN_DATASET]->(d)
            MERGE (v)-[:USES_CATEGORY]->(cat)
        )
        """,
    ),
    (
        "question_items",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $question_items AS question_items
        UNWIND question_items AS row
        MERGE (qi:QuestionItem {id: row.question_item_id})
        SET qi += row
        MERGE (qi)-[:IN_DATASET]->(d)
        FOREACH (
            variableId IN CASE
                WHEN row.variable_id IS NULL THEN []
                ELSE [row.variable_id]
            END |
            MERGE (v:Variable {id: variableId})
            MERGE (v)-[:IN_DATASET]->(d)
            MERGE (v)-[:USES_QUESTION_ITEM]->(qi)
        )
        FOREACH (
            parentQuestionId IN CASE
                WHEN row.parent_question_id IS NULL THEN []
                ELSE [row.parent_question_id]
            END |
            MERGE (pq:Question {id: parentQuestionId})
            MERGE (pq)-[:IN_DATASET]->(d)
            MERGE (qi)-[:PART_OF]->(pq)
        )
        FOREACH (
            gridId IN CASE
                WHEN row.parent_grid_id IS NULL THEN []
                ELSE [row.parent_grid_id]
            END |
            MERGE (qg:QuestionGrid {id: gridId})
            MERGE (qg)-[:IN_DATASET]->(d)
            MERGE (qg)-[:HAS_ITEM]->(qi)
        )
        FOREACH (
            flowId IN CASE
                WHEN row.parent_flow_id IS NULL THEN []
                ELSE [row.parent_flow_id]
            END |
            MERGE (qf:QuestionFlow {id: flowId})
            MERGE (qf)-[:IN_DATASET]->(d)
            MERGE (qf)-[:HAS_ITEM]->(qi)
        )
        """,
    ),
    (
        "logical_records",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $logical_records AS logical_records
        UNWIND logical_records AS row
        MERGE (lr:LogicalRecord {id: row.logical_record_id})
        SET lr += row
        MERGE (lr)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "physical_structures",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $physical_structures AS physical_structures
        UNWIND physical_structures AS row
        MERGE (ps:PhysicalStructure {id: row.physical_structure_id})
        SET ps += row
        MERGE (ps)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "other_materials",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $other_materials AS other_materials
        UNWIND other_materials AS row
        MERGE (om:OtherMaterial {id: row.material_id})
        SET om += row
        MERGE (om)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "var_groups",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $var_groups AS var_groups
        UNWIND var_groups AS row
        MERGE (vg:VarGroup {id: row.var_group_id})
        SET vg += row
        MERGE (vg)-[:IN_DATASET]->(d)
        FOREACH (varId IN CASE WHEN size(row.variable_ids) = 0 THEN [] ELSE row.variable_ids END |
            MERGE (v:Variable {id: varId})
            MERGE (v)-[:IN_DATASET]->(d)
            MERGE (vg)-[:GROUPS]->(v)
        )
        """,
    ),
    (
        "category_groups",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $category_groups AS category_groups
        UNWIND category_groups AS row
        MERGE (cg:CategoryGroup {id: row.category_group_id})
        SET cg += row
        MERGE (cg)-[:IN_DATASET]->(d)
        FOREACH (catId IN CASE WHEN size(row.category_ids) = 0 THEN [] ELSE row.category_ids END |
            MERGE (cat:Category {id: catId})
            MERGE (cat)-[:IN_DATASET]->(d)
            MERGE (cg)-[:GROUPS]->(cat)
        )
        """,
    ),
    (
        "question_grids",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $question_grids AS question_grids
        UNWIND question_grids AS row
        MERGE (qg:QuestionGrid {id: row.question_grid_id})
        SET qg += row
        MERGE (qg)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "question_flows",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $question_flows AS question_flows
        UNWIND question_flows AS row
        MERGE (qf:QuestionFlow {id: row.question_flow_id})
        SET qf += row
        MERGE (qf)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "sampling_procedures",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $sampling_procedures AS sampling_procedures
        UNWIND sampling_procedures AS row
        MERGE (sp:SamplingProcedure {id: row.sampling_id})
        SET sp += row
        MERGE (sp)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "weights",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $weights AS weights
        UNWIND weights AS row
        MERGE (w:Weight {id: row.weight_id})
        SET w += row
        MERGE (w)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "representations",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $representations AS representations
        UNWIND representations AS row
        MERGE (r:Representation {id: row.representation_id})
        SET r += row
        MERGE (r)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "code_lists",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $code_lists AS code_lists
        UNWIND code_lists AS row
        MERGE (cl:CodeList {id: row.code_list_id})
        SET cl += row
        MERGE (cl)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "methodology_notes",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $methodology_notes AS methodology_notes
        UNWIND methodology_notes AS row
        MERGE (mn:MethodologyNote {id: row.note_id})
        SET mn += row
        MERGE (mn)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "processing_events",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $processing_events AS processing_events
        UNWIND processing_events AS row
        MERGE (pe:ProcessingEvent {id: row.processing_event_id})
        SET pe += row
        MERGE (pe)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "software",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $software AS software
        UNWIND software AS row
        MERGE (sw:Software {id: row.software_id})
        SET sw += row
        MERGE (sw)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "access_conditions",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $access_conditions AS access_conditions
        UNWIND access_conditions AS row
        MERGE (ac:AccessCondition {id: row.access_condition_id})
        SET ac += row
        MERGE (ac)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "citations",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $citations AS citations
        UNWIND citations AS row
        MERGE (cit:Citation {id: row.citation_id})
        SET cit += row
        MERGE (cit)-[:DESCRIBES]->(d)
        """,
    ),
    (
        "coverage",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $coverage AS coverage
        UNWIND coverage AS row
        MERGE (cov:Coverage {id: row.coverage_id})
        SET cov += row
        MERGE (cov)-[:COVERS]->(d)
        """,
    ),
    (
        "funding",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $funding AS funding
        UNWIND funding AS row
        MERGE (fund:Funding {id: row.funding_id})
        SET fund += row
        MERGE (fund)-[:FUNDS]->(d)
        """,
    ),
    (
        "contributor_roles",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $contributor_roles AS contributor_roles
        UNWIND contributor_roles AS row
        MERGE (con:Contributor {id: row.contributor_id})
        SET con += row
        MERGE (con)-[:CONTRIBUTES_TO]->(d)
        """,
    ),
    (
        "instruments",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $instruments AS instruments
        UNWIND instruments AS row
        MERGE (ins:CollectionInstrument {id: row.instrument_id})
        SET ins += row
        MERGE (ins)-[:INSTRUMENT_FOR]->(d)
        """,
    ),
    (
        "control_constructs",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $control_constructs AS control_constructs
        UNWIND control_constructs AS row
        MERGE (cc:ControlConstruct {id: row.construct_id})
        SET cc += row
        MERGE (cc)-[:USES_CONSTRUCT]->(d)
        """,
    ),
    (
        "represented_variables",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $represented_variables AS represented_variables
        UNWIND represented_variables AS row
        MERGE (rv:RepresentedVariable {id: row.represented_variable_id})
        SET rv += row
        MERGE (rv)-[:REPRESENTS]->(d)
        """,
    ),
    (
        "comparisons",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $comparisons AS comparisons
        UNWIND comparisons AS row
        MERGE (cmp:Comparison {id: row.comparison_id})
        SET cmp += row
        MERGE (cmp)-[:HAS_COMPARISON]->(d)
        """,
    ),
    (
        "access_policies",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $access_policies AS access_policies
        UNWIND access_policies AS row
        MERGE (ap:AccessPolicy {id: row.access_policy_id})
        SET ap += row
        MERGE (d)-[:GOVERNED_BY]->(ap)
        """,
    ),
    # DDI-C 2.6 collections
    (
        "ncubes",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $ncubes AS ncubes
        UNWIND ncubes AS row
        MERGE (nc:NCube {id: row.ncube_id})
        SET nc += row
        MERGE (nc)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "ncube_groups",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $ncube_groups AS ncube_groups
        UNWIND ncube_groups AS row
        MERGE (ng:NCubeGroup {id: row.ncube_group_id})
        SET ng += row
        MERGE (ng)-[:IN_DATASET]->(d)
        FOREACH (ncubeId IN CASE WHEN size(row.ncube_ids) = 0 THEN [] ELSE row.ncube_ids END |
            MERGE (nc:NCube {id: ncubeId})
            MERGE (nc)-[:IN_DATASET]->(d)
            MERGE (ng)-[:GROUPS]->(nc)
        )
        """,
    ),
    (
        "document_descriptions",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $document_descriptions AS document_descriptions
        UNWIND document_descriptions AS row
        MERGE (dd:DocumentDescription {id: row.doc_id})
        SET dd += row
        MERGE (dd)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "sample_frames",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $sample_frames AS sample_frames
        UNWIND sample_frames AS row
        MERGE (sf:SampleFrame {id: row.sample_frame_id})
        SET sf += row
        MERGE (sf)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "quality_statements",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $quality_statements AS quality_statements
        UNWIND quality_statements AS row
        MERGE (qs:QualityStatement {id: row.quality_id})
        SET qs += row
        MERGE (qs)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "study_authorizations",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $study_authorizations AS study_authorizations
        UNWIND study_authorizations AS row
        MERGE (sa:StudyAuthorization {id: row.authorization_id})
        SET sa += row
        MERGE (sa)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "study_developments",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $study_developments AS study_developments
        UNWIND study_developments AS row
        MERGE (sd:StudyDevelopment {id: row.development_id})
        SET sd += row
        MERGE (sd)-[:IN_DATASET]->(d)
        """,
    ),
    (
        "ex_post_evaluations",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $ex_post_evaluations AS ex_post_evaluations
        UNWIND ex_post_evaluations AS row
        MERGE (epe:ExPostEvaluation {id: row.evaluation_id})
        SET epe += row
        MERGE (epe)-[:IN_DATASET]->(d)
        """,
    ),
    # Generic identifiables use a composite identity
    # (dataset_id, element_tag, identifiable_id) because the original DDI id
    # is only unique within a given element tag inside a single dataset.
    (
        "generic_identifiables",
        """
        MATCH (d:Dataset {id: $dataset.id})
        WITH d, $generic_identifiables AS generic_identifiables
        UNWIND generic_identifiables AS row
        MERGE (gi:DDIGenericIdentifiable {
            dataset_id: row.dataset_id,
            element_tag: row.element_tag,
            identifiable_id: row.identifiable_id
        })
        SET gi += row
        MERGE (gi)-[:IN_DATASET]->(d)
        """,
    ),
)


# NOTE: The _build_combined_write_cypher function and _COMBINED_WRITE_CYPHER constant
# have been removed because using CALL {} subqueries for writes in Neo4j 5.x
# causes issues where writes don't persist. The write_batch method now executes
# each entity query separately within the same transaction.


_PURGE_DATASET_CYPHER = """
        MATCH (d:Dataset {id: $dataset_id})
        OPTIONAL MATCH (d)-[rel]-()
        WITH d, collect(rel) AS rels
        FOREACH (r IN rels | DELETE r)
        CALL {
            WITH d
            OPTIONAL MATCH (d)-[]-(n)
            WHERE n <> d
            DETACH DELETE n
        }
        DETACH DELETE d
    """


__all__ = ["Neo4jGraphAdapter"]

"""CRUD-simple public API for ``ddigraph``.

The four functions below cover the 90 % case. Power users still have
:class:`~ddigraph.ingest.loader.DDILoader`,
:class:`~ddigraph.ingest.fragment_loader.DDIFragmentLoader`, and the
CDI ``parse_cdi_batches`` family available for fine-grained control;
this module just spares ordinary callers from building drivers, picking
a flavor-specific loader, and chaining ``asyncio.run`` themselves.

Typical usage::

    import ddigraph

    # Bootstrap the target's schema once.
    ddigraph.bootstrap(target="bolt://localhost:7687")

    # Stream a DDI file into the target. Format auto-detected.
    result = ddigraph.load("survey.xml", target="bolt://localhost:7687")
    print(result.nodes_written, "nodes,", result.relationships_written, "relationships")

Connection credentials default to the env-driven
:class:`~ddigraph.config.Settings` model when ``target`` is omitted, so
the existing ``DDIGRAPH_NEO4J_*`` (or legacy ``NEO4J_*``) variables
continue to work.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal

from neo4j import AsyncDriver, AsyncGraphDatabase

from ddigraph.config import Settings
from ddigraph.graph.bootstrap import ensure_schema as _ensure_schema
from ddigraph.ingest.fragment_loader import (
    DDIFragmentLoader,
    detect_ddi_format,
)
from ddigraph.ingest.loader import DDILoader
from ddigraph.paths import default_dataset_id

type FlavorName = Literal["codebook", "lifecycle", "cdi", "unknown"]


@dataclass(slots=True)
class LoadResult:
    """Summary of a single ``ddigraph.load`` invocation.

    Attributes:
        flavor: One of ``"codebook"`` or ``"lifecycle"`` (CDI ingestion
            is not yet covered by this entry point).
        target: The connection URL the load wrote to.
        dataset_id: Identifier assigned to the ingested dataset (the
            codebook flavor always sets one; lifecycle leaves it
            ``None``).
        nodes_written: Number of graph nodes the loader recorded.
        relationships_written: Number of relationships recorded.
        duration_s: Wall-clock seconds the load took.
        dry_run: True if the load ran in dry-run mode (no writes).
        totals: The raw per-entity counts the underlying loader returned.
    """

    flavor: FlavorName
    target: str
    dataset_id: str | None
    nodes_written: int
    relationships_written: int
    duration_s: float
    dry_run: bool
    totals: dict[str, int]


def detect(path: str | Path) -> FlavorName:
    """Return the DDI flavor of ``path``.

    Thin typed wrapper over
    :func:`ddigraph.ingest.fragment_loader.detect_ddi_format` so callers
    get a real ``Literal`` instead of a free-form string.
    """
    raw = detect_ddi_format(path)
    if raw in ("codebook", "lifecycle", "cdi"):
        return raw  # type: ignore[return-value]
    return "unknown"


def _resolve_settings(target: str | None, settings: Settings | None) -> tuple[Settings, str]:
    """Materialise a ``Settings`` instance and the URI it points at.

    If ``settings`` is given, ``target`` overrides its ``neo4j_uri``;
    otherwise a fresh ``Settings()`` is built from environment.
    """
    base = settings or Settings()
    if target is not None:
        # pydantic models are frozen by default; rebuild via model_copy.
        base = base.model_copy(update={"neo4j_uri": target})
    return base, base.neo4j_uri


def _driver(settings: Settings) -> AsyncDriver:
    """Build an ``AsyncDriver`` from a ``Settings`` instance."""
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )


# Re-exported under its historical private name so existing callers and
# tests keep working; the implementation moved to ``ddigraph.paths`` when
# ``ddigraph.graph.view`` needed the same derivation.
_default_dataset_id = default_dataset_id


async def aload(
    path: str | Path,
    *,
    target: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    dry_run: bool = False,
    replace: bool = False,
    settings: Settings | None = None,
) -> LoadResult:
    """Async load of a DDI file into the configured Neo4j target.

    Format auto-detection picks DDI-Codebook or DDI-L Lifecycle and
    dispatches to the matching loader. DDI-CDI is parsed but not yet
    persisted by this entry point (use ``ddigraph.parse_cdi_batches``).
    Non-Neo4j backends (RDF, Gremlin, NetworkX, pandas) are not driven
    through ``load``; use the parser tier and a backend-specific
    adapter (see the ``demo/load_*.py`` examples).

    Args:
        path: Filesystem path to the DDI XML.
        target: Neo4j URL (``bolt://...`` or ``neo4j://...``). When
            omitted the env-driven ``DDIGRAPH_NEO4J_URI`` is used.
        dataset_id: Dataset identifier (codebook flavor). Defaults to
            the file stem when not supplied.
        dataset_name: Human-readable dataset name (codebook flavor).
        dry_run: When True, parse and validate without writing.
        replace: When True, purge existing dataset content before
            loading (codebook flavor only; lifecycle ``clear_first``).
        settings: Optional pre-built ``Settings`` instance.

    Returns:
        A :class:`LoadResult` describing the load outcome.

    Raises:
        ValueError: If ``path`` does not point at a readable XML file.
        NotImplementedError: If ``path`` is a CDI document (not yet
            persisted by this entry point).
    """
    resolved_settings, target_uri = _resolve_settings(target, settings)
    flavor = detect(path)
    if flavor == "cdi":
        raise NotImplementedError(
            "ddigraph.load/aload does not yet persist DDI-CDI documents. "
            "Use ddigraph.parse_cdi_batches and a custom adapter."
        )

    start = perf_counter()
    driver = _driver(resolved_settings)
    try:
        totals: dict[str, int]
        if flavor == "lifecycle":
            loader = DDIFragmentLoader(driver, settings=resolved_settings)
            totals = await loader.load(path=path, clear_first=replace)
            resolved_dataset_id: str | None = None
        else:
            # Codebook flavor uses the sync DDILoader under the hood.
            from neo4j import GraphDatabase

            sync_driver = GraphDatabase.driver(
                resolved_settings.neo4j_uri,
                auth=(
                    resolved_settings.neo4j_user,
                    resolved_settings.neo4j_password.get_secret_value(),
                ),
            )
            try:
                codebook_loader = DDILoader(sync_driver, settings=resolved_settings)
                resolved_dataset_id = dataset_id or _default_dataset_id(path)
                totals = await codebook_loader.load(
                    path=path,
                    dataset_id=resolved_dataset_id,
                    dataset_name=dataset_name,
                    dry_run=dry_run,
                    replace=replace,
                )
            finally:
                sync_driver.close()
    finally:
        await driver.close()

    nodes = sum(v for k, v in totals.items() if "relationship" not in k.lower())
    rels = sum(v for k, v in totals.items() if "relationship" in k.lower())

    return LoadResult(
        flavor=flavor,
        target=target_uri,
        dataset_id=resolved_dataset_id,
        nodes_written=nodes,
        relationships_written=rels,
        duration_s=perf_counter() - start,
        dry_run=dry_run,
        totals=totals,
    )


def load(
    path: str | Path,
    *,
    target: str | None = None,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
    dry_run: bool = False,
    replace: bool = False,
    settings: Settings | None = None,
) -> LoadResult:
    """Synchronously load a DDI file into the configured Neo4j target.

    Internally drives :func:`aload` via :func:`asyncio.run`. Use
    :func:`aload` directly when calling from already-async code.

    See :func:`aload` for argument details.
    """
    return asyncio.run(
        aload(
            path,
            target=target,
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            dry_run=dry_run,
            replace=replace,
            settings=settings,
        )
    )


async def abootstrap(
    *,
    target: str | None = None,
    include_fragments: bool = True,
    settings: Settings | None = None,
) -> None:
    """Async equivalent of :func:`bootstrap`."""
    resolved_settings, _ = _resolve_settings(target, settings)
    driver = _driver(resolved_settings)
    try:
        await _ensure_schema(
            driver,
            database=resolved_settings.neo4j_database,
            include_fragments=include_fragments,
        )
    finally:
        await driver.close()


def bootstrap(
    *,
    target: str | None = None,
    include_fragments: bool = True,
    settings: Settings | None = None,
) -> None:
    """Create the indexes and constraints DDI ingestion needs.

    Args:
        target: Neo4j URL. Defaults to env-driven settings.
        include_fragments: When True, also create DDI-L Lifecycle
            constraints alongside the Codebook ones.
        settings: Optional pre-built ``Settings`` instance.
    """
    asyncio.run(
        abootstrap(
            target=target,
            include_fragments=include_fragments,
            settings=settings,
        )
    )


__all__ = [
    "FlavorName",
    "LoadResult",
    "abootstrap",
    "aload",
    "bootstrap",
    "detect",
    "load",
]

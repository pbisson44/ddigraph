"""Command-line entrypoints for ddigraph."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import orjson
from neo4j import AsyncDriver, AsyncGraphDatabase, Driver, GraphDatabase

from ddigraph.config import Settings, resolve_credentials_source
from ddigraph.exporter import FORMATS as export_formats, RDF_FORMATS as rdf_formats
from ddigraph.graph.bootstrap import ensure_schema
from ddigraph.ingest.fragment_loader import DDIFragmentLoader, detect_ddi_format
from ddigraph.ingest.loader import DRY_RUN_MESSAGE, DDILoader, normalize_dataset_id
from ddigraph.logging import configure_logging, get_logger
from ddigraph.paths import validate_readable_xml_path
from ddigraph.previewer import FORMATS as preview_formats
from ddigraph.rdf.shacl import FLAVORS as shacl_flavors

logger = get_logger(__name__)


def resolve_xml_path(raw_path: str) -> str:
    """Validate that a user-supplied XML path points to a readable file.

    Args:
        raw_path: Path string as entered on the command line.

    Returns:
        The validated absolute path as a string.

    Raises:
        argparse.ArgumentTypeError: If the path is missing, unreadable, or
            does not look like an XML file.
    """
    try:
        return str(validate_readable_xml_path(raw_path))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def resolve_dataset_id(raw_dataset_id: str) -> str:
    """Normalize a user-supplied dataset identifier.

    Args:
        raw_dataset_id: Dataset ID as entered on the command line.

    Returns:
        The normalized dataset identifier.

    Raises:
        argparse.ArgumentTypeError: If the identifier is empty or malformed.
    """
    try:
        return normalize_dataset_id(raw_dataset_id)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _driver_kwargs(settings: Settings) -> dict[str, Any]:
    """Build common keyword arguments for Neo4j driver construction."""
    kwargs: dict[str, Any] = {}

    if settings.max_connection_pool_size is not None:
        kwargs["max_connection_pool_size"] = settings.max_connection_pool_size
    if settings.connection_timeout is not None:
        kwargs["connection_timeout"] = settings.connection_timeout
    if settings.max_connection_lifetime is not None:
        kwargs["max_connection_lifetime"] = settings.max_connection_lifetime

    tls_fields = getattr(settings, "_cli_tls_fields", None)
    if tls_fields is None:
        tls_fields = settings.model_fields_set
    if "encrypted" in tls_fields and settings.encrypted is not None:
        kwargs["encrypted"] = settings.encrypted
    if "verify_hostname" in tls_fields and settings.verify_hostname is not None:
        kwargs["verify_hostname"] = settings.verify_hostname
    if "trusted_certificates" in tls_fields and settings.trusted_certificates is not None:
        kwargs["trusted_certificates"] = settings.trusted_certificates
    if "trusted_certificates_file" in tls_fields and settings.trusted_certificates_file is not None:
        kwargs["trusted_certificates_file"] = settings.trusted_certificates_file

    return kwargs


def _create_driver(settings: Settings) -> Driver:
    """Create a Neo4j driver from settings."""
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        **_driver_kwargs(settings),
    )


def _create_async_driver(settings: Settings) -> AsyncDriver:
    """Create an async Neo4j driver from settings."""
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        **_driver_kwargs(settings),
    )


def _add_connection_options(parser: argparse.ArgumentParser) -> None:
    """Attach Neo4j connection flags to a parser."""
    parser.add_argument("--neo4j-uri", dest="neo4j_uri", help="Neo4j bolt URI")
    parser.add_argument("--neo4j-user", dest="neo4j_user", help="Neo4j username")
    parser.add_argument(
        "--neo4j-password",
        dest="neo4j_password",
        help="Neo4j password (plain-text string)",
    )
    parser.add_argument(
        "--neo4j-database",
        dest="neo4j_database",
        help="Neo4j database name to target",
    )
    parser.add_argument(
        "--max-connection-pool-size",
        type=int,
        dest="max_connection_pool_size",
        help="Maximum pooled connections used by the Neo4j driver",
    )
    parser.add_argument(
        "--connection-timeout",
        type=float,
        dest="connection_timeout",
        help="Seconds to wait when opening a new Neo4j connection",
    )
    parser.add_argument(
        "--max-connection-lifetime",
        type=float,
        dest="max_connection_lifetime",
        help="Seconds to keep pooled Neo4j connections alive before recycling",
    )
    parser.add_argument(
        "--session-timeout",
        type=float,
        dest="session_timeout",
        help="Seconds to keep a Neo4j session alive before timing out",
    )
    parser.add_argument(
        "--transaction-timeout",
        type=float,
        dest="transaction_timeout",
        help="Server-side timeout in seconds for write transactions",
    )
    parser.add_argument(
        "--encrypted",
        dest="encrypted",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Require encrypted (TLS) connections to Neo4j",
    )
    parser.add_argument(
        "--verify-hostname",
        dest="verify_hostname",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Verify the Neo4j server hostname in TLS certificates",
    )
    parser.add_argument(
        "--trusted-certificates",
        dest="trusted_certificates",
        help="Trusted certificate selection (e.g., TRUST_ALL_CERTIFICATES)",
    )
    parser.add_argument(
        "--trusted-certificates-file",
        dest="trusted_certificates_file",
        help="Path to PEM file containing trusted certificates",
    )


def _add_ingestion_tuning(parser: argparse.ArgumentParser) -> None:
    """Attach ingestion tuning flags for batch/concurrency control."""
    parser.add_argument(
        "--queue-maxsize",
        type=int,
        dest="queue_maxsize",
        help="Max batches waiting before back-pressure",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        dest="chunk_size",
        help="Parsed records to accumulate per batch",
    )
    parser.add_argument(
        "--writer-concurrency",
        type=int,
        dest="writer_concurrency",
        help="Concurrent writer tasks flushing to Neo4j",
    )
    parser.add_argument(
        "--batch-metrics",
        dest="batch_metrics",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Emit per-batch metrics to stdout",
    )
    parser.add_argument(
        "--strict-parsing",
        dest="strict_parsing",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Raise on XML syntax errors instead of recovering",
    )
    parser.add_argument(
        "--dry-run",
        "--validate-only",
        dest="dry_run",
        default=None,
        action=argparse.BooleanOptionalAction,
        help="Parse and validate without writing to Neo4j",
    )
    parser.add_argument(
        "--replace",
        dest="replace",
        default=None,
        action=argparse.BooleanOptionalAction,
        help=("Purge existing dataset nodes/relationships before loading (skipped during dry-run)"),
    )
    parser.add_argument(
        "--write-retry-attempts",
        type=int,
        dest="write_retry_attempts",
        help="Maximum attempts for transient write failures (including first attempt)",
    )
    parser.add_argument(
        "--write-retry-base-delay",
        type=float,
        dest="write_retry_base_delay",
        help="Base delay in seconds for exponential backoff on transient write retries",
    )
    parser.add_argument(
        "--write-retry-jitter",
        type=float,
        dest="write_retry_jitter",
        help="Maximum random jitter in seconds added to transient write retry delays",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        help="Logging verbosity (e.g. DEBUG, INFO, WARNING)",
    )
    parser.add_argument(
        "--metrics-namespace",
        dest="metrics_namespace",
        help="Prefix applied to emitted metrics names",
    )


def _tuning_overrides(args: argparse.Namespace) -> dict[str, object]:
    """Collect ``Settings`` overrides from ``--config`` then ``--tune``.

    The collapsed power-user surface: any ``Settings`` field can be set
    without a dedicated flag. ``--config FILE`` is a flat TOML table of
    field/value pairs; ``--tune KEY=VALUE`` (repeatable) overrides it.
    Both sit *below* the explicit per-flag options, which the caller
    applies last. An unknown key is a hard error so a typo fails fast
    instead of being silently dropped.
    """
    valid = set(Settings.model_fields)
    layered: dict[str, object] = {}

    config_file = getattr(args, "config_file", None)
    if config_file is not None:
        try:
            with open(config_file, "rb") as handle:
                data = tomllib.load(handle)
        except OSError as exc:
            raise SystemExit(f"--config: cannot read {config_file}: {exc}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise SystemExit(f"--config: invalid TOML in {config_file}: {exc}") from exc
        for key, value in data.items():
            if key not in valid:
                raise SystemExit(f"--config: unknown setting {key!r} in {config_file}")
            layered[key] = value

    for item in getattr(args, "tune", None) or []:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise SystemExit(f"--tune expects KEY=VALUE, got {item!r}")
        if key not in valid:
            raise SystemExit(f"--tune: unknown setting {key!r}")
        layered[key] = value

    return layered


def _settings_from_args(args: argparse.Namespace) -> Settings:
    """Merge CLI overrides into the pydantic Settings model.

    Precedence (highest first): explicit per-flag options, ``--tune``,
    ``--config`` file, environment / ``.env``, model defaults.
    """
    explicit = {
        field: value
        for field in (
            "neo4j_uri",
            "neo4j_user",
            "neo4j_password",
            "neo4j_database",
            "max_connection_pool_size",
            "connection_timeout",
            "max_connection_lifetime",
            "session_timeout",
            "transaction_timeout",
            "encrypted",
            "verify_hostname",
            "trusted_certificates",
            "trusted_certificates_file",
            "queue_maxsize",
            "chunk_size",
            "writer_concurrency",
            "batch_metrics",
            "strict_parsing",
            "dry_run",
            "replace",
            "write_retry_attempts",
            "write_retry_base_delay",
            "write_retry_jitter",
            "log_level",
            "metrics_namespace",
        )
        if (value := getattr(args, field, None)) is not None
    }
    # Explicit per-flag options win over the --config/--tune layer.
    merged = {**_tuning_overrides(args), **explicit}
    settings = Settings(**merged)
    cli_tls_fields = {
        field
        for field in (
            "encrypted",
            "verify_hostname",
            "trusted_certificates",
            "trusted_certificates_file",
        )
        if field in merged
    }
    object.__setattr__(settings, "_cli_tls_fields", cli_tls_fields)
    return settings


async def _ensure_schema_command(
    args: argparse.Namespace, settings: Settings, create_driver: Any = None
) -> None:
    """Run the schema bootstrap routine."""
    driver_factory = create_driver or _create_async_driver
    driver = driver_factory(settings)
    include_fragments = getattr(args, "include_fragments", False)
    include_cdi = getattr(args, "include_cdi", False)

    try:
        await ensure_schema(
            driver,
            database=settings.neo4j_database,
            include_fragments=include_fragments,
            include_cdi=include_cdi,
        )
        msg = "Schema ensured (including fragments)" if include_fragments else "Schema ensured"
        logger.info(msg, extra={"database": settings.neo4j_database})
        print(f"{msg} for database '{settings.neo4j_database}'")
    finally:
        await driver.close()


async def _load_command_async(
    args: argparse.Namespace, settings: Settings, create_driver: Any = None
) -> dict[str, int]:
    """Async implementation of the load command."""
    # Detect format if auto
    ddi_format = getattr(args, "format", "auto")
    if ddi_format == "auto":
        ddi_format = _detect_load_format(args.xml_path)
        logger.info(f"Auto-detected DDI format: {ddi_format}")

    driver_factory = create_driver or _create_async_driver
    driver = driver_factory(settings)

    credentials_source = resolve_credentials_source(
        cli_overrides=any(
            getattr(args, field, None) for field in ("neo4j_uri", "neo4j_user", "neo4j_password")
        )
    )
    dry_run_status = "ON" if settings.dry_run else "OFF"
    print(
        f"Pre-ingestion: connecting to Neo4j at "
        f"{settings.neo4j_uri} (database '{settings.neo4j_database}'); "
        f"credentials from {credentials_source}; dry-run/validate-only is {dry_run_status}; "
        f"format: {ddi_format}"
    )

    try:
        if settings.dry_run:
            print(DRY_RUN_MESSAGE)

        totals: dict[str, int] = {}
        if ddi_format == "rdf":
            from ddigraph.graph.writer import GraphChunkWriter
            from ddigraph.rdf.reader import read_graph

            writer = GraphChunkWriter(
                driver,
                database=settings.neo4j_database,
                chunk_size=settings.chunk_size,
            )
            totals = await writer.write(read_graph(args.xml_path))
        elif ddi_format == "lifecycle":
            # Use DDI-L FragmentInstance loader
            fragment_loader = DDIFragmentLoader(driver, settings=settings)
            totals = await fragment_loader.load(
                path=args.xml_path,
                clear_first=settings.replace,
            )
        else:
            # Use DDI Codebook loader
            sync_driver = _create_driver(settings) if create_driver is None else driver
            codebook_loader = DDILoader(sync_driver, settings=settings)
            load_error: BaseException | None = None
            try:
                load_result = codebook_loader.load(
                    path=args.xml_path,
                    dataset_id=args.dataset_id,
                    dataset_name=args.dataset_name,
                    dry_run=settings.dry_run,
                    replace=settings.replace,
                )
                totals = await load_result if inspect.isawaitable(load_result) else load_result
            except BaseException as exc:
                load_error = exc
                raise
            finally:
                if sync_driver is not driver:
                    try:
                        sync_driver.close()
                    except Exception:
                        if load_error is None:
                            raise
                        logger.warning(
                            "Failed to close sync codebook driver after loader error",
                            exc_info=True,
                        )

        return totals or {}
    finally:
        await driver.close()


def _detect_load_format(path: str) -> str:
    """Return the format ``load`` should use for a path.

    RDF is recognised by extension rather than by sniffing: ``detect_ddi_format``
    reads the file as XML, and while RDF/XML would parse, Turtle and JSON-LD
    would not, so the three serialisations would disagree about the same graph.

    Args:
        path: The input file path.

    Returns:
        ``"rdf"``, or the DDI flavor reported by ``detect_ddi_format``.
    """
    from ddigraph.rdf.reader import EXTENSION_FORMATS

    suffix = Path(path).suffix.lower()
    # ``.xml`` appears in both maps; DDI XML is the overwhelmingly common
    # case for this command, so it stays with the XML parsers.
    if suffix in EXTENSION_FORMATS and suffix != ".xml":
        return "rdf"
    return detect_ddi_format(path)


def _load_command(args: argparse.Namespace, settings: Settings, create_driver: Any = None) -> None:
    """Stream DDI XML into Neo4j using configured settings."""
    _preflight_validate(args)

    totals = asyncio.run(_load_command_async(args, settings, create_driver))

    if getattr(args, "json_output", False):
        print(orjson.dumps(totals).decode())
    elif totals:
        summary = ", ".join(f"{name}={count}" for name, count in sorted(totals.items()))
        print(f"Ingestion complete: {summary}")
    else:
        print("Ingestion complete")

    logger.info("Ingestion complete", extra={"totals": totals})


def _detect_command(args: argparse.Namespace, settings: Settings) -> None:
    """Detect the DDI format of an XML file."""
    ddi_format = detect_ddi_format(args.xml_path)

    if getattr(args, "json_output", False):
        print(orjson.dumps({"path": args.xml_path, "format": ddi_format}).decode())
    else:
        print(f"Format: {ddi_format}")
        print(f"File: {args.xml_path}")


def _export_command(args: argparse.Namespace, settings: Settings) -> None:
    """Export a DDI file to RDF, JSON, or CSV.

    Needs no Neo4j connection: the whole path runs off the parser tier and
    the backend-neutral graph view.
    """
    from ddigraph.exporter import export

    _preflight_validate(args)

    try:
        result = export(
            args.xml_path,
            args.output,
            format=args.format,
            base=args.base_uri,
            dataset_id=getattr(args, "dataset_id", None),
            dataset_name=getattr(args, "dataset_name", None),
            chunk_size=settings.chunk_size,
        )
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    if getattr(args, "json_output", False):
        payload = {
            "path": str(result.path),
            "format": result.format,
            "nodes": result.nodes,
            "relationships": result.relationships,
            "triples": result.triples,
        }
        print(orjson.dumps(payload).decode())
        return

    print(f"Wrote {result.path}")
    print(f"Format: {result.format}")
    print(f"Nodes: {result.nodes}  Relationships: {result.relationships}")
    if result.triples is not None:
        print(f"Triples: {result.triples}")


def _shapes_command(args: argparse.Namespace, settings: Settings) -> None:
    """Write SHACL shapes derived from the DDI schema.

    Takes no input document: the shapes come from ``DDISchema``, the same
    table that generates the Neo4j constraints.
    """
    from ddigraph.exporter import RDF_FORMATS

    try:
        from ddigraph.rdf.shacl import shapes_graph
    except ImportError as exc:  # pragma: no cover - defensive
        raise SystemExit(str(exc)) from exc

    try:
        graph = shapes_graph(flavor=args.flavor)
    except ImportError as exc:
        raise SystemExit(str(exc)) from exc

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(output), format=RDF_FORMATS[args.format])

    if getattr(args, "json_output", False):
        payload = {"path": str(output), "flavor": args.flavor, "triples": len(graph)}
        print(orjson.dumps(payload).decode())
        return

    print(f"Wrote {output}")
    print(f"Flavor: {args.flavor or 'all'}")
    print(f"Triples: {len(graph)}")


def _preflight_validate(args: argparse.Namespace) -> None:
    """Refuse to process a file that fails its XSD, when asked to.

    Only runs when ``--validate`` was passed. Reads the same flavor the
    command itself will use, so the two never disagree about what the file
    is.
    """
    if not getattr(args, "validate", False):
        return

    from ddigraph.validation import SchemaUnavailableError, validate

    # ``--format`` means different things on different verbs: the DDI flavor
    # on ``load``, but the *output* format on ``export``, where it is
    # "turtle" or "csv". Only forward it when it actually names a flavor;
    # otherwise let the document speak for itself.
    requested = getattr(args, "format", None)
    flavor = requested if requested in {"codebook", "lifecycle", "cdi"} else None

    try:
        result = validate(args.xml_path, flavor=flavor, max_issues=20)
    except SchemaUnavailableError as exc:
        raise SystemExit(str(exc)) from exc

    if result.valid:
        return

    lines = [f"{args.xml_path} does not conform to {result.schema.name}:"]
    lines += [f"  {issue}" for issue in result.issues]
    lines.append("Drop --validate to process it anyway.")
    raise SystemExit("\n".join(lines))


def _validate_command(args: argparse.Namespace, settings: Settings) -> None:
    """Validate a DDI file against the XSD its flavor and version call for.

    Exits non-zero when the document does not conform, so it drops into a
    shell pipeline or a CI step without extra glue.
    """
    from ddigraph.validation import SchemaUnavailableError, validate

    try:
        result = validate(
            args.xml_path,
            flavor=None if args.flavor == "auto" else args.flavor,
            max_issues=args.max_issues,
        )
    except SchemaUnavailableError as exc:
        raise SystemExit(str(exc)) from exc

    if getattr(args, "json_output", False):
        payload = {
            "path": str(args.xml_path),
            "flavor": result.flavor,
            "version": result.version,
            "schema": str(result.schema),
            "valid": result.valid,
            "issues": [
                {"line": issue.line, "column": issue.column, "message": issue.message}
                for issue in result.issues
            ],
        }
        print(orjson.dumps(payload).decode())
        raise SystemExit(0 if result.valid else 1)

    version = f" {result.version.replace('_', '.')}" if result.version else ""
    print(f"File:   {args.xml_path}")
    print(f"Flavor: {result.flavor}{version}")
    print(f"Schema: {result.schema}")

    if result.valid:
        print("Result: valid")
        return

    print(f"Result: invalid ({len(result.issues)} issue(s))")
    for issue in result.issues:
        print(f"  {issue}")
    raise SystemExit(1)


def _preview_command(args: argparse.Namespace, settings: Settings) -> None:
    """Summarise a DDI file's graph shape, with no database involved."""
    from ddigraph.previewer import preview

    rendered = preview(
        args.xml_path,
        format=args.format,
        limit=args.limit,
        dataset_id=getattr(args, "dataset_id", None),
        chunk_size=settings.chunk_size,
    )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {output}")
        return

    print(rendered, end="")


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level CLI argument parser.

    Returns:
        A fully configured :class:`argparse.ArgumentParser` whose
        subparsers wire each ``ddigraph`` subcommand to its handler via
        ``parser.set_defaults(handler=...)``.
    """
    parser = argparse.ArgumentParser(
        prog="ddigraph",
        description=(
            "DDI ingestion tools for Neo4j - supports both DDI Codebook "
            "and DDI-L FragmentInstance formats"
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    # load command
    load_parser = subcommands.add_parser(
        "load",
        help="Stream a DDI XML file into Neo4j (auto-detects Codebook vs Lifecycle)",
    )
    _add_connection_options(load_parser)
    _add_ingestion_tuning(load_parser)
    load_parser.add_argument(
        "--tune",
        action="append",
        metavar="KEY=VALUE",
        dest="tune",
        help=(
            "Set any Settings field without a dedicated flag, e.g. "
            "--tune chunk_size=500 (repeatable; overrides --config; "
            "a dedicated flag still wins)"
        ),
    )
    load_parser.add_argument(
        "--config",
        type=Path,
        dest="config_file",
        metavar="FILE",
        help="TOML file: a flat table of Settings fields (per-flag options win over it)",
    )
    load_parser.add_argument(
        "xml_path",
        type=resolve_xml_path,
        help="Filesystem path to the DDI XML input",
    )
    load_parser.add_argument(
        "--format",
        dest="format",
        choices=["auto", "codebook", "lifecycle", "rdf"],
        default="auto",
        help=(
            "Input format: auto (detect), codebook, lifecycle, or rdf for a "
            "Turtle/JSON-LD/N-Triples/RDF-XML graph (default: auto)"
        ),
    )
    load_parser.add_argument(
        "--dataset-id",
        type=resolve_dataset_id,
        help="Identifier to assign to the ingested dataset (required for Codebook format)",
    )
    load_parser.add_argument(
        "--dataset-name",
        help="Human-readable name for the dataset",
    )
    load_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output ingestion totals as JSON",
    )
    load_parser.add_argument(
        "--validate",
        action="store_true",
        help="Check the file against its official XSD first, and refuse to load it if invalid",
    )
    load_parser.set_defaults(handler=_load_command)

    # detect command
    detect_parser = subcommands.add_parser(
        "detect",
        help="Detect the DDI format of an XML file without loading it",
    )
    detect_parser.add_argument(
        "xml_path",
        type=resolve_xml_path,
        help="Filesystem path to the DDI XML input",
    )
    detect_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output detection result as JSON",
    )
    detect_parser.set_defaults(handler=_detect_command)

    # export command -- writes a file instead of loading a database. Needs no
    # Neo4j connection, so it deliberately carries none of the connection
    # options; RDF formats need the optional ``[rdf]`` extra.
    export_parser = subcommands.add_parser(
        "export",
        help=(
            "Export a DDI file to RDF, JSON, or CSV without touching Neo4j "
            "(RDF formats need the [rdf] extra)"
        ),
    )
    export_parser.add_argument(
        "xml_path",
        type=resolve_xml_path,
        help="Path to a DDI Codebook, DDI-L FragmentInstance, or DDI-CDI file",
    )
    export_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output file, or output directory when --format csv",
    )
    export_parser.add_argument(
        "--format",
        choices=list(export_formats),
        default="turtle",
        help="Output format (default: turtle)",
    )
    export_parser.add_argument(
        "--base-uri",
        dest="base_uri",
        default=None,
        help=(
            "IRI stem for subjects with no DDI URN. Recommended when "
            "publishing; defaults to a urn:ddigraph: identifier rather than "
            "inventing an http:// domain"
        ),
    )
    export_parser.add_argument(
        "--dataset-id",
        dest="dataset_id",
        type=resolve_dataset_id,
        default=None,
        help="Dataset identifier for codebook input (default: the file stem)",
    )
    export_parser.add_argument(
        "--dataset-name",
        dest="dataset_name",
        default=None,
        help="Human-readable dataset name for codebook input",
    )
    export_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit the result summary as JSON",
    )
    export_parser.add_argument(
        "--validate",
        action="store_true",
        help="Check the input against its official XSD first, and refuse it if invalid",
    )
    export_parser.set_defaults(handler=_export_command)

    # shapes command -- derives SHACL from DDISchema. It takes no input
    # document because the shapes describe the vocabulary, not one file.
    shapes_parser = subcommands.add_parser(
        "shapes",
        help="Write SHACL shapes for the DDI vocabulary (needs the [shacl] extra)",
    )
    shapes_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output file for the shapes graph",
    )
    shapes_parser.add_argument(
        "--flavor",
        choices=list(shacl_flavors),
        default=None,
        help=(
            "Restrict shapes to one DDI flavor. Recommended when validating "
            "real data, since a document has exactly one flavor and the "
            "flavors key some shared labels differently"
        ),
    )
    shapes_parser.add_argument(
        "--format",
        choices=list(rdf_formats),
        default="turtle",
        help="Serialisation for the shapes graph (default: turtle)",
    )
    shapes_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit the result summary as JSON",
    )
    shapes_parser.set_defaults(handler=_shapes_command)

    # preview command -- answers "what is actually in this file?" without a
    # database and without an optional extra.
    preview_parser = subcommands.add_parser(
        "preview",
        help="Summarise a DDI file's graph shape as text, Mermaid, or a self-contained HTML page",
    )
    preview_parser.add_argument(
        "xml_path",
        type=resolve_xml_path,
        help="Path to a DDI Codebook, DDI-L FragmentInstance, or DDI-CDI file",
    )
    preview_parser.add_argument(
        "--format",
        choices=list(preview_formats),
        default="text",
        help="Output format (default: text)",
    )
    preview_parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Write to a file instead of stdout",
    )
    preview_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Show up to N example nodes per type (default: 0, counts only)",
    )
    preview_parser.add_argument(
        "--dataset-id",
        dest="dataset_id",
        type=resolve_dataset_id,
        default=None,
        help="Dataset identifier for codebook input (default: the file stem)",
    )
    preview_parser.set_defaults(handler=_preview_command)

    # validate command -- checks a file against the official DDI XSDs that
    # ship with the package. Opt-in rather than automatic: published DDI is
    # frequently imperfect, and refusing to read a file that parses and
    # loads perfectly well would make the tool less useful, not more.
    validate_parser = subcommands.add_parser(
        "validate",
        help="Validate a DDI file against its official XSD",
    )
    validate_parser.add_argument(
        "xml_path",
        type=resolve_xml_path,
        help="Path to a DDI Codebook, DDI-L FragmentInstance, or DDI-CDI file",
    )
    validate_parser.add_argument(
        "--flavor",
        choices=["auto", "codebook", "lifecycle", "cdi"],
        default="auto",
        help="Force a DDI flavor instead of detecting it (default: auto)",
    )
    validate_parser.add_argument(
        "--max-issues",
        dest="max_issues",
        type=int,
        default=20,
        help="Report at most N issues; 0 reports all of them (default: 20)",
    )
    validate_parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Print the result as JSON",
    )
    validate_parser.set_defaults(handler=_validate_command)

    # bootstrap command -- the single schema-creation verb. It replaced
    # ``ensure-schema`` and ``ensure-fragment-schema``, which were deprecated
    # in 0.4.0rc1 and removed in 0.5.0; fragments are included by default.
    bootstrap_parser = subcommands.add_parser(
        "bootstrap",
        help=(
            "Create indexes and constraints. Includes DDI-L Lifecycle by "
            "default; use --no-include-fragments for codebook-only."
        ),
    )
    _add_connection_options(bootstrap_parser)
    bootstrap_parser.add_argument(
        "--include-fragments",
        dest="include_fragments",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Include DDI-L FragmentInstance schema (default: enabled)",
    )
    bootstrap_parser.add_argument(
        "--include-cdi",
        dest="include_cdi",
        default=False,
        action=argparse.BooleanOptionalAction,
        help=(
            "Include DDI-CDI 1.0 schema (default: disabled -- no shipped "
            "writer creates DDI-CDI nodes)"
        ),
    )
    bootstrap_parser.set_defaults(handler=_ensure_schema_command)

    # version command -- prints the installed ddigraph version.
    version_parser = subcommands.add_parser(
        "version",
        help="Print the installed ddigraph version and exit.",
    )
    version_parser.set_defaults(handler=_version_command)

    return parser


def _version_command(args: argparse.Namespace, settings: Settings) -> None:
    """Print the installed package version."""
    from ddigraph import __version__

    print(__version__)


def main(argv: Sequence[str] | None = None) -> None:
    """CLI entrypoint configured via ``[project.scripts]``.

    Args:
        argv: Optional argument vector. When ``None`` (the default), argparse
            consumes ``sys.argv[1:]``. Passed explicitly by tests and by
            programmatic callers.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = _settings_from_args(args)
    configure_logging(settings)

    # Validate required args for codebook format
    if getattr(args, "command", None) == "load":
        ddi_format = getattr(args, "format", "auto")
        if ddi_format == "auto":
            ddi_format = detect_ddi_format(args.xml_path)

        if ddi_format == "codebook" and not getattr(args, "dataset_id", None):
            parser.error("--dataset-id is required for DDI Codebook format")

    result = args.handler(args, settings)
    if inspect.iscoroutine(result):
        asyncio.run(result)


__all__ = ["AsyncGraphDatabase", "GraphDatabase", "build_parser", "main"]

"""Configuration management for ddigraph."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment or .env files.

    Environment variables can use either the DDIGRAPH_ prefix (preferred) or the legacy
    NEO4DDI_ prefix for backward compatibility.
    """

    model_config = SettingsConfigDict(
        env_prefix="DDIGRAPH_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        validation_alias=AliasChoices("NEO4J_URI", "DDIGRAPH_NEO4J_URI"),
    )
    neo4j_user: str = Field(
        default="neo4j",
        validation_alias=AliasChoices(
            "NEO4J_USER", "NEO4J_USERNAME", "DDIGRAPH_NEO4J_USER"
        ),
    )
    neo4j_password: SecretStr = Field(
        default=SecretStr("password"),
        repr=False,
        validation_alias=AliasChoices("NEO4J_PASSWORD", "DDIGRAPH_NEO4J_PASSWORD"),
    )
    neo4j_database: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_DATABASE", "DDIGRAPH_NEO4J_DATABASE"),
    )
    max_connection_pool_size: int | None = Field(
        default=None,
        gt=0,
        description="Maximum number of connections the driver maintains in its pool",
    )
    connection_timeout: float | None = Field(
        default=None,
        gt=0,
        description="Seconds to wait for establishing a new connection before timing out",
    )
    max_connection_lifetime: float | None = Field(
        default=None,
        gt=0,
        description="Seconds a connection is kept alive in the pool before being recycled",
    )
    session_timeout: float | None = Field(
        default=None,
        gt=0,
        description="Seconds to keep a Neo4j session open before timing out",
    )
    transaction_timeout: float | None = Field(
        default=None,
        gt=0,
        description="Server-side timeout in seconds for individual write transactions",
    )
    encrypted: bool | None = Field(
        default=None,
        description=("Whether to require encrypted Neo4j driver connections (TLS)"),
    )
    verify_hostname: bool | None = Field(
        default=None,
        description="Whether to verify the Neo4j server hostname in TLS certificates",
    )
    trusted_certificates: str | None = Field(
        default=None,
        description=(
            "Trusted certificates policy (e.g., TRUST_ALL_CERTIFICATES or system CA selection)"
        ),
    )
    trusted_certificates_file: str | None = Field(
        default=None,
        description="PEM file containing certificates trusted by the Neo4j driver",
    )

    # Ingestion tuning
    queue_maxsize: int = Field(
        default=2,
        gt=0,
        description="Maximum number of batches waiting to be flushed before applying back-pressure",
    )
    chunk_size: int = Field(
        default=200,
        gt=0,
        description=(
            "Total parsed records (across all entity types) to collect before enqueuing a batch"
        ),
    )
    writer_concurrency: int = Field(
        default=1,
        gt=0,
        description="Number of concurrent writer tasks flushing batches to the graph backend",
    )
    batch_metrics: bool = Field(
        default=False,
        description="Emit per-batch observability metrics such as duration and size",
    )
    strict_parsing: bool = Field(
        default=False,
        description=(
            "Raise XML syntax errors instead of attempting recovery; when false, ingestion logs "
            "recoverable parse issues"
        ),
    )
    dry_run: bool = Field(
        default=False,
        description=(
            "Parse and validate DDI batches without writing to the graph; useful for validation"
        ),
    )
    replace: bool = Field(
        default=False,
        description=(
            "Purge existing nodes and relationships for a dataset before loading new content"
        ),
    )
    write_retry_attempts: int = Field(
        default=3,
        ge=1,
        description=("Maximum attempts for transient write failures (including the first attempt)"),
    )
    write_retry_base_delay: float = Field(
        default=0.5,
        ge=0,
        description="Base delay in seconds for exponential backoff on transient write retries",
    )
    write_retry_jitter: float = Field(
        default=0.25,
        ge=0,
        description="Maximum random jitter in seconds added to transient write retry delays",
    )

    # Observability
    log_level: str = Field(default="INFO", description="Python logging level")
    metrics_namespace: str = Field(default="ddigraph", description="Prefix for metrics emission")

    def model_post_init(self, _ctx: object) -> None:
        """Warn callers that still set legacy ``NEO4DDI_*`` environment variables."""
        legacy = sorted(name for name in os.environ if name.startswith("NEO4DDI_"))
        if not legacy:
            return
        import warnings

        warnings.warn(
            "``NEO4DDI_*`` environment variables are deprecated and ignored "
            f"as of 0.4.0; rename to ``DDIGRAPH_*``. Affected: {legacy}. "
            "The recognition shim was removed; legacy callers must update.",
            DeprecationWarning,
            stacklevel=3,
        )


def resolve_credentials_source(
    env: Mapping[str, str] | None = None, *, cli_overrides: bool = False
) -> str:
    """Describe which source supplied connection credentials.

    Args:
        env: Optional environment mapping; defaults to :data:`os.environ`.
        cli_overrides: True when credentials were provided via CLI flags,
            which take precedence over environment variables.

    Returns:
        A human-readable description of which environment variables supplied
        the connection credentials. Recognises the canonical ``DDIGRAPH_*``
        prefix and the legacy ``NEO4J_*`` industry prefix. When CLI
        arguments supply the credentials, that is surfaced explicitly.

    Note:
        The legacy ``NEO4DDI_*`` prefix was retired in 0.4.0. If any
        ``NEO4DDI_*`` variables are still set in the environment they are
        ignored by ``Settings`` and a ``DeprecationWarning`` is emitted.
    """
    env_vars = env or os.environ
    ddigraph_vars = {"DDIGRAPH_NEO4J_URI", "DDIGRAPH_NEO4J_USER", "DDIGRAPH_NEO4J_PASSWORD"}
    legacy_vars = {"NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"}

    if cli_overrides:
        return "CLI arguments (--neo4j-*)"

    ddigraph_present = any(var in env_vars for var in ddigraph_vars)
    legacy_present = any(var in env_vars for var in legacy_vars)

    if ddigraph_present:
        return "DDIGRAPH_* variables"
    if legacy_present:
        return "legacy NEO4J_* variables"
    return "defaults (no DDIGRAPH_* or NEO4J_* overrides detected)"


__all__ = ["Settings", "resolve_credentials_source"]

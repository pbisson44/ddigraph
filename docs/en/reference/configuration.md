# Configuration Reference

ddigraph uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
for configuration management. Every setting can be provided through environment variables,
a `.env` file, CLI flags, or directly in Python code.

## Configuration Precedence

Settings are resolved in the following order (highest priority first):

1. **CLI flags** -- `--neo4j-uri`, `--chunk-size`, etc.
2. **Environment variables** -- `DDIGRAPH_NEO4J_URI`, `DDIGRAPH_CHUNK_SIZE`, etc.
3. **`.env` file** -- automatically loaded from the working directory
4. **Defaults** -- built-in defaults defined in the `Settings` class

!!! info "Legacy prefixes"
    For backward compatibility, ddigraph also recognizes the `NEO4DDI_` and bare `NEO4J_` prefixes
    for connection variables. The `DDIGRAPH_` prefix is preferred and takes precedence when
    multiple prefixes are present.

---

## Connection Settings

| Environment Variable | CLI Flag | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `DDIGRAPH_NEO4J_URI` | `--neo4j-uri` | `str` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `DDIGRAPH_NEO4J_USER` | `--neo4j-user` | `str` | `neo4j` | Neo4j username |
| `DDIGRAPH_NEO4J_PASSWORD` | `--neo4j-password` | `SecretStr` | `password` | Neo4j password |
| `DDIGRAPH_NEO4J_DATABASE` | `--neo4j-database` | `str` | `neo4j` | Target database name |

!!! warning "Password handling"
    `DDIGRAPH_NEO4J_PASSWORD` is stored as a `SecretStr` in pydantic. It will never appear in
    `repr()` output or logs. To retrieve the plain-text value in code, call
    `settings.neo4j_password.get_secret_value()`.

---

## Driver Pooling

These settings control the Neo4j driver connection pool. All are optional; when unset, the
Neo4j driver uses its own defaults.

| Environment Variable | CLI Flag | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `DDIGRAPH_MAX_CONNECTION_POOL_SIZE` | `--max-connection-pool-size` | `int` | driver default | Maximum connections in the pool |
| `DDIGRAPH_CONNECTION_TIMEOUT` | `--connection-timeout` | `float` | driver default | Seconds to wait for a new connection |
| `DDIGRAPH_MAX_CONNECTION_LIFETIME` | `--max-connection-lifetime` | `float` | driver default | Seconds before recycling a pooled connection |
| `DDIGRAPH_SESSION_TIMEOUT` | `--session-timeout` | `float` | driver default | Session lifetime in seconds |
| `DDIGRAPH_TRANSACTION_TIMEOUT` | `--transaction-timeout` | `float` | driver default | Server-side transaction timeout in seconds |

---

## TLS Options

| Environment Variable | CLI Flag | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `DDIGRAPH_ENCRYPTED` | `--encrypted` / `--no-encrypted` | `bool` | `None` | Require TLS connections |
| `DDIGRAPH_VERIFY_HOSTNAME` | `--verify-hostname` / `--no-verify-hostname` | `bool` | `None` | Verify server hostname in TLS certificates |
| `DDIGRAPH_TRUSTED_CERTIFICATES` | `--trusted-certificates` | `str` | `None` | Trust policy (e.g., `TRUST_ALL_CERTIFICATES`) |
| `DDIGRAPH_TRUSTED_CERTIFICATES_FILE` | `--trusted-certificates-file` | `str` | `None` | Path to PEM bundle with trusted certificates |

!!! tip "Neo4j Aura (cloud)"
    For Neo4j Aura, use the `neo4j+s://` URI scheme. This enables TLS automatically:

    ```bash
    export DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
    ```

    You typically do not need `--encrypted` or `--trusted-certificates` when using the `+s` scheme.

### Self-Signed Certificates

```bash
DDIGRAPH_ENCRYPTED=true \
DDIGRAPH_TRUSTED_CERTIFICATES_FILE=/etc/ssl/certs/private-ca.pem \
  ddigraph load /path/to/data.xml --dataset-id demo
```

---

## Ingestion Tuning

| Environment Variable | CLI Flag | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `DDIGRAPH_CHUNK_SIZE` | `--chunk-size` | `int` | `200` | Records per batch |
| `DDIGRAPH_QUEUE_MAXSIZE` | `--queue-maxsize` | `int` | `2` | Max batches in async queue before back-pressure (Codebook only) |
| `DDIGRAPH_WRITER_CONCURRENCY` | `--writer-concurrency` | `int` | `1` | Concurrent writer tasks flushing to the backend |
| `DDIGRAPH_BATCH_METRICS` | `--batch-metrics` / `--no-batch-metrics` | `bool` | `false` | Emit per-batch observability metrics |
| `DDIGRAPH_STRICT_PARSING` | `--strict-parsing` / `--no-strict-parsing` | `bool` | `false` | Fail on XML syntax errors instead of recovering |
| `DDIGRAPH_DRY_RUN` | `--dry-run` / `--validate-only` | `bool` | `false` | Parse and validate without writing to the graph |
| `DDIGRAPH_REPLACE` | `--replace` / `--no-replace` | `bool` | `false` | Purge existing dataset data before loading |

!!! note "Boolean environment variables"
    Boolean settings accept truthy/falsy strings: `true`/`false`, `1`/`0`, `yes`/`no`.

---

## Retry Settings

ddigraph uses exponential backoff with jitter for transient write failures.

| Environment Variable | CLI Flag | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `DDIGRAPH_WRITE_RETRY_ATTEMPTS` | `--write-retry-attempts` | `int` | `3` | Total retry attempts (including first attempt) |
| `DDIGRAPH_WRITE_RETRY_BASE_DELAY` | `--write-retry-base-delay` | `float` | `0.5` | Base delay in seconds for exponential backoff |
| `DDIGRAPH_WRITE_RETRY_JITTER` | `--write-retry-jitter` | `float` | `0.25` | Maximum random jitter in seconds added to delay |

The effective delay for attempt *n* is:

```text
delay = base_delay * (2 ^ n) + random(0, jitter)
```

---

## Logging and Observability

| Environment Variable | CLI Flag | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `DDIGRAPH_LOG_LEVEL` | `--log-level` | `str` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `DDIGRAPH_METRICS_NAMESPACE` | `--metrics-namespace` | `str` | `ddigraph` | Prefix for emitted metrics names |

---

## `.env` File Support

pydantic-settings automatically loads a `.env` file from the current working directory. Create
a `.env` file to avoid exporting variables in every shell session:

```bash title=".env"
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=my-secret-password
DDIGRAPH_NEO4J_DATABASE=neo4j
DDIGRAPH_CHUNK_SIZE=500
DDIGRAPH_LOG_LEVEL=DEBUG
```

!!! warning "Security"
    Never commit `.env` files containing passwords to version control. Add `.env` to your
    `.gitignore` file.

---

## Using the Settings Class in Python

The `Settings` class can be used directly in Python code for programmatic configuration:

```python
from ddigraph.config import Settings

# Load from environment / .env file (default behavior)
settings = Settings()

# Override specific values
settings = Settings(
    neo4j_uri="bolt://production:7687",
    neo4j_password="prod-password",
    chunk_size=1000,
    write_retry_attempts=5,
)

# Access values
print(settings.neo4j_uri)                          # "bolt://production:7687"
print(settings.neo4j_password.get_secret_value())   # "prod-password"
print(settings.chunk_size)                          # 1000
```

### Passing Settings to Loaders

```python
import asyncio
from neo4j import AsyncGraphDatabase
from ddigraph.config import Settings
from ddigraph.ingest.loader import DDILoader
from ddigraph.ingest.fragment_loader import DDIFragmentLoader

settings = Settings(chunk_size=500, write_retry_attempts=5)

driver = AsyncGraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
)

# DDI Codebook
loader = DDILoader(driver, settings=settings)

# DDI-L FragmentInstance
fragment_loader = DDIFragmentLoader(driver, settings=settings)
```

### Checking Credential Sources

```python
from ddigraph.config import resolve_credentials_source

# Determine where connection credentials came from
source = resolve_credentials_source()
print(source)
# Possible outputs:
#   "DDIGRAPH_* variables"
#   "legacy NEO4DDI_* variables"
#   "legacy NEO4J_* variables"
#   "defaults (no DDIGRAPH_*, NEO4DDI_*, or NEO4J_* overrides detected)"
```

---

## Complete Example Configurations

### Local Development

```bash title=".env"
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=password
DDIGRAPH_LOG_LEVEL=DEBUG
DDIGRAPH_BATCH_METRICS=true
```

### High-Throughput Production (Codebook)

```bash title=".env"
DDIGRAPH_NEO4J_URI=bolt://neo4j-cluster:7687
DDIGRAPH_NEO4J_USER=ingestion_user
DDIGRAPH_NEO4J_PASSWORD=strong-password
DDIGRAPH_CHUNK_SIZE=1000
DDIGRAPH_QUEUE_MAXSIZE=4
DDIGRAPH_WRITER_CONCURRENCY=4
DDIGRAPH_MAX_CONNECTION_POOL_SIZE=10
DDIGRAPH_TRANSACTION_TIMEOUT=60
DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
DDIGRAPH_WRITE_RETRY_BASE_DELAY=1.0
DDIGRAPH_WRITE_RETRY_JITTER=0.5
DDIGRAPH_LOG_LEVEL=INFO
DDIGRAPH_BATCH_METRICS=true
```

### Neo4j Aura (Cloud)

```bash title=".env"
DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=aura-password
DDIGRAPH_CHUNK_SIZE=200
DDIGRAPH_CONNECTION_TIMEOUT=10
DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
DDIGRAPH_WRITE_RETRY_BASE_DELAY=2.0
```

### Memory-Constrained Environment

```bash title=".env"
DDIGRAPH_NEO4J_URI=bolt://localhost:7687
DDIGRAPH_NEO4J_USER=neo4j
DDIGRAPH_NEO4J_PASSWORD=password
DDIGRAPH_CHUNK_SIZE=50
DDIGRAPH_QUEUE_MAXSIZE=1
DDIGRAPH_WRITER_CONCURRENCY=1
```

### CI/CD Pipeline

```bash
# Pass everything via environment variables (no .env file)
DDIGRAPH_NEO4J_URI=bolt://ci-neo4j:7687 \
DDIGRAPH_NEO4J_PASSWORD="${NEO4J_CI_PASSWORD}" \
DDIGRAPH_DRY_RUN=true \
  ddigraph load /data/survey.xml --dataset-id ci-test --json
```

---

## All Settings at a Glance

| Setting | Env Variable | CLI Flag | Default |
| --- | --- | --- | --- |
| Neo4j URI | `DDIGRAPH_NEO4J_URI` | `--neo4j-uri` | `bolt://localhost:7687` |
| Neo4j user | `DDIGRAPH_NEO4J_USER` | `--neo4j-user` | `neo4j` |
| Neo4j password | `DDIGRAPH_NEO4J_PASSWORD` | `--neo4j-password` | `password` |
| Neo4j database | `DDIGRAPH_NEO4J_DATABASE` | `--neo4j-database` | `neo4j` |
| Pool size | `DDIGRAPH_MAX_CONNECTION_POOL_SIZE` | `--max-connection-pool-size` | driver default |
| Connect timeout | `DDIGRAPH_CONNECTION_TIMEOUT` | `--connection-timeout` | driver default |
| Connection lifetime | `DDIGRAPH_MAX_CONNECTION_LIFETIME` | `--max-connection-lifetime` | driver default |
| Session timeout | `DDIGRAPH_SESSION_TIMEOUT` | `--session-timeout` | driver default |
| Transaction timeout | `DDIGRAPH_TRANSACTION_TIMEOUT` | `--transaction-timeout` | driver default |
| Encrypted | `DDIGRAPH_ENCRYPTED` | `--encrypted` | `None` |
| Verify hostname | `DDIGRAPH_VERIFY_HOSTNAME` | `--verify-hostname` | `None` |
| Trusted certs | `DDIGRAPH_TRUSTED_CERTIFICATES` | `--trusted-certificates` | `None` |
| Trusted certs file | `DDIGRAPH_TRUSTED_CERTIFICATES_FILE` | `--trusted-certificates-file` | `None` |
| Chunk size | `DDIGRAPH_CHUNK_SIZE` | `--chunk-size` | `200` |
| Queue max size | `DDIGRAPH_QUEUE_MAXSIZE` | `--queue-maxsize` | `2` |
| Writer concurrency | `DDIGRAPH_WRITER_CONCURRENCY` | `--writer-concurrency` | `1` |
| Batch metrics | `DDIGRAPH_BATCH_METRICS` | `--batch-metrics` | `false` |
| Strict parsing | `DDIGRAPH_STRICT_PARSING` | `--strict-parsing` | `false` |
| Dry run | `DDIGRAPH_DRY_RUN` | `--dry-run` | `false` |
| Replace | `DDIGRAPH_REPLACE` | `--replace` | `false` |
| Retry attempts | `DDIGRAPH_WRITE_RETRY_ATTEMPTS` | `--write-retry-attempts` | `3` |
| Retry base delay | `DDIGRAPH_WRITE_RETRY_BASE_DELAY` | `--write-retry-base-delay` | `0.5` |
| Retry jitter | `DDIGRAPH_WRITE_RETRY_JITTER` | `--write-retry-jitter` | `0.25` |
| Log level | `DDIGRAPH_LOG_LEVEL` | `--log-level` | `INFO` |
| Metrics namespace | `DDIGRAPH_METRICS_NAMESPACE` | `--metrics-namespace` | `ddigraph` |

---

See [CLI Reference](cli.md) for command-specific options and [Performance Tuning](../advanced/tuning.md) for
recommendations on choosing optimal values.

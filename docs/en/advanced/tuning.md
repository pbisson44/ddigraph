# Performance Tuning

This guide covers tuning parameters for both DDI Codebook and DDI-L FragmentInstance ingestion.

## Quick Reference

| Parameter | Default | DDI Codebook | DDI-L FragmentInstance |
| ----------- | --------- | -------------- | ------------------------ |
| `chunk_size` | 200 | Records per batch | Fragments per batch |
| `queue_maxsize` | 2 | Batches buffered | N/A (sync parsing) |
| `writer_concurrency` | 4 | Parallel writers | N/A (sequential batches) |
| `write_retry_attempts` | 3 | Retry count | Retry count |

## Batch Size (`DDIGRAPH_CHUNK_SIZE`)

Controls how many records/fragments are grouped before writing to Neo4j.

### DDI Codebook

Larger batches reduce transaction overhead but increase per-transaction latency. The threshold
counts all parsed record types together (variables, questions, categories, etc.):

```bash
# Larger batches for high-throughput ingestion
export DDIGRAPH_CHUNK_SIZE=1000

# Smaller batches for memory-constrained environments
export DDIGRAPH_CHUNK_SIZE=100
```

For codebooks with mixed metadata and variables, 500-1000 combined records keeps writes efficient.

### DDI-L FragmentInstance

Fragments are batched by element type before UNWIND writes:

```bash
# For large FragmentInstance files (>5000 fragments)
ddigraph load questionnaire.xml --chunk-size 500

# For smaller files or debugging
ddigraph load questionnaire.xml --chunk-size 50
```

**Recommendation**: Start with 200-300 for FragmentInstance files and adjust based on memory
and write latency.

## Queue Size (`DDIGRAPH_QUEUE_MAXSIZE`)

*Applies to DDI Codebook only.*

Controls back-pressure between parsing and writing by capping queued `DDIBatch` objects:

```bash
# Keep writer busy on fast systems
export DDIGRAPH_QUEUE_MAXSIZE=4

# Reduce memory usage
export DDIGRAPH_QUEUE_MAXSIZE=1
```

The FragmentInstance loader uses synchronous batch parsing, so queue size doesn't apply.

## Writer Concurrency (`DDIGRAPH_WRITER_CONCURRENCY`)

*Applies to DDI Codebook only.*

Sets how many batches flush to Neo4j in parallel:

```bash
# Higher concurrency for fast Neo4j clusters
export DDIGRAPH_WRITER_CONCURRENCY=4

# Single writer for debugging or constrained connections
export DDIGRAPH_WRITER_CONCURRENCY=1
```

Ensure `max_connection_pool_size` >= `writer_concurrency` to avoid writer starvation.

## Driver Pooling

### Connection Pool Size

```bash
# Match or exceed writer concurrency
export DDIGRAPH_MAX_CONNECTION_POOL_SIZE=10
export DDIGRAPH_WRITER_CONCURRENCY=4
```

### Timeouts

| Setting | Purpose | Recommendation |
| --------- | --------- | ---------------- |
| `connection_timeout` | Time to establish connection | 5-30s |
| `max_connection_lifetime` | Recycle idle connections | 300-3600s |
| `session_timeout` | Session lifetime | Match transaction needs |
| `transaction_timeout` | Server-side transaction limit | 30-120s |

```bash
# Fast failure on connection issues
export DDIGRAPH_CONNECTION_TIMEOUT=5

# Long-running transactions for large batches
export DDIGRAPH_TRANSACTION_TIMEOUT=60
```

## Retry Configuration

Both loaders support exponential backoff with jitter for transient failures:

```bash
# Aggressive retries for unstable networks
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
export DDIGRAPH_WRITE_RETRY_BASE_DELAY=1.0
export DDIGRAPH_WRITE_RETRY_JITTER=0.5

# Fast failure for stable environments
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=2
export DDIGRAPH_WRITE_RETRY_BASE_DELAY=0.1
export DDIGRAPH_WRITE_RETRY_JITTER=0
```

CLI equivalent:

```bash
ddigraph load file.xml --dataset-id demo \
  --write-retry-attempts 5 \
  --write-retry-base-delay 1.0 \
  --write-retry-jitter 0.5
```

## Dry Run and Replace

### Validation Mode

Parse and plan without writing:

```bash
# Validate before production ingestion
ddigraph load file.xml --dataset-id demo --dry-run

# Or via environment
DDIGRAPH_DRY_RUN=true ddigraph load file.xml --dataset-id demo
```

### Replace Mode

Purge existing data before loading:

```bash
# Re-ingest a dataset from scratch
ddigraph load file.xml --dataset-id demo --replace

# Replace is skipped during dry-run
ddigraph load file.xml --dataset-id demo --dry-run --replace  # No purge occurs
```

## Format-Specific Tuning

### DDI-C

Optimize for the producer/consumer pipeline:

```bash
# High-throughput configuration
export DDIGRAPH_CHUNK_SIZE=1000
export DDIGRAPH_QUEUE_MAXSIZE=4
export DDIGRAPH_WRITER_CONCURRENCY=4
export DDIGRAPH_MAX_CONNECTION_POOL_SIZE=10
```

### DDI-L Fragment Inst

Optimize for batched UNWIND writes:

```bash
# Large FragmentInstance files
export DDIGRAPH_CHUNK_SIZE=500
export DDIGRAPH_TRANSACTION_TIMEOUT=60
# Memory-constrained environments
export DDIGRAPH_CHUNK_SIZE=100
```

## Monitoring

Enable batch metrics for visibility:

```bash
ddigraph load file.xml --dataset-id demo --batch-metrics
```

This emits timing and count metrics that can be captured by observability systems.

### Useful Metrics

| Metric | Description |
| -------- | ------------- |
| `batch_duration_seconds` | Time per batch write |
| `batch_size` | Records/fragments per batch |
| `batches` | Total batches processed |
| `batch_write_retries` | Retry count |

## Worked Examples

### Large DDI Codebook (10K+ variables)

```bash
export DDIGRAPH_NEO4J_URI=bolt://cluster:7687
export DDIGRAPH_MAX_CONNECTION_POOL_SIZE=20
export DDIGRAPH_CHUNK_SIZE=1000
export DDIGRAPH_QUEUE_MAXSIZE=4
export DDIGRAPH_WRITER_CONCURRENCY=4
export DDIGRAPH_TRANSACTION_TIMEOUT=60
ddigraph bootstrap
ddigraph load large_codebook.xml --dataset-id survey2024 --batch-metrics
```

### Large DDI-L FragmentInstance (5K+ fragments)

```bash
export DDIGRAPH_NEO4J_URI=bolt://cluster:7687
export DDIGRAPH_CHUNK_SIZE=500
export DDIGRAPH_TRANSACTION_TIMEOUT=60
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
ddigraph bootstrap
ddigraph load large_questionnaire.xml --batch-metrics --json
```

### AuraDB Cloud Instance

```bash
export DDIGRAPH_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
export DDIGRAPH_ENCRYPTED=true
export DDIGRAPH_CONNECTION_TIMEOUT=10
export DDIGRAPH_CHUNK_SIZE=200  # Smaller batches for cloud latency
export DDIGRAPH_WRITE_RETRY_ATTEMPTS=5
export DDIGRAPH_WRITE_RETRY_BASE_DELAY=2.0
ddigraph bootstrap
ddigraph load file.xml --dataset-id demo
```

### Memory-Constrained Environment

```bash
export DDIGRAPH_CHUNK_SIZE=50
export DDIGRAPH_QUEUE_MAXSIZE=1
export DDIGRAPH_WRITER_CONCURRENCY=1
ddigraph load file.xml --dataset-id demo
```

## Performance Comparison

### DDI-L FragmentInstance Performance

For `Ireland_LabourSurvey.xml` (148K lines, 2,762 fragments):

| Metric | Value |
| -------- | -------- |
| Neo4j queries | ~30 |
| Memory pattern | O(chunk_size) |
| Async operations | All writes |
| Queries per fragment | ~0.01 |

The low query count comes from UNWIND batching by fragment type.

## Troubleshooting

### Slow Ingestion

1. Increase `chunk_size` to reduce transaction overhead
2. Increase `writer_concurrency` (Codebook) if pool has capacity
3. Check Neo4j server resources and indexes

### Memory Issues

1. Decrease `chunk_size` to reduce in-flight data
2. Decrease `queue_maxsize` (Codebook) to limit buffering
3. Ensure XML parsing uses streaming (`iterparse`)

### Connection Errors

1. Increase `connection_timeout` for slow networks
2. Increase `write_retry_attempts` for transient failures
3. Verify TLS settings for cloud instances

### Transaction Timeouts

1. Decrease `chunk_size` to reduce per-transaction work
2. Increase `transaction_timeout` for large batches
3. Check Neo4j server configuration

See [Architecture](../user-guide/architecture.md) for design context and [CLI Reference](../reference/cli.md) for all options.

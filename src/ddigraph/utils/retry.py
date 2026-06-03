"""Retry utilities for transient write failures."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

from neo4j.exceptions import TransientError

logger = logging.getLogger(__name__)


async def retry_transient(
    fn: Callable[[], Awaitable[Any]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    jitter: float = 0.25,
    retry_metric: str = "batch_write_retries",
    log_prefix: str = "Batch write",
    log_extra: dict[str, object] | None = None,
    metrics: Any | None = None,
) -> None:
    """Execute an async callable with exponential-backoff retry on TransientError.

    Args:
        fn: Zero-argument async callable to execute.
        attempts: Maximum number of attempts (including the first).
        base_delay: Base delay in seconds for exponential backoff.
        jitter: Maximum random jitter in seconds added to each delay.
        retry_metric: Metric key to increment on each retry.
        log_prefix: Prefix for log messages to identify the caller context.
        log_extra: Extra fields to include in log records.
        metrics: Optional metrics emitter supporting ``increment()``.

    Raises:
        TransientError: When all retry attempts are exhausted.
    """
    attempts = max(1, attempts)
    extra = dict(log_extra) if log_extra else {}

    for attempt in range(1, attempts + 1):
        try:
            await fn()
            return
        except TransientError:
            if attempt >= attempts:
                logger.exception(
                    "%s failed after retries",
                    log_prefix,
                    extra={**extra, "attempts": attempt},
                )
                raise

            delay = base_delay * (2 ** (attempt - 1))
            if jitter:
                delay += random.uniform(0, jitter)

            if metrics is not None:
                metrics.increment(retry_metric)
            logger.warning(
                "Retrying %s after transient error",
                log_prefix.lower(),
                extra={
                    **extra,
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "delay_s": round(delay, 3),
                },
            )
            await asyncio.sleep(delay)


__all__ = ["retry_transient"]

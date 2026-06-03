"""Chunking and serialization helpers for streaming workflows."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict
from typing import Any, cast


def chunked[T](iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield fixed-size chunks from an iterable.

    Args:
        iterable: Source iterable.
        size: Desired chunk size (must be > 0).
    """
    if size <= 0:
        raise ValueError("chunk size must be positive")

    batch: list[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def window[T](seq: Sequence[T], size: int) -> list[list[T]]:
    """Convenience wrapper for testing chunk boundaries."""
    return list(chunked(seq, size))


def as_dicts(records: Sequence[object]) -> list[dict[str, object]]:
    """Convert a sequence of dataclass instances to plain dictionaries.

    Args:
        records: Dataclass instances to convert.

    Returns:
        List of plain dictionaries suitable for Cypher parameters or JSON
        serialization.
    """
    return [asdict(cast(Any, record)) for record in records]


__all__ = ["as_dicts", "chunked", "window"]

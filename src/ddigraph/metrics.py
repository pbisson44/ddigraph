"""Lightweight metrics hooks for observability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class MetricsEmitter(Protocol):
    """Minimal protocol for emitting counters and timings."""

    def increment(self, name: str, value: int = 1) -> None: ...

    """Increment the metric counter."""

    def observe(self, name: str, value: float) -> None: ...

    """Record an observed metric value."""


@dataclass
class NullMetrics:
    """No-op metrics emitter used by default."""

    namespace: str = "ddigraph"

    def _full_name(self, name: str) -> str:
        """Construct the full metric name."""
        return f"{self.namespace}.{name}" if self.namespace else name

    def increment(self, name: str, value: int = 1) -> None:
        """Increment the metric counter."""  # pragma: no cover - trivial
        _ = self._full_name(name)

    def observe(self, name: str, value: float) -> None:  # pragma: no cover - trivial
        """Record an observed metric value."""  # pragma: no cover - trivial
        _ = self._full_name(name)


__all__ = ["MetricsEmitter", "NullMetrics"]

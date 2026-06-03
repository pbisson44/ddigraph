"""Logging helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from .config import Settings

DEFAULT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(settings: Settings | None = None) -> None:
    """Configure application logging.

    Args:
        settings: Optional runtime settings that provide the log level and
            metrics namespace; defaults to ``Settings()`` when omitted.
    """
    effective_settings = settings or Settings()
    level = logging.getLevelName(effective_settings.log_level)
    logging.basicConfig(level=level, format=DEFAULT_FORMAT)
    logging.getLogger(__name__).debug(
        "Logging configured",
        extra={
            "level": level,
            "metrics_namespace": effective_settings.metrics_namespace,
        },
    )


def get_logger(
    name: str, extra: Mapping[str, str] | None = None
) -> logging.LoggerAdapter[logging.Logger]:
    """Return a module-scoped logger with optional contextual fields.

    Args:
        name: Logger name, typically the module ``__name__``.
        extra: Optional contextual key/value pairs to attach to each emitted
            log record.

    Returns:
        A ``logging.LoggerAdapter`` configured for the requested logger name.
    """
    base = logging.getLogger(name)
    return logging.LoggerAdapter(base, extra or {})


__all__ = ["configure_logging", "get_logger"]

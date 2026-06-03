import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from ddigraph.config import Settings
from ddigraph.logging import DEFAULT_FORMAT, configure_logging, get_logger


@pytest.fixture
def logging_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], list[str | None], MagicMock]:
    basic_config_calls: dict[str, Any] = {}
    logger_mock = MagicMock()
    logger_names: list[str | None] = []

    def fake_basicConfig(**kwargs: Any) -> None:
        basic_config_calls.update(kwargs)

    def fake_getLogger(name: str | None = None) -> MagicMock:
        logger_names.append(name)
        return logger_mock

    monkeypatch.setattr(logging, "basicConfig", fake_basicConfig)
    monkeypatch.setattr(logging, "getLogger", fake_getLogger)
    return basic_config_calls, logger_names, logger_mock


def test_configure_logging_uses_settings(
    logging_mocks: tuple[dict[str, Any], list[str | None], MagicMock],
) -> None:
    calls, logger_names, logger_mock = logging_mocks

    settings = Settings(log_level="WARNING", metrics_namespace="custom")

    configure_logging(settings)

    expected_level = logging.getLevelName(settings.log_level)
    assert calls == {
        "level": expected_level,
        "format": DEFAULT_FORMAT,
    }
    assert "ddigraph.logging" in logger_names
    logger_mock.debug.assert_called_once_with(
        "Logging configured",
        extra={"level": expected_level, "metrics_namespace": "custom"},
    )


def test_get_logger_returns_adapter_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_logger = MagicMock()
    captured_names: list[str | None] = []

    def fake_getLogger(name: str | None = None) -> MagicMock:
        captured_names.append(name)
        return base_logger

    monkeypatch.setattr(logging, "getLogger", fake_getLogger)

    adapter = get_logger("ddigraph.some.module", {"request_id": "abc123"})

    assert isinstance(adapter, logging.LoggerAdapter)
    assert adapter.logger is base_logger
    assert adapter.extra == {"request_id": "abc123"}
    assert captured_names[-1] == "ddigraph.some.module"

from unittest.mock import patch

from ddigraph.metrics import NullMetrics


def test_full_name_prefixes_with_namespace() -> None:
    metrics = NullMetrics(namespace="prefix")

    assert metrics._full_name("metric") == "prefix.metric"


def test_full_name_passthrough_without_namespace() -> None:
    metrics = NullMetrics(namespace="")

    assert metrics._full_name("metric") == "metric"


def test_increment_invokes_full_name_only() -> None:
    metrics = NullMetrics()

    with patch.object(metrics, "_full_name", wraps=metrics._full_name) as full_name:
        metrics.increment("metric")

    full_name.assert_called_once_with("metric")


def test_observe_invokes_full_name_only() -> None:
    metrics = NullMetrics()

    with patch.object(metrics, "_full_name", wraps=metrics._full_name) as full_name:
        metrics.observe("metric", 1.23)

    full_name.assert_called_once_with("metric")

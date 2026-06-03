import warnings

import pytest

from ddigraph.config import Settings, resolve_credentials_source


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", True),
        ("false", False),
    ],
)
def test_verify_hostname_env_mapping(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("DDIGRAPH_VERIFY_HOSTNAME", value)

    settings = Settings()

    assert settings.verify_hostname is expected


def test_neo4ddi_env_emits_deprecation_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """``NEO4DDI_*`` env vars were dropped in 0.4.0; setting one warns.

    The legacy prefix was retired alongside the broader env-var
    consolidation. The warning lists every offending variable so users
    know exactly what to rename.
    """
    monkeypatch.setenv("NEO4DDI_NEO4J_URI", "bolt://legacy:7687")
    monkeypatch.setenv("NEO4DDI_NEO4J_USER", "legacy-user")

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        Settings()

    deprecations = [w for w in captured if issubclass(w.category, DeprecationWarning)]
    assert deprecations, "expected a DeprecationWarning when NEO4DDI_* is set"
    message = str(deprecations[0].message)
    assert "NEO4DDI_NEO4J_URI" in message
    assert "NEO4DDI_NEO4J_USER" in message
    assert "DDIGRAPH_*" in message


def test_resolve_credentials_source_recognises_canonical_and_legacy() -> None:
    """``resolve_credentials_source`` only mentions DDIGRAPH_* and NEO4J_*."""
    assert resolve_credentials_source({"DDIGRAPH_NEO4J_URI": "x"}) == "DDIGRAPH_* variables"
    assert resolve_credentials_source({"NEO4J_URI": "x"}) == "legacy NEO4J_* variables"
    assert "defaults" in resolve_credentials_source({})


def test_resolve_credentials_source_no_longer_returns_neo4ddi_branch() -> None:
    """Setting only NEO4DDI_* hits the ``defaults`` branch since the alias is gone."""
    assert (
        resolve_credentials_source({"NEO4DDI_NEO4J_URI": "x"})
        == "defaults (no DDIGRAPH_* or NEO4J_* overrides detected)"
    )

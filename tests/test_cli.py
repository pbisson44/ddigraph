import argparse
import asyncio
from pathlib import Path
from typing import cast

import pytest

from ddigraph import cli
from ddigraph.config import Settings
from ddigraph.ingest.loader import DRY_RUN_MESSAGE


def test_parser_requires_subcommand() -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_resolve_xml_path_requires_readable_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"

    with pytest.raises(argparse.ArgumentTypeError) as excinfo:
        cli.resolve_xml_path(str(missing))

    assert "readable file" in str(excinfo.value)


def test_resolve_dataset_id_rejects_blank_values() -> None:
    with pytest.raises(argparse.ArgumentTypeError) as excinfo:
        cli.resolve_dataset_id("   ")

    assert "dataset_id must be a non-empty string" in str(excinfo.value)


def test_resolve_dataset_id_strips_whitespace() -> None:
    assert cli.resolve_dataset_id("  demo  ") == "demo"


def test_load_parser_parses_arguments(tmp_path: Path) -> None:
    xml_path = tmp_path / "codebook.xml"
    xml_path.touch()

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "load",
            str(xml_path),
            "--dataset-id",
            "demo",
            "--dataset-name",
            "Demo",
            "--replace",
            "--neo4j-uri",
            "bolt://db:7687",
            "--queue-maxsize",
            "4",
            "--batch-metrics",
            "--dry-run",
        ]
    )

    assert args.command == "load"
    assert args.xml_path == str(xml_path.resolve())
    assert args.dataset_id == "demo"
    assert args.dataset_name == "Demo"
    assert args.replace is True
    assert args.neo4j_uri == "bolt://db:7687"
    assert args.queue_maxsize == 4
    assert args.batch_metrics is True
    assert args.dry_run is True
    assert args.handler is cli._load_command


def test_driver_receives_connection_tuning(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyDriver:
        def close(self) -> None:  # pragma: no cover - trivial
            pass

    def fake_driver(uri: str, auth: object, **kwargs: object) -> DummyDriver:
        captured["uri"] = uri
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return DummyDriver()

    monkeypatch.setattr(cli.GraphDatabase, "driver", staticmethod(fake_driver))

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "bootstrap",
            "--neo4j-uri",
            "bolt://db:7687",
            "--neo4j-user",
            "tester",
            "--neo4j-password",
            "secret",
            "--max-connection-pool-size",
            "7",
            "--connection-timeout",
            "3.5",
            "--max-connection-lifetime",
            "120",
            "--session-timeout",
            "8",
            "--transaction-timeout",
            "2.5",
        ]
    )

    settings = cli._settings_from_args(args)
    driver = cli._create_driver(settings)

    assert isinstance(driver, DummyDriver)
    assert captured["uri"] == "bolt://db:7687"
    assert captured["auth"] == ("tester", "secret")
    assert captured["kwargs"] == {
        "max_connection_pool_size": 7,
        "connection_timeout": 3.5,
        "max_connection_lifetime": 120.0,
    }
    assert settings.session_timeout == 8.0
    assert settings.transaction_timeout == 2.5


def test_driver_receives_tls_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyDriver:
        def close(self) -> None:  # pragma: no cover - trivial
            pass

    def fake_driver(uri: str, auth: object, **kwargs: object) -> DummyDriver:
        captured["uri"] = uri
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return DummyDriver()

    monkeypatch.setattr(cli.GraphDatabase, "driver", staticmethod(fake_driver))

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "bootstrap",
            "--neo4j-uri",
            "neo4j+s://db:7687",
            "--encrypted",
            "--verify-hostname",
            "--trusted-certificates",
            "TRUST_ALL_CERTIFICATES",
            "--trusted-certificates-file",
            "/certs/ca.pem",
        ]
    )

    settings = cli._settings_from_args(args)
    driver = cli._create_driver(settings)

    assert isinstance(driver, DummyDriver)
    assert captured["uri"] == "neo4j+s://db:7687"
    assert captured["auth"] == (settings.neo4j_user, settings.neo4j_password.get_secret_value())
    assert settings.verify_hostname is True
    assert captured["kwargs"] == {
        "encrypted": True,
        "verify_hostname": True,
        "trusted_certificates": "TRUST_ALL_CERTIFICATES",
        "trusted_certificates_file": "/certs/ca.pem",
    }


def test_tls_settings_ignored_without_cli_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyDriver:
        def close(self) -> None:  # pragma: no cover - trivial
            pass

    def fake_driver(uri: str, auth: object, **kwargs: object) -> DummyDriver:
        captured["uri"] = uri
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return DummyDriver()

    monkeypatch.setattr(cli.GraphDatabase, "driver", staticmethod(fake_driver))
    monkeypatch.setenv("NEO4DDI_TRUSTED_CERTIFICATES", "TRUST_SYSTEM_CA")

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "bootstrap",
            "--neo4j-uri",
            "bolt://db:7687",
            "--neo4j-user",
            "tester",
            "--neo4j-password",
            "secret",
        ]
    )

    # Building settings with a legacy NEO4DDI_* var emits a deprecation warning;
    # assert it fires (and keep it out of the test-run warnings summary).
    with pytest.warns(DeprecationWarning, match="NEO4DDI"):
        settings = cli._settings_from_args(args)
    driver = cli._create_driver(settings)

    assert isinstance(driver, DummyDriver)
    assert captured["kwargs"] == {}


def test_explicit_plaintext_connections_respected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyDriver:
        def close(self) -> None:  # pragma: no cover - trivial
            pass

    def fake_driver(uri: str, auth: object, **kwargs: object) -> DummyDriver:
        captured["uri"] = uri
        captured["auth"] = auth
        captured["kwargs"] = kwargs
        return DummyDriver()

    monkeypatch.setattr(cli.GraphDatabase, "driver", staticmethod(fake_driver))

    parser = cli.build_parser()
    args = parser.parse_args(["bootstrap", "--neo4j-uri", "bolt://db:7687", "--no-encrypted"])

    settings = cli._settings_from_args(args)
    driver = cli._create_driver(settings)

    assert isinstance(driver, DummyDriver)
    assert captured["kwargs"] == {"encrypted": False}
    assert "encrypted" in settings.model_fields_set


def test_ensure_schema_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    async def fake_ensure(
        driver: object,
        database: str | None = None,
        include_fragments: bool = False,
        include_cdi: bool = False,
    ) -> None:
        calls["driver"] = driver
        calls["database"] = database
        calls["include_fragments"] = include_fragments
        calls["include_cdi"] = include_cdi

    monkeypatch.setattr(cli, "ensure_schema", fake_ensure)

    class DummyDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:  # pragma: no cover - trivial
            self.closed = True

    dummy_driver = DummyDriver()

    def fake_driver_factory(settings: Settings) -> DummyDriver:
        calls["settings"] = settings
        return dummy_driver

    settings = Settings()
    args = argparse.Namespace(command="bootstrap", handler=cli._ensure_schema_command)

    asyncio.run(cli._ensure_schema_command(args, settings, create_driver=fake_driver_factory))

    assert calls["driver"] is dummy_driver
    assert calls["database"] == settings.neo4j_database
    assert calls["settings"] is settings
    assert dummy_driver.closed is True


def test_load_command_emits_totals_and_closes_driver(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    totals = {"variables": 2, "categories": 5}

    class DummyDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:  # pragma: no cover - trivial
            self.closed = True

    class DummyLoader:
        def __init__(self, driver: DummyDriver, settings: Settings | None = None) -> None:
            self.driver = driver
            self.settings = settings

        async def load(
            self,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> dict[str, int]:
            assert path == "input.xml"
            assert dataset_id == "demo"
            assert dataset_name is None
            assert dry_run is False
            assert replace is False
            return totals

    dummy_driver = DummyDriver()

    def fake_driver_factory(settings: Settings) -> DummyDriver:
        assert isinstance(settings, Settings)
        return dummy_driver

    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    args = argparse.Namespace(
        command="load",
        handler=cli._load_command,
        xml_path="input.xml",
        dataset_id="demo",
        dataset_name=None,
        replace=False,
        json_output=False,
        format="codebook",
    )

    settings = Settings(dry_run=False)

    cli._load_command(args, settings, create_driver=fake_driver_factory)

    captured = capsys.readouterr()
    assert "Ingestion complete: categories=5, variables=2" in captured.out
    assert captured.err == ""
    assert dummy_driver.closed is True


def test_load_command_handles_sync_loader(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    totals = {"variables": 3}

    class DummyDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:  # pragma: no cover - trivial
            self.closed = True

    class DummyLoader:
        def __init__(self, driver: DummyDriver, settings: Settings | None = None) -> None:
            self.driver = driver
            self.settings = settings

        def load(
            self,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> dict[str, int]:
            assert path == "input.xml"
            assert dataset_id == "demo"
            assert dataset_name == "Demo"
            assert dry_run is False
            assert replace is False
            return totals

    dummy_driver = DummyDriver()

    def fake_driver_factory(settings: Settings) -> DummyDriver:
        assert isinstance(settings, Settings)
        return dummy_driver

    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    args = argparse.Namespace(
        command="load",
        handler=cli._load_command,
        xml_path="input.xml",
        dataset_id="demo",
        dataset_name="Demo",
        replace=False,
        json_output=True,
        format="codebook",
    )

    settings = Settings(dry_run=False)

    cli._load_command(args, settings, create_driver=fake_driver_factory)

    captured = capsys.readouterr()
    assert '{"variables":3}' in captured.out
    assert captured.err == ""
    assert dummy_driver.closed is True


def test_load_command_closes_sync_driver_when_codebook_loader_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyAsyncDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:  # pragma: no cover - trivial
            self.closed = True

    class DummySyncDriver:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class DummyLoader:
        def __init__(self, driver: DummySyncDriver, settings: Settings | None = None) -> None:
            self.driver = driver
            self.settings = settings

        def load(
            self,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> dict[str, int]:
            raise RuntimeError("load failed")

    async_driver = DummyAsyncDriver()
    sync_driver = DummySyncDriver()

    monkeypatch.setattr(cli, "_create_async_driver", lambda settings: async_driver)
    monkeypatch.setattr(cli, "_create_driver", lambda settings: sync_driver)
    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    args = argparse.Namespace(
        command="load",
        handler=cli._load_command,
        xml_path="input.xml",
        dataset_id="demo",
        dataset_name=None,
        replace=False,
        json_output=False,
        format="codebook",
    )
    settings = Settings(dry_run=False)

    with pytest.raises(RuntimeError, match="load failed"):
        asyncio.run(cli._load_command_async(args, settings))

    assert sync_driver.closed is True
    assert async_driver.closed is True


def test_load_command_keeps_loader_error_when_sync_close_fails(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class DummyAsyncDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:  # pragma: no cover - trivial
            self.closed = True

    class DummySyncDriver:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True
            raise RuntimeError("close failed")

    class DummyLoader:
        def __init__(self, driver: DummySyncDriver, settings: Settings | None = None) -> None:
            self.driver = driver
            self.settings = settings

        def load(
            self,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> dict[str, int]:
            raise RuntimeError("load failed")

    async_driver = DummyAsyncDriver()
    sync_driver = DummySyncDriver()

    monkeypatch.setattr(cli, "_create_async_driver", lambda settings: async_driver)
    monkeypatch.setattr(cli, "_create_driver", lambda settings: sync_driver)
    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    args = argparse.Namespace(
        command="load",
        handler=cli._load_command,
        xml_path="input.xml",
        dataset_id="demo",
        dataset_name=None,
        replace=False,
        json_output=False,
        format="codebook",
    )
    settings = Settings(dry_run=False)

    with caplog.at_level("WARNING"):
        with pytest.raises(RuntimeError, match="load failed"):
            asyncio.run(cli._load_command_async(args, settings))

    assert "Failed to close sync codebook driver after loader error" in caplog.text
    assert sync_driver.closed is True
    assert async_driver.closed is True


def test_load_invocation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    class DummyDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:  # pragma: no cover - trivial
            self.closed = True

    dummy_driver = DummyDriver()

    class DummyLoader:
        def __init__(self, driver: object, settings: Settings) -> None:
            calls["driver"] = driver
            calls["settings"] = settings

        async def load(
            self,
            *,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> None:
            calls["path"] = path
            calls["dataset_id"] = dataset_id
            calls["dataset_name"] = dataset_name
            calls["dry_run"] = dry_run
            calls["replace"] = replace

    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    def fake_driver_factory(settings: Settings) -> DummyDriver:
        calls["settings_from_driver"] = settings
        return dummy_driver

    settings = Settings()
    xml_path = tmp_path / "codebook.xml"
    xml_path.write_text("<codeBook/>")

    args = argparse.Namespace(
        command="load",
        handler=cli._load_command,
        xml_path=str(xml_path),
        dataset_id="demo",
        dataset_name="Demo",
        dry_run=settings.dry_run,
        format="codebook",
        replace=False,
        json_output=False,
    )

    cli._load_command(args, settings, create_driver=fake_driver_factory)

    assert calls["driver"] is dummy_driver
    assert calls["settings"] is settings
    assert calls["settings_from_driver"] is settings
    assert calls["path"] == str(xml_path)
    assert calls["dataset_id"] == "demo"
    assert calls["dataset_name"] == "Demo"
    assert calls["dry_run"] is settings.dry_run
    assert dummy_driver.closed is True


def test_settings_from_args_applies_retry_flags(tmp_path: Path) -> None:
    xml_path = tmp_path / "codebook.xml"
    xml_path.write_text("<CodeBook/>")

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "load",
            str(xml_path),
            "--dataset-id",
            "demo",
            "--write-retry-attempts",
            "5",
            "--write-retry-base-delay",
            "1.5",
            "--write-retry-jitter",
            "0.75",
        ]
    )

    settings = cli._settings_from_args(args)

    assert settings.write_retry_attempts == 5
    assert settings.write_retry_base_delay == 1.5
    assert settings.write_retry_jitter == 0.75


def test_main_applies_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_configure_logging(settings: Settings) -> None:  # pragma: no cover - trivial
        calls["log_settings"] = settings

    class DummyDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    dummy_driver = DummyDriver()

    def fake_driver_factory(settings: Settings) -> DummyDriver:
        calls["driver_settings"] = settings
        return dummy_driver

    async def fake_ensure(
        driver: object,
        database: str | None = None,
        include_fragments: bool = False,
        include_cdi: bool = False,
    ) -> None:
        calls["ensure_driver"] = driver
        calls["database"] = database
        calls["include_fragments"] = include_fragments
        calls["include_cdi"] = include_cdi

    monkeypatch.setattr(cli, "_create_async_driver", fake_driver_factory)
    monkeypatch.setattr(cli, "ensure_schema", fake_ensure)
    monkeypatch.setattr(cli, "configure_logging", fake_configure_logging)

    cli.main(
        [
            "bootstrap",
            "--neo4j-uri",
            "bolt://db:9999",
            "--neo4j-user",
            "custom",
            "--neo4j-password",
            "secret",
            "--neo4j-database",
            "example",
        ]
    )

    log_settings = cast(Settings, calls["log_settings"])
    driver_settings = cast(Settings, calls["driver_settings"])

    assert log_settings.neo4j_uri == "bolt://db:9999"
    assert log_settings.neo4j_user == "custom"
    assert log_settings.neo4j_password.get_secret_value() == "secret"
    assert log_settings.neo4j_database == "example"
    assert driver_settings is log_settings
    assert calls["ensure_driver"] is dummy_driver
    assert dummy_driver.closed is True


def test_main_load_invokes_loader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: dict[str, object] = {}

    class DummyDriver:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    dummy_driver = DummyDriver()

    def fake_driver_factory(settings: Settings) -> DummyDriver:
        calls["driver_settings"] = settings
        return dummy_driver

    class DummyLoader:
        def __init__(self, driver: object, settings: Settings) -> None:
            calls["loader_driver"] = driver
            calls["loader_settings"] = settings

        async def load(
            self,
            *,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> None:
            calls["path"] = path
            calls["dataset_id"] = dataset_id
            calls["dataset_name"] = dataset_name
            calls["dry_run"] = dry_run
            calls["replace"] = replace

    def fake_configure_logging(settings: Settings) -> None:  # pragma: no cover - trivial
        calls["log_settings"] = settings

    monkeypatch.setattr(cli, "_create_driver", fake_driver_factory)
    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "configure_logging", fake_configure_logging)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    xml_path = tmp_path / "codebook.xml"
    xml_path.write_text("<codeBook/>")

    cli.main(
        [
            "load",
            str(xml_path),
            "--dataset-id",
            "demo",
            "--dataset-name",
            "Demo Dataset",
            "--neo4j-uri",
            "bolt://db:7777",
            "--chunk-size",
            "123",
            "--queue-maxsize",
            "8",
            "--replace",
            "--log-level",
            "DEBUG",
            "--metrics-namespace",
            "ingest",
            "--validate-only",
        ]
    )

    captured = capsys.readouterr()
    assert DRY_RUN_MESSAGE in captured.out

    loader_settings = cast(Settings, calls["loader_settings"])

    assert calls["loader_driver"] is dummy_driver
    assert calls["path"] == str(xml_path.resolve())
    assert calls["dataset_id"] == "demo"
    assert calls["dataset_name"] == "Demo Dataset"
    assert calls["dry_run"] is True
    assert calls["replace"] is True
    assert loader_settings.neo4j_uri == "bolt://db:7777"
    assert loader_settings.chunk_size == 123
    assert loader_settings.queue_maxsize == 8
    assert loader_settings.log_level == "DEBUG"
    assert loader_settings.metrics_namespace == "ingest"
    assert calls["log_settings"] is loader_settings
    assert dummy_driver.closed is True


def test_load_command_does_not_close_injected_driver_when_codebook_loader_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyInjectedDriver:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    class DummyLoader:
        def __init__(self, driver: DummyInjectedDriver, settings: Settings | None = None) -> None:
            self.driver = driver
            self.settings = settings

        def load(
            self,
            path: str,
            dataset_id: str,
            dataset_name: str | None = None,
            dry_run: bool | None = None,
            replace: bool = False,
        ) -> dict[str, int]:
            raise RuntimeError("load failed")

    dummy_driver = DummyInjectedDriver()

    def fake_driver_factory(settings: Settings) -> DummyInjectedDriver:
        return dummy_driver

    monkeypatch.setattr(cli, "DDILoader", DummyLoader)
    monkeypatch.setattr(cli, "detect_ddi_format", lambda path: "codebook")

    args = argparse.Namespace(
        command="load",
        handler=cli._load_command,
        xml_path="input.xml",
        dataset_id="demo",
        dataset_name=None,
        replace=False,
        json_output=False,
        format="codebook",
    )
    settings = Settings(dry_run=False)

    with pytest.raises(RuntimeError, match="load failed"):
        asyncio.run(cli._load_command_async(args, settings, create_driver=fake_driver_factory))

    assert dummy_driver.closed is True


def test_version_subcommand_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    """``ddigraph version`` writes the installed __version__ to stdout."""
    import ddigraph

    parser = cli.build_parser()
    args = parser.parse_args(["version"])
    settings = Settings()
    args.handler(args, settings)
    out = capsys.readouterr().out.strip()
    assert out == ddigraph.__version__


def test_bootstrap_subcommand_defaults_to_include_fragments() -> None:
    """``ddigraph bootstrap`` includes the fragment schema by default."""
    parser = cli.build_parser()
    args = parser.parse_args(["bootstrap"])
    assert args.command == "bootstrap"
    assert args.include_fragments is True

    # Power users can opt out with --no-include-fragments.
    args_opt_out = parser.parse_args(["bootstrap", "--no-include-fragments"])
    assert args_opt_out.include_fragments is False


@pytest.mark.parametrize("removed", ["ensure-schema", "ensure-fragment-schema"])
def test_removed_schema_subcommands_are_rejected(removed: str) -> None:
    """The 0.4.x deprecation shims are gone as of 0.5.0.

    Both verbs were deprecated in 0.4.0rc1 with removal announced for
    0.5.0. ``bootstrap`` covers each of them: it includes fragments by
    default and takes ``--no-include-fragments`` for the codebook-only
    case the old ``ensure-schema`` served.
    """
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([removed])


def test_subcommand_surface_is_the_documented_verbs() -> None:
    """Pin the verb list so a removal or addition is a deliberate edit."""
    parser = cli.build_parser()
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]

    assert len(subparsers) == 1
    assert set(subparsers[0].choices) == {
        "load",
        "detect",
        "bootstrap",
        "version",
        "export",
        "shapes",
        "preview",
        "validate",
    }


def test_export_needs_no_connection_options() -> None:
    """``export`` writes a file; it must not require or accept a database.

    Offering ``--neo4j-uri`` on a command that never opens a connection
    would imply the export goes through Neo4j, which is exactly the
    misunderstanding this release is trying to clear up.
    """
    parser = cli.build_parser()

    args = parser.parse_args(["export", "tests/fixtures/codebook_sample.xml", "-o", "out.ttl"])
    assert args.format == "turtle"
    assert not hasattr(args, "neo4j_uri")

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "export",
                "tests/fixtures/codebook_sample.xml",
                "-o",
                "out.ttl",
                "--neo4j-uri",
                "bolt://db:7687",
            ]
        )


def test_export_rejects_an_unknown_format() -> None:
    """Choices are checked by argparse before any parsing work happens."""
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            ["export", "tests/fixtures/codebook_sample.xml", "-o", "o.ttl", "--format", "yaml"]
        )


def test_bootstrap_include_cdi_defaults_off_and_is_settable() -> None:
    """DDI-CDI schema is opt-in; nothing shipped writes CDI nodes."""
    parser = cli.build_parser()

    assert parser.parse_args(["bootstrap"]).include_cdi is False
    assert parser.parse_args(["bootstrap", "--include-cdi"]).include_cdi is True

"""``--tune KEY=VALUE`` / ``--config FILE`` collapse on ``ddigraph load``.

The 25+ dedicated tuning flags still work; this adds a power-user
surface that sets any ``Settings`` field without a bespoke flag. These
tests pin the round-trip, the precedence order (flag > ``--tune`` >
``--config`` > env > default), and the fail-fast on an unknown key.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ddigraph import cli


def _ns(**kw: object) -> argparse.Namespace:
    """A Namespace with only the attributes a test sets.

    ``_settings_from_args`` reads every field via ``getattr(...,
    None)``, so unset attributes default to "not provided".
    """
    return argparse.Namespace(**kw)


def test_tune_roundtrips_and_coerces_types() -> None:
    settings = cli._settings_from_args(_ns(tune=["chunk_size=500", "strict_parsing=true"]))
    assert settings.chunk_size == 500
    assert settings.strict_parsing is True


def test_config_file_roundtrips(tmp_path: Path) -> None:
    cfg = tmp_path / "tune.toml"
    cfg.write_text('chunk_size = 250\nlog_level = "DEBUG"\n', encoding="utf-8")
    settings = cli._settings_from_args(_ns(config_file=cfg))
    assert settings.chunk_size == 250
    assert settings.log_level == "DEBUG"


def test_precedence_flag_beats_tune_beats_config(tmp_path: Path) -> None:
    cfg = tmp_path / "tune.toml"
    cfg.write_text("chunk_size = 100\nwriter_concurrency = 2\n", encoding="utf-8")
    settings = cli._settings_from_args(
        _ns(
            config_file=cfg,
            tune=["chunk_size=200", "writer_concurrency=3"],
            chunk_size=300,  # an explicit per-flag option
        )
    )
    assert settings.chunk_size == 300  # flag wins
    assert settings.writer_concurrency == 3  # --tune wins over --config


def test_unknown_tune_key_fails_fast() -> None:
    with pytest.raises(SystemExit, match="unknown setting 'nope'"):
        cli._settings_from_args(_ns(tune=["nope=1"]))


def test_malformed_tune_fails_fast() -> None:
    with pytest.raises(SystemExit, match="KEY=VALUE"):
        cli._settings_from_args(_ns(tune=["chunk_size"]))


def test_unknown_config_key_fails_fast(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.toml"
    cfg.write_text("not_a_setting = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="unknown setting 'not_a_setting'"):
        cli._settings_from_args(_ns(config_file=cfg))


def test_missing_config_file_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="cannot read"):
        cli._settings_from_args(_ns(config_file=tmp_path / "absent.toml"))


def test_load_parser_accepts_tune_and_config(tmp_path: Path) -> None:
    xml = tmp_path / "x.xml"
    xml.write_text("<codeBook/>", encoding="utf-8")
    parser = cli.build_parser()
    args = parser.parse_args(["load", str(xml), "--tune", "chunk_size=42", "--config", "c.toml"])
    assert args.tune == ["chunk_size=42"]
    assert args.config_file == Path("c.toml")

"""Contract tests for ``BatchBuilder._run_composition``.

The walker that consumes :class:`CompositionSpec` is the seam through
which all 31 flat codebook handlers now flow. The codebook snapshot
test pins its behaviour against the historical hand-written handlers;
these tests document the contract directly so a future change to the
walker (extra id modes, new splat flags, etc.) breaks here first with
a clear error rather than only via a snapshot diff.

A synthetic record dataclass is monkeypatched into the loader module's
globals and a synthetic ``CompositionSpec`` into the registry. The
real :class:`BatchBuilder` provides the surrounding plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from lxml import etree

from ddigraph.ingest import _composition_specs as specs_module, loader as ldr
from ddigraph.ingest._composition_specs import CompositionSpec, Field


@dataclass(frozen=True)
class _Synthetic:
    """A throwaway record class the walker can construct."""

    dataset_id: str
    dataset_name: str | None
    test_id: str
    extra1: object = None
    extra2: object = None
    urn: str | None = None
    agency: str | None = None
    version: str | None = None
    reusable_urn: str | None = None
    reusable_agency: str | None = None
    reusable_version: str | None = None
    reusable_id: str | None = None
    reusable_type_of_object: str | None = None
    name: str | None = None
    label: str | None = None
    description: str | None = None
    rationale: str | None = None
    language: str | None = None


def _el(xml: str) -> etree._Element:
    return etree.fromstring(xml)


def _spec(**overrides: Any) -> CompositionSpec:
    defaults: dict[str, Any] = {
        "collection": "test_records",
        "record": "_Synthetic",
        "id_field": "test_id",
        "dedup": "seen_test",
    }
    defaults.update(overrides)
    return CompositionSpec(**defaults)


@pytest.fixture
def builder(monkeypatch: pytest.MonkeyPatch) -> ldr.BatchBuilder:
    """A BatchBuilder with synthetic collection/counter/dedup attrs."""
    b = ldr.BatchBuilder("ds1", "DS1", chunk_size=100)
    monkeypatch.setattr(ldr, "_Synthetic", _Synthetic, raising=False)
    b.test_records = []  # type: ignore[attr-defined]
    b.test_counter = 0  # type: ignore[attr-defined]
    b.seen_test = set()  # type: ignore[attr-defined]
    return b


def _register(monkeypatch: pytest.MonkeyPatch, spec: CompositionSpec) -> None:
    monkeypatch.setitem(specs_module.SPECS, "ingest_test", spec)


def test_always_mode_uses_elem_id_when_present(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(monkeypatch, _spec(id_slug="t", counter="test_counter"))
    builder._run_composition("ingest_test", _el('<v ID="custom"/>'))
    assert builder.test_records[0].test_id == "custom"  # type: ignore[attr-defined]
    # ``always`` still bumps the counter before consulting the element.
    assert builder.test_counter == 1  # type: ignore[attr-defined]


def test_always_mode_falls_back_to_synthesised_id(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(monkeypatch, _spec(id_slug="t", counter="test_counter"))
    builder._run_composition("ingest_test", _el("<v/>"))
    assert builder.test_records[0].test_id == "ds1:t_1"  # type: ignore[attr-defined]


def test_lazy_mode_only_bumps_counter_when_id_missing(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(monkeypatch, _spec(id_slug="t", counter="test_counter", id_mode="lazy"))
    builder._run_composition("ingest_test", _el('<v ID="x"/>'))
    builder._run_composition("ingest_test", _el("<v/>"))
    ids = [r.test_id for r in builder.test_records]  # type: ignore[attr-defined]
    assert ids == ["x", "ds1:t_1"]
    assert builder.test_counter == 1  # type: ignore[attr-defined]


def test_id_slug_none_skips_when_elem_has_no_id(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(monkeypatch, _spec(id_slug=None))
    builder._run_composition("ingest_test", _el("<v/>"))
    assert builder.test_records == []  # type: ignore[attr-defined]


def test_dedup_short_circuits_repeated_id(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(monkeypatch, _spec(id_slug="t", counter="test_counter"))
    builder._run_composition("ingest_test", _el('<v ID="x"/>'))
    builder._run_composition("ingest_test", _el('<v ID="x"/>'))
    assert len(builder.test_records) == 1  # type: ignore[attr-defined]


def test_field_const_and_alias_evaluate_in_order(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(
        monkeypatch,
        _spec(
            id_slug="t",
            counter="test_counter",
            fields=(
                Field("extra1", const="literal"),
                Field("extra2", alias="extra1"),  # reuse the literal
            ),
        ),
    )
    builder._run_composition("ingest_test", _el('<v ID="x"/>'))
    rec = builder.test_records[0]  # type: ignore[attr-defined]
    assert rec.extra1 == "literal"
    assert rec.extra2 == "literal"


def test_extra_kwargs_override_declared_fields(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(
        monkeypatch,
        _spec(
            id_slug="t",
            counter="test_counter",
            fields=(Field("extra1", const="from_field"),),
        ),
    )
    builder._run_composition(
        "ingest_test",
        _el('<v ID="x"/>'),
        extra={"extra1": "from_extra", "extra2": "also"},
    )
    rec = builder.test_records[0]  # type: ignore[attr-defined]
    assert rec.extra1 == "from_extra"  # extra wins over the const field
    assert rec.extra2 == "also"


def test_splat_metadata_drops_listed_keys(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    _register(
        monkeypatch,
        _spec(
            id_slug="t",
            counter="test_counter",
            fields=(Field("version", const="from_field"),),
            splat_metadata=True,
            metadata_drop=("version",),  # version comes from the field
        ),
    )
    elem = _el('<v ID="x" agency="NSO" version="9.9"/>')
    builder._run_composition("ingest_test", elem)
    rec = builder.test_records[0]  # type: ignore[attr-defined]
    assert rec.version == "from_field"  # not clobbered by the metadata splat
    assert rec.agency == "NSO"  # other metadata keys still merged


def test_splat_textual_label_fallback(
    builder: ldr.BatchBuilder, monkeypatch: pytest.MonkeyPatch
) -> None:
    fallback = Field("label", select=lambda e: e.findtext("name"))
    _register(
        monkeypatch,
        _spec(
            id_slug="t",
            counter="test_counter",
            splat_textual=True,
            textual_label_fallback=fallback,
        ),
    )
    # No <labl> child -> textual["label"] starts None -> fallback fires.
    elem = _el('<v ID="x"><name>From-name</name></v>')
    builder._run_composition("ingest_test", elem)
    rec = builder.test_records[0]  # type: ignore[attr-defined]
    assert rec.label == "From-name"

"""Forward-only ratchet on XSD relationship structural coverage.

The 0.4.0 simplification plan requires every concrete identifiable
element across DDI-C 2.6, DDI-L 3.x, and DDI-CDI 1.0 to be backed by a
runtime ``NodeDefinition`` whose property and relationship sets are a
superset of the XSD. Property coverage is tracked in a follow-up commit;
this file covers the relationship dimension.

Two complementary assertions per flavor:

1. ``test_relationship_coverage_floor_per_flavor`` -- the relationship
   coverage percentage must stay at or above its recorded baseline.
   Raising the baseline is a normal part of progress; lowering it
   requires explicit acknowledgement.
2. ``test_relationship_coverage_summary_stays_advisory`` -- runs the
   audit script with ``--structural`` and verifies it exits 0 at the
   advisory threshold (0.0). At ``0.4.0rc1`` the threshold gets raised
   to 100.0; that change is made in CI's workflow YAML, not here.

When a fix lands that closes part of the gap, bump the corresponding
``_BASELINE_*_PCT`` value up to the new measured coverage. A test that
fails because actual coverage exceeds the baseline is a *success* --
raise the baseline.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Recorded relationship coverage percentages at the time this test was
# written (the start of plan step A.1). Coverage cannot drop below
# these numbers without the test failing.
#
# Source of truth: ``python scripts/xsd_coverage.py --structural``.
_BASELINE_DDI_L_PCT = 100.0  # 282 / 282 runtime / xsd-declared *Reference (plan step D)
_BASELINE_DDI_CDI_PCT = 100.0  # 240 / 240 runtime / xsd-declared associations (plan step C)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_coverage() -> dict[str, dict[str, object]]:
    """Run the audit and return the parsed structural coverage report."""
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    try:
        import xsd_coverage
    finally:
        sys.path.pop(0)
    return xsd_coverage._structural_coverage()


@pytest.mark.parametrize(
    ("flavor", "baseline_pct"),
    [
        ("ddi_l", _BASELINE_DDI_L_PCT),
        ("ddi_cdi", _BASELINE_DDI_CDI_PCT),
    ],
)
def test_relationship_coverage_floor_per_flavor(flavor: str, baseline_pct: float) -> None:
    """Coverage must stay at or above the recorded baseline.

    If this fails with actual > baseline, congratulations -- update
    the ``_BASELINE_*_PCT`` constant above to the new floor.
    """
    coverage = _load_coverage()[flavor]
    actual = float(coverage["coverage_pct"])  # type: ignore[arg-type]
    assert actual >= baseline_pct, (
        f"{flavor} structural coverage regressed: "
        f"actual={actual:.1f}% < baseline={baseline_pct:.1f}%. "
        f"Missing {len(coverage['missing'])} of {coverage['target_count']} tags."  # type: ignore[arg-type]
    )


def test_codebook_relationship_coverage_is_not_applicable() -> None:
    """DDI-Codebook uses positional containment, not reference tags.

    The structural-coverage audit reports DDI-C as 100% (no targets)
    so the threshold gate never blocks on it. This test pins that
    invariant so a future change to the codebook walker is noticed.
    """
    coverage = _load_coverage()["ddi_c"]
    assert coverage["target_count"] == 0
    assert float(coverage["coverage_pct"]) == 100.0  # type: ignore[arg-type]


def test_audit_script_exits_zero_at_advisory_threshold() -> None:
    """``--structural`` without raising the threshold must exit 0.

    Until plan step C lands and runs the loaders through the generated
    relationship tables, CI runs ``--structural`` advisory-only. This
    test guards against the script ever exiting non-zero in advisory
    mode.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "xsd_coverage.py"),
            "--structural",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"advisory structural audit exited {result.returncode}; stderr:\n{result.stderr}"
    )


def test_audit_script_passes_at_full_threshold() -> None:
    """``--structural --structural-threshold 100`` must now pass.

    Plan steps C and D wired the runtime relationship tables through
    the XSD-derived data. DDI-L and DDI-CDI are both at 100%, and
    DDI-Codebook is N/A (containment-only). The CI workflow YAML can
    raise its threshold from advisory (0.0) to 100.0 with confidence.

    If this regresses to a failure, a loader change has reintroduced
    silently-dropped relationships; investigate before lowering the
    threshold.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "xsd_coverage.py"),
            "--structural",
            "--structural-threshold",
            "100",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"structural coverage regressed below 100% threshold; "
        f"exit={result.returncode}\nstderr:\n{result.stderr}"
    )

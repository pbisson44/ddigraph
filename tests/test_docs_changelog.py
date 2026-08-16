"""Guard the coupling between the docs changelog pages and ``CHANGELOG.md``.

The published pages used to be hand-maintained copies and had drifted badly:
both stopped at ``v0.1.0`` with no 0.4.x content at all, and they disagreed
with the root file on entity counts. They now include the real file via a
``pymdownx.snippets`` directive with a line offset, which removes that whole
class of drift but introduces a smaller one -- the offset is a magic number
that a future edit to the changelog preamble would silently invalidate,
producing a page with a duplicated title or a missing first release.

``mkdocs.yml`` sets ``check_paths: true``, so a *missing* file fails the
build. A wrong *offset* does not, which is what these tests cover.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
DOC_PAGES = [
    REPO_ROOT / "docs" / "en" / "project" / "changelog.md",
    REPO_ROOT / "docs" / "fr" / "project" / "changelog.md",
]

_SNIPPET = re.compile(r'--8<--\s+"CHANGELOG\.md:(\d+)"')


@pytest.mark.parametrize("page", DOC_PAGES, ids=lambda p: f"{p.parent.parent.name}")
def test_page_includes_the_changelog_rather_than_copying_it(page: Path) -> None:
    """A copy drifts; an include cannot."""
    assert _SNIPPET.search(page.read_text(encoding="utf-8")), (
        f"{page} no longer includes CHANGELOG.md -- a hand-maintained copy "
        "will drift out of date exactly as the previous one did"
    )


@pytest.mark.parametrize("page", DOC_PAGES, ids=lambda p: f"{p.parent.parent.name}")
def test_snippet_offset_lands_on_a_version_heading(page: Path) -> None:
    """The included region must begin at the newest release, not mid-preamble.

    ``pymdownx.snippets`` line ranges are 1-indexed and inclusive.
    """
    match = _SNIPPET.search(page.read_text(encoding="utf-8"))
    assert match is not None
    start = int(match.group(1))

    lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    assert start <= len(lines), f"offset {start} is past the end of CHANGELOG.md"

    first_included = lines[start - 1]
    assert first_included.startswith("## "), (
        f"{page.name} includes CHANGELOG.md from line {start}, which is "
        f"{first_included!r} -- expected a '## <version>' heading"
    )


def test_included_region_excludes_the_changelog_title() -> None:
    """The page supplies its own H1; including a second one breaks the TOC."""
    match = _SNIPPET.search(DOC_PAGES[0].read_text(encoding="utf-8"))
    assert match is not None

    included = CHANGELOG.read_text(encoding="utf-8").splitlines()[int(match.group(1)) - 1 :]

    assert not any(line.startswith("# ") for line in included)


def test_changelog_documents_the_release_in_progress() -> None:
    """0.5.0 must be described before it can be published.

    The publish workflow releases on a version bump to ``main`` with no
    manual approval step, so the changelog entry cannot be a follow-up.
    """
    assert "## 0.5.0" in CHANGELOG.read_text(encoding="utf-8")


def test_no_duplicate_version_headings() -> None:
    """Two sections claiming the same version make the file ambiguous.

    A stray ``## Unreleased`` sat below ``## 0.4.0a1`` describing work that
    had already shipped; adding a genuine unreleased section would have put
    two contradictory meanings of the word in one file.
    """
    headings = [
        line
        for line in CHANGELOG.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]

    assert len(headings) == len(set(headings)), "duplicate '## ' headings in CHANGELOG.md"

"""Unit tests for the docs readability gate's prose extraction.

The Flesch-Kincaid grade is only meaningful over natural-language
sentences. ``scripts/check_readability.py`` therefore reduces a
Markdown page to its prose before scoring. These tests pin that
reduction so a reference page that is mostly an identifier table can
never inflate the gate (the bug that made ``relationships.md`` score
Grade 38) and so genuine prose is preserved.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_readability.py"
_spec = importlib.util.spec_from_file_location("_check_readability", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cr)


def test_strips_tables_code_links_and_headings() -> None:
    md = (
        "# Title\n\n"
        "Real prose stays here.\n\n"
        "## A heading that is not a sentence\n\n"
        "| Relationship | Start | End |\n"
        "| --- | --- | --- |\n"
        "| `IN_DATASET` | Variable | Dataset |\n\n"
        "```python\nprint('code is not prose')\n```\n\n"
        "See the [adapter guide](adapter.md) and <https://example.org>.\n"
        "Use `some_identifier_name` carefully.\n"
        "![diagram](img.png)\n\n"
        "**Bold lead**: and *emphasis* survive as words.\n"
    )
    prose = _cr._strip_non_prose(md).strip()

    assert "Real prose stays here." in prose
    assert "adapter guide" in prose  # link text kept
    assert "Bold lead" in prose and "emphasis" in prose  # emphasis markers gone
    assert "*" not in prose and "#" not in prose and "|" not in prose
    assert "IN_DATASET" not in prose  # table row dropped
    assert "code is not prose" not in prose  # fenced code dropped
    assert "some_identifier_name" not in prose  # inline code neutralised
    assert "https://example.org" not in prose
    assert "img.png" not in prose
    assert "A heading that is not a sentence" not in prose


def test_grade_returns_grade_and_word_count() -> None:
    pytest.importorskip("textstat", reason="textstat is the optional ``docs`` extra")
    sample = "The cat sat on the mat. The dog ran in the park. Birds sing."
    scored = _cr._grade(sample)
    assert scored is not None
    grade, words = scored
    assert isinstance(grade, float)
    assert words == len(_cr._strip_non_prose(sample).split())


def test_empty_after_stripping_is_unscorable() -> None:
    assert _cr._grade("```\njust code\n```\n") is None

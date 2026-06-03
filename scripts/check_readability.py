"""Advisory Flesch-Kincaid grade-level audit for the docs tree.

Plan step I targets Grade-10 readability for every English-language
documentation page. This script wraps :mod:`textstat` so contributors
can ``make check-readability`` (or run it directly) before pushing
and see which pages still trip the threshold.

The script is **advisory** by default: it always exits 0 and prints
the grade per page. Pass ``--threshold 10`` to fail when any page
exceeds the given Flesch-Kincaid grade, and ``--fail-on-error`` to
treat unreadable files as errors (otherwise they are skipped with a
warning).

Usage::

    python scripts/check_readability.py docs/en
    python scripts/check_readability.py docs/en --threshold 10 --fail-on-error

``textstat`` is an optional dependency in the ``docs`` extra; if it
is not installed the script prints a hint and exits 0 so CI does not
hard-fail on environments that have not pulled in the docs extras.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_HTML_TAG = re.compile(r"<[^>]+>")
_MKDOCS_DIRECTIVE = re.compile(r"^!{3} .*$|^={3} .*$", re.MULTILINE)
_TABLE_ROW = re.compile(r"^\s*\|.*$", re.MULTILINE)
_AUTOLINK = re.compile(r"<https?://[^>]+>")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_REF_LINK_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*\S+.*$", re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`]+`")
_HEADING_LINE = re.compile(r"^\s*#{1,6}[^\n]*$", re.MULTILINE)
_EMPHASIS = re.compile(r"(\*{1,3}|_{1,3})(?=\S)(.+?)(?<=\S)\1")
# Below this many prose words the Flesch-Kincaid score is dominated by
# a handful of unavoidable domain nouns and is statistical noise; such
# pages (short code/reference stubs) are reported but never block.
_MIN_PROSE_WORDS = 150

# Structured release logs (Keep a Changelog format) are terse,
# fragmentary entries -- not narrative documentation. Flesch-Kincaid is
# meaningless over them, mirroring the .markdownlintignore CHANGELOG
# carve-out. Reported but never blocking.
_NON_PROSE_BASENAMES = frozenset({"changelog.md"})


def _strip_non_prose(text: str) -> str:
    """Reduce a Markdown page to its natural-language prose.

    Flesch-Kincaid is defined over natural-language sentences. Markdown
    tables, inline-code identifiers, link targets, and code blocks are
    not prose: scoring them inflates the grade into a meaningless
    number (a reference page that is mostly a relationship table would
    score Grade 30+ purely from underscore-laden identifiers). This
    removes those constructs so the score reflects the prose a reader
    actually has to parse.
    """
    text = _FRONT_MATTER.sub("", text)
    text = _CODE_FENCE.sub("", text)
    text = _MKDOCS_DIRECTIVE.sub("", text)
    text = _TABLE_ROW.sub("", text)
    text = _REF_LINK_DEF.sub("", text)
    text = _IMAGE.sub("", text)
    # Keep the visible link text, drop the URL target.
    text = _LINK.sub(r"\1", text)
    text = _AUTOLINK.sub("", text)
    # Inline code is an identifier, not a word -- replace with a single
    # neutral token so the surrounding sentence still parses.
    text = _INLINE_CODE.sub("code", text)
    text = _HTML_TAG.sub("", text)
    # Headings are labels, not sentences; a run of stripped headings
    # would otherwise read as one giant unpunctuated "sentence".
    text = _HEADING_LINE.sub("", text)
    text = _EMPHASIS.sub(r"\2", text)
    return _sentence_terminate_lines(text)


def _sentence_terminate_lines(text: str) -> str:
    """Make each non-empty line its own sentence.

    A Markdown list item is a discrete statement but carries no
    terminal punctuation. Fed to a sentence-based metric as-is, a run
    of bullets reads as one enormous sentence, so the score measures
    bullet density rather than readability. Terminating every line that
    lacks sentence punctuation restores one-statement-per-sentence.
    """
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line[-1] in ".!?":
            out.append(line)
        elif line[-1] in ":;,":
            out.append(line[:-1] + ".")
        else:
            out.append(line + ".")
    return "\n".join(out)


def _grade(text: str) -> tuple[float, int] | None:
    """Return ``(grade, prose_word_count)`` or ``None`` if unscorable.

    The word count lets the caller treat very short prose bodies as
    advisory: Flesch-Kincaid over a few sentences of unavoidable domain
    vocabulary is noise, not a readability signal.
    """
    try:
        import textstat
    except ImportError:
        print(
            "textstat is not installed; install with ``pip install ddigraph[docs]`` "
            "to enable readability scoring.",
            file=sys.stderr,
        )
        return None
    prose = _strip_non_prose(text).strip()
    if not prose:
        return None
    try:
        return float(textstat.flesch_kincaid_grade(prose)), len(prose.split())
    except _SCORING_ERRORS:
        return None


# Hoisted because ruff format 0.15.x with target-version py314 strips
# the parens off inline ``except (A, B):`` clauses (see commit 06ed1ba).
_SCORING_ERRORS: tuple[type[BaseException], ...] = (ValueError, ZeroDivisionError)


def main() -> int:
    """Score every ``*.md`` file under the given roots."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        default=[Path("docs/en")],
        help="Directories to scan for ``*.md`` files (default: docs/en).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Maximum acceptable Flesch-Kincaid grade. None (default) is advisory.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero if any page exceeds ``--threshold``.",
    )
    args = parser.parse_args()

    over: list[tuple[Path, float]] = []
    advisory: list[tuple[Path, float]] = []
    skipped: list[Path] = []
    for root in args.roots:
        if not root.exists():
            print(f"skipping non-existent root: {root}", file=sys.stderr)
            continue
        for path in sorted(root.rglob("*.md")):
            scored = _grade(path.read_text(encoding="utf-8"))
            if scored is None:
                skipped.append(path)
                continue
            grade, words = scored
            marker = "  "
            if args.threshold is not None and grade > args.threshold:
                if words < _MIN_PROSE_WORDS or path.name in _NON_PROSE_BASENAMES:
                    marker = "~ "
                    advisory.append((path, grade))
                else:
                    marker = "!!"
                    over.append((path, grade))
            print(f"{marker} {grade:5.1f}  {path}")

    if skipped:
        print(f"\nSkipped {len(skipped)} file(s) without scorable prose.")
    if advisory:
        print(
            f"\n{len(advisory)} short page(s) over threshold but under "
            f"{_MIN_PROSE_WORDS} prose words (advisory only):"
        )
        for path, grade in advisory:
            print(f"  {grade:5.1f}  {path}")

    if args.threshold is not None and over:
        print(f"\n{len(over)} page(s) exceed threshold {args.threshold}:")
        for path, grade in over:
            print(f"  {grade:5.1f}  {path}")
        if args.fail_on_error:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

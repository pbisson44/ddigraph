"""Selector primitives for the codebook composition DSL (plan step K).

This module is the single import point for the small set of pure
extraction functions used by:

* the TOML-driven walker that replaces the ~33 flat ``ingest_*``
  handlers, and
* the ~7 recursive handlers that stay as Python but compose these
  primitives instead of re-implementing extraction inline.

Every function here delegates to the battle-tested helpers already in
``ddigraph.ingest.loader`` so behaviour is byte-identical to the
pre-step-K loader (the snapshot test in
``tests/test_codebook_loader_snapshot.py`` is the gate). A later
migration commit physically relocates the helper bodies here and has
``loader`` import them back; until then this is a thin, faithful
facade.

The module is private (leading-underscore name); it does not widen
the package's public surface.

See ``docs/en/project/dsl-design.md`` for the full design.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ddigraph.ingest import loader as _loader

if TYPE_CHECKING:
    from lxml import etree


def text(elem: etree._Element, path: str) -> str | None:
    """First text node at ``path`` under ``elem``, or ``None``.

    Mirrors ``loader._first_text``.
    """
    return _loader._first_text(elem, path)


def text_any(elem: etree._Element, *paths: str) -> str | None:
    """First non-empty text across ``paths`` (namespace-insensitive).

    Mirrors ``loader._first_text_any``.
    """
    return _loader._first_text_any(elem, *paths)


def text_local(elem: etree._Element | None, *local_names: str) -> str | None:
    """First text whose element local-name matches one of ``local_names``.

    Mirrors ``loader._first_text_local``.
    """
    return _loader._first_text_local(elem, *local_names)


def text_or_none(elem: etree._Element | None) -> str | None:
    """Direct text content of ``elem`` (stripped) or ``None``.

    Mirrors ``loader._text_or_none`` (which aliases
    ``utils.parsing.get_text``).
    """
    if elem is None:
        return None
    return _loader._text_or_none(elem)


def attr(elem: etree._Element | None, name: str, *fallbacks: str) -> str | None:
    """Attribute ``name`` (or the first present of ``fallbacks``) on ``elem``.

    Returns ``None`` when ``elem`` is ``None`` or no attribute is set.
    Used for patterns like ``location.get("fileid") or location.get("FILEID")``.
    """
    if elem is None:
        return None
    value = elem.get(name)
    if value is not None:
        return value
    for candidate in fallbacks:
        value = elem.get(candidate)
        if value is not None:
            return value
    return None


def count(elem: etree._Element, child_tag: str) -> int:
    """Number of direct ``child_tag`` children of ``elem``."""
    return len(elem.findall(child_tag))


def metadata(elem: etree._Element | None) -> dict[str, str | None]:
    """Shared DDI metadata (``urn``/``agency``/``version`` + reusable ids).

    Mirrors ``loader._common_metadata``. Splat into a record's kwargs.
    """
    return _loader._common_metadata(elem)


def textual(elem: etree._Element | None) -> dict[str, str | None]:
    """Common textual fields (name/label/description/rationale/language).

    Mirrors ``loader._textual_metadata``. Splat into a record's kwargs.
    """
    return _loader._textual_metadata(elem)


def question_text(elem: etree._Element | None) -> str | None:
    """Literal question text with the loader's fallback chain.

    Mirrors ``loader._question_text``.
    """
    return _loader._question_text(elem)


def identifier(elem: etree._Element, default: str | None = "") -> str | None:
    """Resolve an element's identifier, falling back to ``default``.

    Mirrors ``loader._get_identifier``.
    """
    return _loader._get_identifier(elem, default=default)


def refs_by_suffix(elem: etree._Element, suffix: str) -> list[str]:
    """Reference values whose element tag ends with ``suffix``.

    Mirrors ``loader._reference_values_by_suffix`` (which aliases
    ``utils.parsing.extract_references_by_suffix``).
    """
    return _loader._reference_values_by_suffix(elem, suffix)


def truncate(value: str | None, limit: int) -> str | None:
    """Truncate ``value`` to ``limit`` characters; ``None`` passes through."""
    if value is None:
        return None
    return value[:limit]


def child_texts(elem: etree._Element, *paths: str) -> list[str]:
    """Stripped, non-empty ``.text`` of every element matching any ``path``.

    Mirrors the loader idiom
    ``for ref in elem.findall(".//nCubeRef") + elem.findall(".//ncubeRef"):
    ref.text.strip() if ref.text else None`` -- shallow ``.text`` only
    (not deep text), order preserved, empties skipped. ``paths`` are
    evaluated in order and their matches concatenated.
    """
    out: list[str] = []
    for path in paths:
        for node in elem.findall(path):
            raw = node.text
            if raw:
                stripped = raw.strip()
                if stripped:
                    out.append(stripped)
    return out


__all__ = [
    "attr",
    "child_texts",
    "count",
    "identifier",
    "metadata",
    "question_text",
    "refs_by_suffix",
    "text",
    "text_any",
    "text_local",
    "text_or_none",
    "textual",
    "truncate",
]

"""Utility modules for ddigraph."""

from ddigraph.utils.chunking import as_dicts, chunked, window
from ddigraph.utils.parsing import (
    close_iterparse_context,
    extract_common_metadata,
    extract_reference_value,
    extract_references_by_suffix,
    extract_reusable_identifiers,
    extract_textual_metadata,
    get_all_child_text,
    get_child_text,
    get_identifier,
    get_language,
    get_nested_text,
    get_text,
    strip_namespace,
)
from ddigraph.utils.retry import retry_transient

__all__ = [
    "as_dicts",
    "chunked",
    "close_iterparse_context",
    "extract_common_metadata",
    "extract_reference_value",
    "extract_references_by_suffix",
    "extract_reusable_identifiers",
    "extract_textual_metadata",
    "get_all_child_text",
    "get_child_text",
    "get_identifier",
    "get_language",
    "get_nested_text",
    "get_text",
    "retry_transient",
    "strip_namespace",
    "window",
]

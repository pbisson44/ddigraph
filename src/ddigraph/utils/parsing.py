"""Shared XML parsing utilities for DDI ingestion.

This module consolidates common parsing functions used by both the DDI
Codebook loader and the DDI-L FragmentInstance loader, eliminating code
duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lxml import etree


def strip_namespace(tag: str | bytes | bytearray | Any) -> str:
    """Remove XML namespace prefix from a tag.

    Args:
        tag: XML tag possibly containing a namespace in Clark notation {ns}local.
             Also accepts lxml QName objects.

    Returns:
        The local name portion of the tag without namespace.

    Examples:
        >>> strip_namespace("{http://example.org}Element")
        'Element'
        >>> strip_namespace("Element")
        'Element'
    """
    if isinstance(tag, bytes):
        tag_value = tag.decode()
    elif isinstance(tag, bytearray):
        tag_value = bytes(tag).decode()
    else:
        tag_value = str(tag)

    if tag_value.startswith("{"):
        return tag_value.split("}", 1)[1]
    return tag_value


def get_text(elem: etree._Element | None) -> str | None:
    """Get stripped text content from an element.

    Args:
        elem: XML element to extract text from.

    Returns:
        Stripped text content or None if empty/missing.
    """
    if elem is None:
        return None

    text = elem.text
    if isinstance(text, str):
        stripped = text.strip()
        if stripped:
            return stripped
    return None


def get_child_text(
    elem: etree._Element | None,
    *local_names: str,
    recursive: bool = False,
) -> str | None:
    """Get text from the first matching child element.

    Args:
        elem: Parent element to search within.
        local_names: Local tag names to match (without namespace).
        recursive: If True, search all descendants; if False, only direct children.

    Returns:
        Text content from the first matching element, or None.
    """
    if elem is None:
        return None

    iterator = elem.iter() if recursive else elem
    for child in iterator:
        if strip_namespace(child.tag) in local_names:
            text = get_text(child)
            if text:
                return text
    return None


def get_nested_text(
    elem: etree._Element | None,
    *local_names: str,
) -> str | None:
    """Get text from nested String/Content elements within matching children.

    This handles the DDI-L pattern where text is wrapped in r:String or r:Content
    elements inside a parent element like Label or Name.

    Args:
        elem: Parent element to search within.
        local_names: Local tag names of parent elements to check.

    Returns:
        Text content from nested String/Content, or direct text as fallback.
    """
    if elem is None:
        return None

    for child in elem:
        child_local = strip_namespace(child.tag)
        if child_local in local_names:
            # Check for nested String/Content elements (DDI-L pattern)
            for subchild in child:
                sub_local = strip_namespace(subchild.tag)
                if sub_local in ("String", "Content"):
                    text = get_text(subchild)
                    if text:
                        return text
            # Fall back to direct text
            text = get_text(child)
            if text:
                return text
    return None


def get_all_child_text(
    elem: etree._Element | None,
    *local_names: str,
    recursive: bool = False,
) -> list[str]:
    """Get text from all matching child elements.

    Args:
        elem: Parent element to search within.
        local_names: Local tag names to match.
        recursive: If True, search all descendants.

    Returns:
        List of text values from all matching elements.
    """
    values: list[str] = []
    if elem is None:
        return values

    iterator = elem.iter() if recursive else elem
    for child in iterator:
        if strip_namespace(child.tag) in local_names:
            text = get_text(child)
            if text:
                values.append(text)
    return values


def get_identifier(
    elem: etree._Element | None,
    default: str | None = None,
) -> str | None:
    """Extract the ID attribute or child element from a DDI element.

    Args:
        elem: Element to extract identifier from.
        default: Default value if no identifier found.

    Returns:
        The identifier string or default value.
    """
    if elem is None:
        return default

    # Try attribute first
    identifier = elem.get("ID") or elem.get("id")
    if isinstance(identifier, str) and identifier:
        return identifier

    # Try child element (DDI-L pattern)
    id_text = get_child_text(elem, "ID")
    if id_text:
        return id_text

    return default


def get_language(elem: etree._Element | None) -> str | None:
    """Extract language code from an element.

    Args:
        elem: Element to check for language attributes.

    Returns:
        Language code string or None.
    """
    if elem is None:
        return None

    # Check xml:lang attribute
    lang = elem.get("{http://www.w3.org/XML/1998/namespace}lang")
    if isinstance(lang, str) and lang:
        return lang

    # Check child Language element
    return get_child_text(elem, "Language", "language")


def extract_reference_value(elem: etree._Element | None) -> str | None:
    """Extract a reference value from a DDI reference element.

    Handles both URN-based and component-based (Agency:ID:Version) references.

    Args:
        elem: Reference element to extract value from.

    Returns:
        Reference string (URN or qualified ID) or None.
    """
    if elem is None:
        return None

    # Prefer URN if available
    urn = get_child_text(elem, "URN", recursive=True)
    if urn:
        return urn

    # Build from components
    agency = get_child_text(elem, "Agency", recursive=True)
    identifier = get_child_text(elem, "ID", recursive=True)
    version = get_child_text(elem, "Version", recursive=True)

    components = [v for v in (agency, identifier, version) if v]
    if components:
        return ":".join(components)

    # Fall back to direct text
    return get_text(elem)


def extract_references_by_suffix(
    elem: etree._Element | None,
    suffix: str,
) -> list[str]:
    """Collect reference values from elements whose tag ends with a suffix.

    Args:
        elem: Parent element to search within.
        suffix: Tag suffix to match (e.g., "Reference").

    Returns:
        List of extracted reference values.
    """
    values: list[str] = []
    if elem is None:
        return values

    for target in elem.iter():
        if strip_namespace(target.tag).endswith(suffix):
            ref = extract_reference_value(target)
            if ref:
                values.append(ref)
    return values


def extract_reusable_identifiers(
    elem: etree._Element | None,
) -> dict[str, str | None]:
    """Extract DDI reusable identifier fields from an element.

    Args:
        elem: Element containing reusable identifier children.

    Returns:
        Dictionary with reusable_id, reusable_version, reusable_urn,
        reusable_agency, and reusable_type_of_object fields.
    """
    if elem is None:
        return {
            "reusable_id": None,
            "reusable_version": None,
            "reusable_urn": None,
            "reusable_agency": None,
            "reusable_type_of_object": None,
        }

    return {
        "reusable_id": get_child_text(elem, "ID") or elem.get("ID") or elem.get("id"),
        "reusable_version": get_child_text(elem, "Version"),
        "reusable_urn": get_child_text(elem, "URN"),
        "reusable_agency": get_child_text(elem, "Agency"),
        "reusable_type_of_object": get_child_text(elem, "TypeOfObject"),
    }


def extract_common_metadata(
    elem: etree._Element | None,
) -> dict[str, str | None]:
    """Extract common DDI metadata attributes from an element.

    Args:
        elem: Element to extract metadata from.

    Returns:
        Dictionary with urn, agency, version, and reusable identifier fields.
    """
    reusable = extract_reusable_identifiers(elem)

    urn = None
    agency = None
    version = None

    if elem is not None:
        urn = (
            elem.get("URN")
            or elem.get("urn")
            or get_child_text(elem, "URN", "urn")
            or reusable.get("reusable_urn")
        )
        agency = (
            elem.get("agency")
            or elem.get("AGENCY")
            or get_child_text(elem, "agency", "Agency")
            or reusable.get("reusable_agency")
        )
        version = (
            elem.get("version")
            or elem.get("VERSION")
            or get_child_text(elem, "version", "Version")
            or reusable.get("reusable_version")
        )

    return {"urn": urn, "agency": agency, "version": version, **reusable}


def extract_textual_metadata(
    elem: etree._Element | None,
) -> dict[str, str | None]:
    """Extract common textual fields from a DDI element.

    Args:
        elem: Element to extract text fields from.

    Returns:
        Dictionary with name, label, description, rationale, and language fields.
    """
    if elem is None:
        return {
            "name": None,
            "label": None,
            "description": None,
            "rationale": None,
            "language": None,
        }

    name = get_child_text(elem, "name", "Name") or get_nested_text(elem, "Name")
    label = get_child_text(elem, "labl", "label") or get_nested_text(elem, "Label")
    description = get_child_text(
        elem, "Description", "description", "Content", "content"
    ) or get_text(elem)
    rationale = get_child_text(elem, "Rationale") or get_nested_text(elem, "Rationale")
    language = get_language(elem)

    return {
        "name": name,
        "label": label,
        "description": description,
        "rationale": rationale,
        "language": language,
    }


def close_iterparse_context(context: Any) -> None:
    """Close an lxml iterparse context if the method is available.

    Older lxml versions may not expose a ``close()`` method on the iterator
    returned by ``iterparse``.  This helper avoids duplicating the hasattr /
    getattr guard across every loader.

    Args:
        context: The iterparse iterator to close.
    """
    close_fn = getattr(context, "close", None)
    if close_fn is not None:
        close_fn()


__all__ = [
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
    "strip_namespace",
]

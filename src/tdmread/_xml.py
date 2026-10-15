"""Namespace-agnostic helpers for reading the USI `.tdm` XML header."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ._errors import TdmError, quote

ElementMap = dict[str, ET.Element]

# References appear as `id("usi12")`, optionally wrapped as
# `#xpointer(id("usi12") id("usi13"))`. This matches every id token in either form.
_REF = re.compile(r'id\("([^"]*)"\)')
_INTEGER = re.compile(r"[+-]?[0-9]+", re.ASCII)
# Wider than any 64-bit count or offset, far below Python's digit limit for int().
_MAX_DIGITS = 40


def child(element: ET.Element | None, name: str) -> ET.Element | None:
    """Return the first child element called `name` in any namespace, or None."""
    if element is None:
        return None
    for item in element:
        if item.tag == name or item.tag.endswith("}" + name):
            return item
    return None


def child_text(element: ET.Element | None, name: str) -> str:
    """Return the stripped text of the first `name` child, or an empty string."""
    found = child(element, name)
    return (found.text or "").strip() if found is not None else ""


def local_name(element: ET.Element) -> str:
    """Return the element's tag without any namespace."""
    return element.tag.rsplit("}", 1)[-1]


def refs(text: str) -> list[str]:
    """Return every referenced id found in `text`, in order."""
    return _REF.findall(text)


def one_ref(text: str) -> str | None:
    """Return the first referenced id in `text`, or None when there is none."""
    found = _REF.search(text)
    return found.group(1) if found else None


def resolve(by_id: ElementMap, element: ET.Element | None, name: str) -> ET.Element | None:
    """Follow the first reference held by the `name` child of `element`."""
    ref = one_ref(child_text(element, name))
    return by_id.get(ref) if ref is not None else None


def parse_int(text: str, what: str) -> int:
    """Parse a decimal integer written in ASCII digits, or raise :class:`TdmError`."""
    stripped = text.strip()
    if not _INTEGER.fullmatch(stripped):
        raise TdmError(f"{what} is not an integer: {quote(text)}")
    if len(stripped) > _MAX_DIGITS:
        raise TdmError(f"{what} is too large: {quote(text)}")
    return int(stripped)


def count_attribute(element: ET.Element, name: str, default: int | None = None) -> int:
    """Return the non-negative integer XML attribute `name`, or `default` when absent."""
    text = element.get(name)
    if text is None:
        if default is None:
            raise TdmError(f"block is missing its {name!r} attribute")
        return default
    value = parse_int(text, f"block attribute {name!r}")
    if value < 0:
        raise TdmError(f"block attribute {name!r} is negative: {value}")
    return value

"""Namespace-agnostic helpers for reading the USI `.tdm` XML header."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ._model import FileMetadata

# References appear as `id("usi12")`, optionally wrapped as
# `#xpointer(id("usi12") id("usi13"))`. This matches every id token in either form.
_REF = re.compile(r'id\("([^"]+)"\)')


def child_text(element: ET.Element | None, name: str) -> str:
    """Return the stripped text of the first `name` child, or an empty string."""
    if element is None:
        return ""
    child = element.find(f"{{*}}{name}")
    return (child.text or "").strip() if child is not None else ""


def refs(text: str) -> list[str]:
    """Return every referenced id found in `text`, in order."""
    return _REF.findall(text)


def one_ref(text: str) -> str | None:
    """Return the first referenced id in `text`, or None when there is none."""
    found = _REF.findall(text)
    return found[0] if found else None


def long_attribute(element: ET.Element, name: str) -> int | None:
    """Return the integer value of a `long_attribute` named `name`, or None.

    Channel lengths and similar scalars live in `instance_attributes` as
    `<long_attribute name="NI_ChannelLength">1000</long_attribute>` entries.
    """
    for attr in element.findall(".//{*}long_attribute"):
        if attr.get("name") == name:
            text = (attr.text or "").strip()
            if text:
                try:
                    return int(text)
                except ValueError:
                    return None
    return None


def read_metadata(root: ET.Element) -> FileMetadata:
    """Extract dataset-level metadata from the `tdm_root` block."""
    tdm_root = root.find(".//{*}tdm_root")
    if tdm_root is None:
        return FileMetadata()
    return FileMetadata(
        name=child_text(tdm_root, "name"),
        title=child_text(tdm_root, "title"),
        description=child_text(tdm_root, "description"),
        author=child_text(tdm_root, "author"),
        datetime=child_text(tdm_root, "datetime"),
    )

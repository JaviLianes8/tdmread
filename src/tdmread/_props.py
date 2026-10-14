"""Read the custom properties (``instance_attributes``) of the root, a group or a channel."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from datetime import datetime

from ._errors import TdmError
from ._numbers import as_byte, as_single, is_float, parse_integer
from ._times import parse_iso
from ._xml import child, local_name

PropertyValue = str | int | float | datetime

_INTEGER_KINDS = frozenset({"byte", "short", "long", "longlong"})
_FLOAT_KINDS = frozenset({"float", "double"})


class Properties(Mapping[str, PropertyValue]):
    """A read-only, hashable, picklable mapping of property names to values."""

    __slots__ = ("_items",)

    def __init__(self, items: Mapping[str, PropertyValue] | None = None) -> None:
        self._items: dict[str, PropertyValue] = dict(items or {})

    def __getitem__(self, key: str) -> PropertyValue:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(tuple(self._items.items()))

    def __repr__(self) -> str:
        return repr(self._items)

    def __reduce__(self) -> tuple[type[Properties], tuple[dict[str, PropertyValue]]]:
        return (Properties, (self._items,))


def read_properties(element: ET.Element | None) -> Properties:
    """Collect the typed ``*_attribute`` entries of `element`'s ``instance_attributes``."""
    block = child(element, "instance_attributes")
    if block is None:
        return Properties()
    found: dict[str, PropertyValue] = {}
    for attr in block:
        name = attr.get("name")
        kind = local_name(attr).removesuffix("_attribute")
        if name is None or name in found:
            continue
        found[name] = _value(kind, attr)
    return Properties(found)


def _value(kind: str, attr: ET.Element) -> PropertyValue:
    if kind == "string":
        parts = [item.text or "" for item in attr if local_name(item) == "s"]
        # NI's reader keeps only the first part of a string with several.
        return parts[0] if parts else (attr.text or "").strip()
    text = (attr.text or "").strip()
    # A value that does not parse as its declared kind is kept as the raw text.
    try:
        if kind == "byte":
            return as_byte(parse_integer(text))
        if kind in _INTEGER_KINDS:
            return parse_integer(text)
        if kind == "time":
            return parse_iso(text)
    except TdmError:
        return text
    if kind in _FLOAT_KINDS and is_float(text):
        return as_single(float(text)) if kind == "float" else float(text)
    return text

"""Decode value blocks out of a binary .tdx file."""

from __future__ import annotations

import struct
from datetime import datetime
from typing import NamedTuple

from ._errors import UnsupportedTdmError, quote
from ._times import decode_times

# TDX valueType names mapped to standard-size struct codes. NI's own reader treats
# eInt8Usi as an unsigned byte (it is what NI writes for DT_BYTE) and eSInt8Usi as the
# signed byte; both were checked against NI's reader. The byte order is applied apart.
_STRUCT_CODE: dict[str, str] = {
    "eInt8Usi": "B",
    "eSInt8Usi": "b",
    "eUInt8Usi": "B",
    "eInt16Usi": "h",
    "eUInt16Usi": "H",
    "eInt32Usi": "i",
    "eUInt32Usi": "I",
    "eInt64Usi": "q",
    "eUInt64Usi": "Q",
    "eFloat32Usi": "f",
    "eFloat64Usi": "d",
}
_TIME = "eTimeUsi"
_TIME_SIZE = 16

_BYTE_ORDER: dict[str, str] = {"littleEndian": "<", "bigEndian": ">"}

Decoded = tuple[float, ...] | tuple[datetime, ...]


class Layout(NamedTuple):
    """Where a block's values sit in the .tdx.

    Value ``j`` starts at ``start + (j // per_scan) * stride + (j % per_scan) * item``.
    A plain ``block`` is contiguous; ``block_bm`` and ``block_mr`` interleave channels.
    """

    start: int
    length: int
    stride: int | None = None
    per_scan: int = 1


def byte_order_prefix(byte_order: str) -> str:
    """Return the struct prefix ('<' or '>') for a TDM byteOrder attribute."""
    try:
        return _BYTE_ORDER[byte_order]
    except KeyError:
        raise UnsupportedTdmError(f"unknown byte order {quote(byte_order)}") from None


def supported_value_types() -> frozenset[str]:
    """The .tdx block valueType names tdmread decodes.

    Strings stored in the .tdx (``eStringUsi`` blocks) are not among them; strings
    written in the .tdm header itself are always read.

    >>> from tdmread import supported_value_types
    >>> sorted(supported_value_types())[:3]
    ['eFloat32Usi', 'eFloat64Usi', 'eInt16Usi']
    >>> "eTimeUsi" in supported_value_types()
    True
    """
    return frozenset(_STRUCT_CODE) | {_TIME}


def item_size(value_type: str) -> int:
    """Return the size in bytes of one value of `value_type`."""
    if value_type == _TIME:
        return _TIME_SIZE
    code = _STRUCT_CODE.get(value_type)
    if code is None:
        raise UnsupportedTdmError(f"unsupported value type {quote(value_type)}")
    return struct.calcsize("<" + code)


def span(layout: Layout, size: int) -> tuple[int, int]:
    """Return the (first byte, end byte) range that `layout` reads, items of `size`."""
    if layout.length == 0:
        return layout.start, layout.start
    last = layout.length - 1
    stride = layout.stride if layout.stride is not None else size * layout.per_scan
    end = layout.start + (last // layout.per_scan) * stride + (last % layout.per_scan) * size
    return layout.start, end + size


def decode(raw: bytes, layout: Layout, value_type: str, prefix: str) -> Decoded:
    """Decode the values of `layout` from `raw`, which holds exactly its span."""
    size = item_size(value_type)
    if layout.stride is not None and layout.length:
        raw = _gather(raw, layout, size)
    if value_type == _TIME:
        return decode_times(raw[: layout.length * size], prefix)
    code = _STRUCT_CODE[value_type]
    return struct.unpack(f"{prefix}{layout.length}{code}", raw[: layout.length * size])


def _gather(raw: bytes, layout: Layout, size: int) -> bytes:
    stride, per_scan = layout.stride or 0, layout.per_scan
    starts = ((j // per_scan) * stride + (j % per_scan) * size for j in range(layout.length))
    return b"".join(raw[at : at + size] for at in starts)

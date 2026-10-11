"""Decode numeric value blocks out of a binary .tdx file."""

from __future__ import annotations

import struct

from ._errors import TdmError, UnsupportedTdmError

# TDM valueType names mapped to standard-size struct format codes. The byte-order
# prefix is applied separately, so every code here reads a fixed width.
_STRUCT_CODE: dict[str, str] = {
    "eInt8Usi": "b",
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

_BYTE_ORDER: dict[str, str] = {"littleEndian": "<", "bigEndian": ">"}


def byte_order_prefix(byte_order: str) -> str:
    """Return the struct prefix ('<' or '>') for a TDM byteOrder attribute."""
    try:
        return _BYTE_ORDER[byte_order]
    except KeyError:
        raise UnsupportedTdmError(f"unknown byte order {byte_order!r}") from None


def supported_value_types() -> frozenset[str]:
    """The set of TDM valueType names this reader can decode."""
    return frozenset(_STRUCT_CODE)


def decode_block(
    data: bytes,
    prefix: str,
    value_type: str,
    byte_offset: int,
    length: int,
) -> tuple[float, ...]:
    """Decode `length` values of `value_type` starting at `byte_offset` in `data`."""
    code = _STRUCT_CODE.get(value_type)
    if code is None:
        raise UnsupportedTdmError(f"unsupported value type {value_type!r}")
    item = struct.calcsize(prefix + code)
    end = byte_offset + length * item
    if byte_offset < 0 or end > len(data):
        raise TdmError(
            f"block of {length} {value_type} at offset {byte_offset} "
            f"runs past the .tdx data ({len(data)} bytes)"
        )
    return struct.unpack(f"{prefix}{length}{code}", data[byte_offset:end])

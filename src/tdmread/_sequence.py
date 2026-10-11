"""Turn a localcolumn into decoded values, explicit or implicit-linear."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import NamedTuple

from ._binary import decode_block
from ._errors import TdmError, UnsupportedTdmError
from ._xml import child_text, long_attribute, one_ref

_ElementMap = dict[str | None, ET.Element]

# Representations that generate a linear axis instead of storing samples.
_IMPLICIT = frozenset({"implicit_linear", "implicit"})


class Sequence(NamedTuple):
    """Decoded samples plus the TDM value type and representation they came from."""

    value_type: str
    representation: str
    values: tuple[float, ...]


def read_sequence(
    channel_el: ET.Element,
    column: ET.Element,
    by_id: _ElementMap,
    blocks: _ElementMap,
    data: bytes,
    prefix: str,
) -> Sequence:
    """Decode the values a localcolumn describes.

    `explicit` columns are read from the .tdx block they point at. `implicit_linear`
    columns are generated as `offset + index * increment` from their generation
    parameters, with the length taken from the owning channel. Any other
    representation raises :class:`UnsupportedTdmError`.
    """
    representation = child_text(column, "sequence_representation") or "explicit"
    if representation == "explicit":
        return _read_explicit(column, by_id, blocks, data, prefix)
    if representation in _IMPLICIT:
        return _read_implicit(channel_el, column, by_id)
    raise UnsupportedTdmError(
        f"unsupported sequence representation {representation!r}; "
        "only 'explicit' and 'implicit_linear' channels are read"
    )


def _read_explicit(
    column: ET.Element,
    by_id: _ElementMap,
    blocks: _ElementMap,
    data: bytes,
    prefix: str,
) -> Sequence:
    sequence = by_id.get(one_ref(child_text(column, "values")))
    if sequence is None:
        return Sequence("", "explicit", ())
    values_el = sequence.find("{*}values")
    block = blocks.get(values_el.get("external")) if values_el is not None else None
    if block is None:
        return Sequence("", "explicit", ())
    value_type = block.get("valueType", "")
    byte_offset = int(block.get("byteOffset", "0"))
    length = int(block.get("length", "0"))
    values = decode_block(data, prefix, value_type, byte_offset, length)
    return Sequence(value_type, "explicit", values)


def _read_implicit(
    channel_el: ET.Element,
    column: ET.Element,
    by_id: _ElementMap,
) -> Sequence:
    offset, increment = _generation_parameters(child_text(column, "generation_parameters"))
    count = long_attribute(channel_el, "NI_ChannelLength")
    if count is None:
        count = _count_from_submatrix(column, by_id)
    if count is None:
        raise TdmError("implicit channel has no known length (no NI_ChannelLength or submatrix)")
    if count < 0:
        raise TdmError(f"implicit channel reports a negative length: {count}")
    values = tuple(offset + index * increment for index in range(count))
    return Sequence("", "implicit_linear", values)


def _generation_parameters(text: str) -> tuple[float, float]:
    """Return `(offset, increment)` from a generation_parameters string.

    A missing or partial value defaults the offset to 0.0 and the increment to 1.0,
    which yields the natural sample-index axis.
    """
    parts = text.split()
    offset = _as_float(parts[0]) if parts else 0.0
    increment = _as_float(parts[1]) if len(parts) > 1 else 1.0
    return offset, increment


def _as_float(token: str) -> float:
    try:
        return float(token)
    except ValueError as exc:
        raise TdmError(f"invalid generation parameter {token!r}") from exc


def _count_from_submatrix(column: ET.Element, by_id: _ElementMap) -> int | None:
    submatrix = by_id.get(one_ref(child_text(column, "submatrix")))
    if submatrix is None:
        return None
    rows = child_text(submatrix, "number_of_rows")
    if not rows:
        return None
    try:
        return int(rows)
    except ValueError:
        return None

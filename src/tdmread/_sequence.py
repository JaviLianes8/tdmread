"""Turn a localcolumn into decoded values for each sequence representation.

The rules follow NI's own reader, checked on files it wrote and on probes it read:
``implicit_linear`` is ``start + index * increment`` (a lone start gives a constant),
``implicit_constant`` repeats its value, ``raw_linear`` and ``raw_linear_external``
scale stored values as ``offset + factor * raw``, and generated channels take their
length from the submatrix row count.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import NamedTuple, cast

from ._channel import Values
from ._errors import TdmError, UnsupportedTdmError, quote
from ._explicit import read_values
from ._numbers import parse_float
from ._tdx import TdxSource
from ._xml import ElementMap, child, child_text, parse_int, resolve

_RAW = frozenset({"raw_linear", "raw_linear_external"})
_GENERATED = frozenset({"implicit_linear", "implicit_constant"})
# Generated channels need no stored data, so their size is capped: at most this many
# values plus one per byte of the .tdx, so a tiny header cannot demand gigabytes.
GENERATED_ALLOWANCE = 10_000_000


class Sequence(NamedTuple):
    """Decoded samples plus the TDX value type and representation they came from."""

    value_type: str
    representation: str
    values: Values


class Context(NamedTuple):
    """What every column of one dataset is read against."""

    by_id: ElementMap
    blocks: ElementMap
    tdx: TdxSource
    prefix: str
    budget: list[int]


def read_sequence(channel: ET.Element, column: ET.Element, ctx: Context) -> Sequence:
    """Decode the values that `column`, a localcolumn of `channel`, describes."""
    representation = child_text(column, "sequence_representation") or "explicit"
    if representation == "explicit":
        value_type, values = read_values(column, ctx.by_id, ctx.blocks, ctx.tdx, ctx.prefix)
        return Sequence(value_type, representation, values)
    if representation in _RAW:
        value_type, raw = read_values(column, ctx.by_id, ctx.blocks, ctx.tdx, ctx.prefix)
        offset, factor = _parameters(column, 2, representation)
        scaled = tuple(offset + factor * value for value in _numbers(raw, representation))
        return Sequence(value_type, representation, scaled)
    if representation in _GENERATED:
        return Sequence("", representation, _generate(channel, column, representation, ctx))
    raise UnsupportedTdmError(f"unsupported sequence representation {quote(representation)}")


def _generate(
    channel: ET.Element, column: ET.Element, representation: str, ctx: Context
) -> tuple[float, ...]:
    count = _length(channel, column, ctx.by_id)
    if count > ctx.budget[0]:
        raise TdmError(
            f"generated channels would need {count} values; the limit for this file "
            f"is {ctx.budget[0]} more"
        )
    ctx.budget[0] -= count
    params = _parameters(column, 1, representation)
    start = params[0]
    step = params[1] if representation == "implicit_linear" and len(params) > 1 else 0.0
    if step == 0.0:
        return (start,) * count
    return tuple(start + index * step for index in range(count))


def _numbers(values: Values, representation: str) -> tuple[float, ...]:
    if not all(isinstance(value, (int, float)) for value in values):
        raise TdmError(f"a {representation} channel must store numbers")
    return cast("tuple[float, ...]", values)


def _parameters(column: ET.Element, needed: int, representation: str) -> tuple[float, ...]:
    tokens = child_text(column, "generation_parameters").split()
    if len(tokens) < needed:
        raise TdmError(f"a {representation} channel needs {needed} generation parameter(s)")
    return tuple(parse_float(token) for token in tokens[:2])


def _length(channel: ET.Element, column: ET.Element, by_id: ElementMap) -> int:
    rows = child_text(resolve(by_id, column, "submatrix"), "number_of_rows")
    if not rows:
        rows = _channel_length(channel)
    if not rows:
        raise TdmError("a generated channel has no row count (submatrix number_of_rows)")
    count = parse_int(rows, "row count")
    if count < 0:
        raise TdmError(f"a generated channel has a negative row count: {count}")
    return count


def _channel_length(channel: ET.Element) -> str:
    attributes = child(channel, "instance_attributes")
    for attr in attributes if attributes is not None else ():
        if attr.get("name") == "NI_ChannelLength":
            return (attr.text or "").strip()
    return ""

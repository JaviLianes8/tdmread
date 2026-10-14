"""Turn a localcolumn into decoded values for each sequence representation.

The rules follow NI's own reader, checked on files it wrote and on probes it read:
``implicit_linear`` is ``start + index * increment`` (a lone start gives a constant),
``implicit_constant`` repeats its value (a column without generation_parameters takes
them from the first stored values), ``raw_linear`` and ``raw_linear_external``
scale stored values as ``offset + factor * raw``, and generated channels take their
length from the submatrix row count.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import NamedTuple, cast

from ._channel import Values
from ._errors import TdmError, UnsupportedTdmError, quote
from ._explicit import GENERATED, SCALED, charge, read_values, values_ref
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
    cache: dict[object, object]


def read_sequence(channel: ET.Element, column: ET.Element, ctx: Context) -> Sequence:
    """Decode the values that `column`, a localcolumn of `channel`, describes.

    Each column and each value sequence is decoded once per dataset, however many
    channels refer to it. A generated column takes its length from the channel, so only
    its parameters and row count are shared; its values are generated per channel.
    """
    key = ("column", id(column))
    found = ctx.cache.get(key)
    if found is None:
        found = _decode(column, ctx)
        ctx.cache[key] = found
    if isinstance(found, Sequence):
        return found
    representation, rows, params = cast("tuple[str, str, tuple[float, ...]]", found)
    count = _length(rows or _channel_length(channel))
    charge(count, ctx.budget, GENERATED)
    start = params[0]
    step = params[1] if representation == "implicit_linear" and len(params) > 1 else 0.0
    if step == 0.0:
        return Sequence("", representation, (start,) * count)
    return Sequence("", representation, tuple(start + i * step for i in range(count)))


def _stored(column: ET.Element, ctx: Context) -> tuple[str, Values]:
    ref = values_ref(column)
    if ref is None:
        return "", ()
    key = ("values", ref)
    if key not in ctx.cache:
        ctx.cache[key] = read_values(
            column, ctx.by_id, ctx.blocks, ctx.tdx, ctx.prefix, ctx.cache, ctx.budget
        )
    return cast("tuple[str, Values]", ctx.cache[key])


def _decode(column: ET.Element, ctx: Context) -> object:
    representation = child_text(column, "sequence_representation") or "explicit"
    if representation == "explicit":
        value_type, values = _stored(column, ctx)
        return Sequence(value_type, representation, values)
    if representation in _RAW:
        value_type, raw = _stored(column, ctx)
        offset, factor = _parameters(column, 2, representation)
        charge(len(raw), ctx.budget, SCALED)
        scaled = tuple(offset + factor * value for value in _numbers(raw, representation))
        return Sequence(value_type, representation, scaled)
    if representation in _GENERATED:
        rows = child_text(resolve(ctx.by_id, column, "submatrix"), "number_of_rows")
        return (representation, rows, _generation(column, representation, ctx))
    raise UnsupportedTdmError(f"unsupported sequence representation {quote(representation)}")


def _generation(column: ET.Element, representation: str, ctx: Context) -> tuple[float, ...]:
    # Without generation_parameters, NI's reader takes the start and the increment from
    # the first two values of the sequence the column refers to.
    if child_text(column, "generation_parameters"):
        return _parameters(column, 1, representation)
    _, stored = _stored(column, ctx)
    if not stored:
        raise TdmError(f"{representation} channel has no generation parameters")
    return _numbers(stored, representation)[:2]


def _numbers(values: Values, representation: str) -> tuple[float, ...]:
    if not all(isinstance(value, (int, float)) for value in values):
        raise TdmError(f"{representation} channel must store numbers")
    return cast("tuple[float, ...]", values)


def _parameters(column: ET.Element, needed: int, representation: str) -> tuple[float, ...]:
    tokens = child_text(column, "generation_parameters").split()
    if len(tokens) < needed:
        raise TdmError(f"{representation} channel needs {needed} generation parameter(s)")
    return tuple(parse_float(token) for token in tokens[:2])


def _length(rows: str) -> int:
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

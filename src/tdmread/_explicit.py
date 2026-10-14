"""Read the stored values a localcolumn points to, from the .tdx or from the header."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import cast

from ._binary import Layout, decode, item_size, span
from ._channel import Values
from ._errors import TdmError, UnsupportedTdmError, quote
from ._inline import inline_values
from ._tdx import TdxSource
from ._xml import ElementMap, child, count_attribute, local_name, one_ref


def read_values(
    column: ET.Element,
    by_id: ElementMap,
    blocks: ElementMap,
    tdx: TdxSource,
    prefix: str,
    cache: dict[object, object] | None = None,
) -> tuple[str, Values]:
    """Return ``(value_type, values)`` for the sequence `column` refers to.

    A column without a values reference is an empty channel, as NI writes them. The
    value type is the .tdx block's valueType, or empty for values written in the header.
    """
    ref = values_ref(column)
    if ref is None:
        return "", ()
    sequence = by_id.get(ref)
    if sequence is None:
        raise TdmError(f"a channel refers to a value sequence that does not exist: {quote(ref)}")
    values = child(sequence, "values")
    if values is None:
        return "", ()
    external = values.get("external")
    if external is None:
        return "", inline_values(sequence, values)
    key = ("block", external)
    if cache is not None and key in cache:
        return cast("tuple[str, Values]", cache[key])
    found = _block_values(blocks, external, tdx, prefix)
    if cache is not None:
        cache[key] = found
    return found


def _block_values(
    blocks: ElementMap, external: str, tdx: TdxSource, prefix: str
) -> tuple[str, Values]:
    block = blocks.get(external)
    if block is None:
        raise TdmError(f"a channel refers to a .tdx block that does not exist: {quote(external)}")
    value_type = block.get("valueType", "")
    if value_type == "eStringUsi":
        raise UnsupportedTdmError("strings stored in the .tdx (eStringUsi blocks) are not read")
    size = item_size(value_type)
    layout = block_layout(block, size)
    if layout.length == 0:
        return value_type, ()
    start, end = span(layout, size)
    return value_type, decode(tdx.read(start, end), layout, value_type, prefix)


def values_ref(column: ET.Element) -> str | None:
    """Return the id of the value sequence `column` refers to, or None."""
    found = child(column, "values")
    return one_ref(found.text or "") if found is not None else None


def block_layout(block: ET.Element, size: int) -> Layout:
    """Describe where the values of a ``block`` or ``block_bm`` element sit.

    NI's reader ignores blockSize and blockOffset on a plain ``block``. A ``block_bm``
    holds value ``i`` at ``byteOffset + blockOffset + i * blockSize``. ``block_mr`` is
    refused: NI's own two readers disagreed on it when probed.
    """
    kind = local_name(block)
    start = count_attribute(block, "byteOffset", 0)
    length = count_attribute(block, "length", 0)
    if kind == "block":
        return Layout(start, length)
    if kind != "block_bm":
        raise UnsupportedTdmError(f"unsupported .tdx block layout {quote(kind)}")
    start += count_attribute(block, "blockOffset", 0)
    stride = count_attribute(block, "blockSize")
    if stride < size:
        raise UnsupportedTdmError(
            f"block_bm with blockSize {stride} cannot hold a {size}-byte value per scan"
        )
    return Layout(start, length, stride)

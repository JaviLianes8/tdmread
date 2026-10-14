"""Read the stored values a localcolumn points to, from the .tdx or from the header."""

from __future__ import annotations

import xml.etree.ElementTree as ET

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
) -> tuple[str, Values]:
    """Return ``(value_type, values)`` for the sequence `column` refers to.

    A column without a values reference is an empty channel, as NI writes them. The
    value type is the .tdx block's valueType, or empty for values written in the header.
    """
    values_ref = child(column, "values")
    ref = one_ref(values_ref.text or "") if values_ref is not None else None
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


def block_layout(block: ET.Element, size: int) -> Layout:
    """Describe where the values of a ``block``, ``block_bm`` or ``block_mr`` element sit."""
    kind = local_name(block)
    start = count_attribute(block, "byteOffset", 0)
    length = count_attribute(block, "length", 0)
    if kind == "block":
        # NI's reader ignores blockSize and blockOffset on a plain block.
        return Layout(start, length)
    start += count_attribute(block, "blockOffset", 0)
    stride = count_attribute(block, "blockSize")
    per_scan = count_attribute(block, "valuesPerScan", 1) if kind == "block_mr" else 1
    if per_scan < 1 or stride < per_scan * size:
        raise UnsupportedTdmError(
            f"interleaved block with blockSize {stride} cannot hold {per_scan} value(s) "
            f"of {size} bytes per scan"
        )
    return Layout(start, length, stride, per_scan)

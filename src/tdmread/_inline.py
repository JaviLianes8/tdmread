"""Read values written inline in the .tdm header instead of in the .tdx file."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ._channel import Values
from ._errors import UnsupportedTdmError, quote
from ._numbers import as_byte, as_single, parse_float, parse_integer
from ._times import parse_iso
from ._xml import local_name

_INTEGER_SEQUENCES = frozenset(
    {
        "byte_sequence",
        "ubyte_sequence",
        "short_sequence",
        "ushort_sequence",
        "long_sequence",
        "ulong_sequence",
        "longlong_sequence",
        "ulonglong_sequence",
    }
)
_FLOAT_SEQUENCES = frozenset({"float_sequence", "double_sequence"})


def inline_values(sequence: ET.Element, values: ET.Element) -> Values:
    """Decode the inline `values` element of `sequence` (a ``*_sequence`` element).

    Numbers are separated by any whitespace, strings are ``<s>`` children, and times
    are ISO text. NI's reader returns exactly the values written, whatever the row count.
    """
    kind = local_name(sequence)
    if kind == "string_sequence":
        return tuple(item.text or "" for item in values if local_name(item) == "s")
    tokens = (values.text or "").split()
    # As NI's reader does, inline bytes are unsigned and inline floats are 32-bit.
    if kind == "byte_sequence":
        return tuple(as_byte(parse_integer(token)) for token in tokens)
    if kind in _INTEGER_SEQUENCES:
        return tuple(parse_integer(token) for token in tokens)
    if kind == "float_sequence":
        return tuple(as_single(parse_float(token)) for token in tokens)
    if kind in _FLOAT_SEQUENCES:
        return tuple(parse_float(token) for token in tokens)
    if kind == "time_sequence":
        return tuple(parse_iso(token) for token in tokens)
    raise UnsupportedTdmError(f"unsupported value sequence {quote(kind)}")

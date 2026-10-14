"""Strict parsing of numbers written as text in the .tdm header."""

from __future__ import annotations

import math
import re
import struct

from ._errors import TdmError, quote

# ASCII decimal notation only: Python's own int() and float() also accept underscores
# and non-ASCII digits, which no TDM writer produces.
_INTEGER = re.compile(r"[+-]?[0-9]{1,40}", re.ASCII)
_FLOAT = re.compile(
    r"[+-]?(?:(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,6})?|inf|infinity|nan)",
    re.ASCII | re.IGNORECASE,
)


def parse_integer(token: str) -> int:
    """Parse one integer token such as ``-42``.

    >>> parse_integer("-42")
    -42
    """
    if not _INTEGER.fullmatch(token):
        raise TdmError(f"invalid integer value {quote(token)}")
    return int(token)


def parse_float(token: str) -> float:
    """Parse one floating-point token such as ``2.5e-3``, ``INF`` or ``NaN``.

    >>> parse_float("2.5e-3"), parse_float("-INF")
    (0.0025, -inf)
    """
    if len(token) > 400 or not _FLOAT.fullmatch(token):
        raise TdmError(f"invalid floating-point value {quote(token)}")
    return float(token)


def is_float(token: str) -> bool:
    """Tell whether `token` is a valid floating-point token."""
    return len(token) <= 400 and _FLOAT.fullmatch(token) is not None


def as_byte(value: int) -> int:
    """Read an integer as NI reads a byte: unsigned, modulo 256.

    >>> as_byte(-5), as_byte(255)
    (251, 255)
    """
    return value % 256


def as_single(value: float) -> float:
    """Round a float to 32-bit precision, as NI stores ``float`` values.

    >>> as_single(0.1), as_single(-1e300)
    (0.10000000149011612, -inf)
    """
    try:
        single: float = struct.unpack("<f", struct.pack("<f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)
    return single


def as_short(value: int) -> int:
    """Read an integer as NI reads a ``short``: wrapped to 16 bits.

    >>> as_short(32768), as_short(65535)
    (-32768, -1)
    """
    return (value + 32768) % 65536 - 32768


def as_long(value: int) -> int:
    """Read an integer as NI reads a ``long``: clamped to 32 bits.

    >>> as_long(2**31), as_long(-(2**31) - 1)
    (2147483647, -2147483648)
    """
    return max(-(2**31), min(2**31 - 1, value))


NARROW = {"byte": as_byte, "short": as_short, "long": as_long}

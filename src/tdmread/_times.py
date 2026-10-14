"""Turn TDM time values into naive ``datetime`` objects.

TDM stores times as local wall-clock time without a zone. In the .tdx a time is 16 bytes,
an unsigned 64-bit fraction of a second (units of 2**-64 s) followed by signed 64-bit whole
seconds since 1904-01-01 00:00. In the .tdm XML it is ISO text with any number of
fractional digits. As NI's reader does, both are rounded to the nearest nanosecond (never
past the end of their second) and then cut to whole microseconds (``datetime`` holds no
finer unit).
"""

from __future__ import annotations

import re
import struct
from datetime import datetime, timedelta
from fractions import Fraction

from ._errors import TdmError, quote

EPOCH = datetime(1904, 1, 1)
_SECOND = timedelta(seconds=1)
_NANO = 1_000_000_000
_MIN_SECONDS = (datetime.min - EPOCH) // _SECOND
_MAX_SECONDS = (datetime.max - EPOCH) // _SECOND
_ISO = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?",
    re.ASCII,
)


def from_timestamp(seconds: int, fraction: int) -> datetime:
    """Return the time `seconds` + `fraction` / 2**64 after 1904-01-01.

    As NI's reader does, the fraction is rounded to the nearest nanosecond (never past
    the end of its second) and then cut to microseconds.

    >>> from_timestamp(3_874_844_079, 2**63)
    datetime.datetime(2026, 10, 14, 17, 34, 39, 500000)
    >>> from_timestamp(3_850_074_000, 0x0126E978D4FDF3B0)
    datetime.datetime(2026, 1, 1, 1, 0, 0, 4500)
    """
    nanos = min((fraction * _NANO + 2**63) >> 64, _NANO - 1)
    if not _MIN_SECONDS <= seconds <= _MAX_SECONDS:
        raise TdmError(f"time value {seconds} s from 1904 is outside the years 1 to 9999")
    return EPOCH + timedelta(seconds=seconds, microseconds=nanos // 1000)


def decode_times(raw: bytes, prefix: str) -> tuple[datetime, ...]:
    """Decode consecutive 16-byte time values in the byte order given by `prefix`."""
    layout = struct.Struct(prefix + ("Qq" if prefix == "<" else "qQ"))
    if prefix == "<":
        return tuple(from_timestamp(s, f) for f, s in layout.iter_unpack(raw))
    return tuple(from_timestamp(s, f) for s, f in layout.iter_unpack(raw))


def parse_iso(text: str) -> datetime:
    """Parse a TDM ISO time such as ``2026-10-14T15:34:39.7812`` (any number of digits).

    >>> parse_iso("2026-10-14T15:34:39.781104564666748046875")
    datetime.datetime(2026, 10, 14, 15, 34, 39, 781104)
    >>> parse_iso("2026-10-14T12:11:12.345677999999999985281")
    datetime.datetime(2026, 10, 14, 12, 11, 12, 345678)
    """
    match = _ISO.fullmatch(text.strip())
    if match is None:
        raise TdmError(f"invalid time {quote(text)}")
    year, month, day, hour, minute, second = (int(part) for part in match.groups()[:6])
    # NI reads the digits as a double, cuts double * 2**64 to a fraction and rounds that
    # like a .tdx time; a double of exactly 1.0 carries into the next second.
    fraction = int(Fraction(float("0." + (match.group(7) or "0")[:400])) * 2**64)
    try:
        whole = datetime(year, month, day, hour, minute, second)
    except ValueError:
        raise TdmError(f"invalid time {quote(text)}") from None
    seconds = (whole - EPOCH) // _SECOND
    if fraction >= 2**64:
        seconds, fraction = seconds + 1, 0
    return from_timestamp(seconds, fraction)

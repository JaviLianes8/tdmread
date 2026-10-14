"""Turn TDM time values into naive ``datetime`` objects.

TDM stores times as local wall-clock time without a zone. In the .tdx a time is 16 bytes,
an unsigned 64-bit fraction of a second (units of 2**-64 s) followed by signed 64-bit whole
seconds since 1904-01-01 00:00. In the .tdm XML it is ISO text with any number of
fractional digits. Both are cut (never rounded) to whole microseconds.
"""

from __future__ import annotations

import re
import struct
from datetime import datetime, timedelta

from ._errors import TdmError, quote

EPOCH = datetime(1904, 1, 1)
_SECOND = timedelta(seconds=1)
_MIN_SECONDS = (datetime.min - EPOCH) // _SECOND
_MAX_SECONDS = (datetime.max - EPOCH) // _SECOND
_ISO = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]+))?",
    re.ASCII,
)


def from_timestamp(seconds: int, fraction: int) -> datetime:
    """Return the time `seconds` + `fraction` / 2**64 after 1904-01-01, cut to microseconds.

    >>> from_timestamp(3_874_844_079, 2**63)
    datetime.datetime(2026, 10, 14, 17, 34, 39, 500000)
    """
    if not _MIN_SECONDS <= seconds <= _MAX_SECONDS:
        raise TdmError(f"time value {seconds} s from 1904 is outside the years 1 to 9999")
    micro = (fraction * 1_000_000) >> 64
    return EPOCH + timedelta(seconds=seconds, microseconds=micro)


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
    """
    match = _ISO.fullmatch(text.strip())
    if match is None:
        raise TdmError(f"invalid time {quote(text)}")
    year, month, day, hour, minute, second = (int(part) for part in match.groups()[:6])
    digits = (match.group(7) or "")[:6].ljust(6, "0")
    try:
        return datetime(year, month, day, hour, minute, second, int(digits))
    except ValueError:
        raise TdmError(f"invalid time {quote(text)}") from None

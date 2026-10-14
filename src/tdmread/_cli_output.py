"""Text, CSV and JSON rendering for the command-line interface."""

from __future__ import annotations

import csv
import io
import json
import math
import sys
from datetime import datetime
from typing import TextIO

from ._channel import Channel

# Error messages printed by the command are cut to this many characters.
MESSAGE_LIMIT = 300


def cell(value: object) -> str:
    """Render one value: floats round-trip (``repr``), times as ISO text, text as is."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        # JSON has no NaN or infinity; they are written as the strings Python prints.
        return repr(value)
    return value


def as_csv(channel: Channel) -> str:
    """Render a channel as two CSV columns: the index and the value."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["index", channel.name or "value"])
    for index, value in enumerate(channel.data):
        writer.writerow([index, cell(value)])
    return buffer.getvalue()


def as_json(channel: Channel) -> str:
    """Render a channel and its values as a JSON object."""
    payload = {
        "name": channel.name,
        "unit": channel.unit,
        "value_type": channel.value_type,
        "representation": channel.representation,
        "datatype": channel.datatype,
        "length": len(channel),
        "data": [_json_value(value) for value in channel.data],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def emit(text: str, stream: TextIO | None = None) -> None:
    """Write `text`, replacing characters the stream's encoding cannot show."""
    target = stream if stream is not None else sys.stdout
    encoding = getattr(target, "encoding", None) or "utf-8"
    try:
        target.write(text)
    except UnicodeEncodeError:
        target.write(text.encode(encoding, "backslashreplace").decode(encoding))


def short(message: str) -> str:
    """Cut an error message to :data:`MESSAGE_LIMIT` characters."""
    if len(message) <= MESSAGE_LIMIT:
        return message
    return message[: MESSAGE_LIMIT - 3] + "..."

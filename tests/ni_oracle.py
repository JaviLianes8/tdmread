"""Load the recorded NI reader views (``ni_view.json``) and compare tdmread against them.

The views were recorded by ``scripts/capture_ni.py``: ``channel`` is NI's channel-level
reading (LabVIEW's converter to TDMS, read back), ``datastore`` is NI's DataStore COM API.
Time values are compared with the DataStore view, which keeps TDM's local wall-clock time;
the TDMS view holds them shifted to UTC.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from tdmread import Channel, TdmFile

FIXTURES = Path(__file__).parent / "fixtures"


def load_view(folder: str) -> dict[str, Any]:
    """Return the recorded views of every file in `folder`."""
    path = FIXTURES / folder / "ni_view.json"
    view: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return view


def canon(value: object) -> object:
    """Write a tdmread value the way the capture wrote NI's values."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S.%f")
    return value


def ni_channels(view: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """Map ``(group, channel)`` to the recorded values (or summary) of one view."""
    return {
        (group["name"], channel["name"]): channel.get("values")
        for group in view.get("groups", [])
        for channel in group["channels"]
    }


def same_values(channel: Channel, recorded: Any) -> bool:
    """Tell whether `channel` holds exactly the values NI recorded."""
    ours = [canon(value) for value in channel.data]
    if isinstance(recorded, dict):
        text = json.dumps(ours, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return len(ours) == int(recorded["count"]) and digest == str(recorded["sha256"])
    return ours == list(recorded)


def expected_for(dataset: TdmFile, views: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """Pick, per channel, the NI view tdmread is compared with."""
    channel_view, store_view = ni_channels(views["channel"]), ni_channels(views["datastore"])
    picked = {}
    for group, channel in dataset.channels():
        key = (group.name, channel.name)
        is_time = channel.data and isinstance(channel.data[0], datetime)
        picked[key] = store_view.get(key) if is_time else channel_view.get(key)
    return picked

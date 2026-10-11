"""Structured result types returned by :func:`tdmread.read_tdm`."""

from __future__ import annotations

from dataclasses import dataclass

from ._errors import TdmError


@dataclass(frozen=True)
class Channel:
    """One channel: its metadata and the values decoded from the .tdx."""

    name: str
    unit: str
    description: str
    value_type: str
    data: tuple[float, ...]


@dataclass(frozen=True)
class Group:
    """A channel group holding an ordered set of channels."""

    name: str
    channels: tuple[Channel, ...]

    def channel(self, name: str) -> Channel:
        """Return the channel with `name`, or raise :class:`TdmError`."""
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise TdmError(f"no channel named {name!r} in group {self.name!r}")


@dataclass(frozen=True)
class TdmFile:
    """A parsed TDM dataset: its groups, each with its channels and data."""

    groups: tuple[Group, ...]

    def group(self, name: str) -> Group:
        """Return the group with `name`, or raise :class:`TdmError`."""
        for group in self.groups:
            if group.name == name:
                return group
        raise TdmError(f"no group named {name!r}")

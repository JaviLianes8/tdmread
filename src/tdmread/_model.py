"""Structured result types returned by :func:`tdmread.read_tdm`."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from ._errors import TdmError


@dataclass(frozen=True)
class Channel:
    """One channel: its metadata and the values decoded from the .tdx.

    `data` holds the decoded numbers as a plain tuple. For `explicit` channels the
    values come straight from the .tdx; for `implicit_linear` channels they are the
    generated linear axis `offset + index * increment`. `value_type` is the TDM
    valueType of an explicit block (empty for a generated axis), and `representation`
    is the sequence representation (`explicit` or `implicit_linear`).
    """

    name: str
    unit: str
    description: str
    value_type: str
    data: tuple[float, ...]
    representation: str = ""
    minimum: float | None = None
    maximum: float | None = None
    datatype: str = ""

    def __len__(self) -> int:
        """Number of samples in the channel."""
        return len(self.data)

    def to_list(self) -> list[float]:
        """Return the channel values as a new list."""
        return list(self.data)

    def to_numpy(self) -> Any:
        """Return the values as a NumPy array.

        NumPy is an optional extra: the core library never imports it. This raises
        :class:`TdmError` with an actionable message when NumPy is not installed.
        """
        try:
            import numpy as np
        except ModuleNotFoundError as exc:
            raise TdmError(
                "NumPy is not installed; run 'pip install numpy' to use Channel.to_numpy()"
            ) from exc
        return np.asarray(self.data)


@dataclass(frozen=True)
class Group:
    """A channel group holding an ordered set of channels."""

    name: str
    channels: tuple[Channel, ...]
    description: str = ""

    def __len__(self) -> int:
        """Number of channels in the group."""
        return len(self.channels)

    def __iter__(self) -> Iterator[Channel]:
        """Iterate over the group's channels in order."""
        return iter(self.channels)

    @property
    def channel_names(self) -> tuple[str, ...]:
        """The names of the channels in this group, in order."""
        return tuple(channel.name for channel in self.channels)

    def channel(self, name: str) -> Channel:
        """Return the channel with `name`, or raise :class:`TdmError`."""
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise TdmError(f"no channel named {name!r} in group {self.name!r}")


@dataclass(frozen=True)
class FileMetadata:
    """Dataset-level metadata read from the .tdm `tdm_root` block."""

    name: str = ""
    title: str = ""
    description: str = ""
    author: str = ""
    datetime: str = ""


@dataclass(frozen=True)
class TdmFile:
    """A parsed TDM dataset: its groups, each with its channels and data."""

    groups: tuple[Group, ...]
    metadata: FileMetadata = field(default_factory=FileMetadata)

    def __len__(self) -> int:
        """Number of groups in the dataset."""
        return len(self.groups)

    def __iter__(self) -> Iterator[Group]:
        """Iterate over the dataset's groups in order."""
        return iter(self.groups)

    @property
    def group_names(self) -> tuple[str, ...]:
        """The names of the groups in this dataset, in order."""
        return tuple(group.name for group in self.groups)

    def group(self, name: str) -> Group:
        """Return the group with `name`, or raise :class:`TdmError`."""
        for group in self.groups:
            if group.name == name:
                return group
        raise TdmError(f"no group named {name!r}")

    def channels(self) -> Iterator[tuple[Group, Channel]]:
        """Iterate over every `(group, channel)` pair in the dataset."""
        for group in self.groups:
            for channel in group.channels:
                yield group, channel

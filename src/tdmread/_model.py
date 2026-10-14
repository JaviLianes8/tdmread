"""The group and dataset types returned by :func:`tdmread.read_tdm`."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from ._channel import Channel
from ._errors import TdmError, quote
from ._props import Properties, PropertyValue


@dataclass(frozen=True)
class Group:
    """A channel group holding an ordered set of channels and its custom properties.

    >>> from tdmread import Channel, Group
    >>> group = Group("Run 1", (Channel("U", "V", "", "eFloat64Usi", (1.0, 2.0)),))
    >>> len(group), group.channel_names, group.channel("U").data
    (1, ('U',), (1.0, 2.0))
    """

    name: str
    channels: tuple[Channel, ...]
    description: str = ""
    properties: Mapping[str, PropertyValue] = field(default_factory=Properties, hash=False)

    def __len__(self) -> int:
        """Number of channels in the group.

        >>> from tdmread import Group
        >>> len(Group("empty", ()))
        0
        """
        return len(self.channels)

    def __iter__(self) -> Iterator[Channel]:
        """Iterate over the group's channels in order.

        >>> from tdmread import Channel, Group
        >>> [c.name for c in Group("G", (Channel("a", "", "", "", ()),))]
        ['a']
        """
        return iter(self.channels)

    @property
    def channel_names(self) -> tuple[str, ...]:
        """The names of the channels in this group, in order.

        >>> from tdmread import Channel, Group
        >>> Group("G", (Channel("a", "", "", "", ()), Channel("b", "", "", "", ()))).channel_names
        ('a', 'b')
        """
        return tuple(channel.name for channel in self.channels)

    def channel(self, name: str) -> Channel:
        """Return the first channel called `name`, or raise :class:`TdmError`.

        >>> from tdmread import Channel, Group
        >>> Group("G", (Channel("a", "", "", "", (7,)),)).channel("a").data
        (7,)
        """
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise TdmError(f"no channel named {quote(name)} in group {quote(self.name)}")


@dataclass(frozen=True)
class FileMetadata:
    """Dataset-level metadata read from the .tdm ``tdm_root`` element.

    `datetime` is the header's text as written (TDM times are local wall-clock time).

    >>> from tdmread import FileMetadata
    >>> FileMetadata(name="run", author="lab").author
    'lab'
    """

    name: str = ""
    title: str = ""
    description: str = ""
    author: str = ""
    datetime: str = ""


@dataclass(frozen=True)
class TdmFile:
    """A parsed TDM dataset: its groups, metadata and root custom properties.

    >>> from tdmread import Channel, Group, TdmFile
    >>> dataset = TdmFile((Group("G", (Channel("a", "", "", "", (1, 2)),)),))
    >>> dataset.group_names, [c.name for g, c in dataset.channels()]
    (('G',), ['a'])
    """

    groups: tuple[Group, ...]
    metadata: FileMetadata = field(default_factory=FileMetadata)
    properties: Mapping[str, PropertyValue] = field(default_factory=Properties, hash=False)

    def __len__(self) -> int:
        """Number of groups in the dataset.

        >>> from tdmread import TdmFile
        >>> len(TdmFile(()))
        0
        """
        return len(self.groups)

    def __iter__(self) -> Iterator[Group]:
        """Iterate over the dataset's groups in order.

        >>> from tdmread import Group, TdmFile
        >>> [g.name for g in TdmFile((Group("A", ()), Group("B", ())))]
        ['A', 'B']
        """
        return iter(self.groups)

    @property
    def group_names(self) -> tuple[str, ...]:
        """The names of the groups in this dataset, in order.

        >>> from tdmread import Group, TdmFile
        >>> TdmFile((Group("A", ()),)).group_names
        ('A',)
        """
        return tuple(group.name for group in self.groups)

    def group(self, name: str) -> Group:
        """Return the first group called `name`, or raise :class:`TdmError`.

        >>> from tdmread import Group, TdmFile
        >>> TdmFile((Group("A", ()),)).group("A").name
        'A'
        """
        for group in self.groups:
            if group.name == name:
                return group
        raise TdmError(f"no group named {quote(name)}")

    def channels(self) -> Iterator[tuple[Group, Channel]]:
        """Iterate over every ``(group, channel)`` pair in the dataset.

        >>> from tdmread import Channel, Group, TdmFile
        >>> dataset = TdmFile((Group("G", (Channel("a", "", "", "", ()),)),))
        >>> [(g.name, c.name) for g, c in dataset.channels()]
        [('G', 'a')]
        """
        for group in self.groups:
            for channel in group.channels:
                yield group, channel

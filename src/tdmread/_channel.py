"""The channel type returned inside :class:`tdmread.TdmFile`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from ._errors import TdmError, quote
from ._props import Properties, PropertyValue

Values = tuple[float, ...] | tuple[str, ...] | tuple[datetime, ...]


@dataclass(frozen=True)
class Channel:
    """One channel: its metadata and its decoded values.

    `data` is a tuple holding one kind of value: numbers (``int`` for integer types,
    ``float`` otherwise) for numeric channels, ``str`` for string channels, and naive
    ``datetime`` (local wall-clock time, cut to microseconds) for time channels.
    `value_type` is the .tdx valueType the values were stored as (empty when they come
    from the header or are generated), `representation` is the sequence representation
    (``explicit``, ``implicit_linear``, ``implicit_constant``, ``raw_linear`` or
    ``raw_linear_external``), `datatype` is the header's ``DT_*`` name, and
    `properties` holds the channel's custom properties.

    >>> from tdmread import Channel
    >>> volts = Channel("U", "V", "", "eFloat64Usi", (0.5, 1.5, 2.5))
    >>> len(volts), volts.unit, volts.data[1]
    (3, 'V', 1.5)
    >>> volts.properties
    {}
    """

    name: str
    unit: str
    description: str
    value_type: str
    data: Values
    representation: str = ""
    minimum: float | None = None
    maximum: float | None = None
    datatype: str = ""
    properties: Mapping[str, PropertyValue] = field(default_factory=Properties, hash=False)

    def __len__(self) -> int:
        """Number of values in the channel.

        >>> from tdmread import Channel
        >>> len(Channel("n", "", "", "eInt32Usi", (1, 2, 3)))
        3
        """
        return len(self.data)

    def numbers(self) -> tuple[float, ...]:
        """Return `data` typed as numbers, or raise :class:`TdmError` for text or times.

        Use it (or :meth:`strings`, :meth:`times`) when a type checker needs to know the
        kind of value; an empty channel gives ``()`` for all three.

        >>> from tdmread import Channel
        >>> sum(Channel("n", "", "", "eInt32Usi", (1, 2, 3)).numbers())
        6
        """
        return cast("tuple[float, ...]", self._only((int, float), "numbers"))

    def strings(self) -> tuple[str, ...]:
        """Return `data` typed as strings, or raise :class:`TdmError` for other values.

        >>> from tdmread import Channel
        >>> Channel("s", "", "", "", ("a", "b")).strings()
        ('a', 'b')
        """
        return cast("tuple[str, ...]", self._only((str,), "strings"))

    def times(self) -> tuple[datetime, ...]:
        """Return `data` typed as ``datetime`` values, or raise :class:`TdmError`.

        >>> from datetime import datetime
        >>> from tdmread import Channel
        >>> Channel("t", "", "", "eTimeUsi", (datetime(2026, 1, 2),)).times()[0].year
        2026
        """
        return cast("tuple[datetime, ...]", self._only((datetime,), "times"))

    def _only(self, kinds: tuple[type, ...], label: str) -> Values:
        for value in self.data:
            if isinstance(value, bool) or not isinstance(value, kinds):
                kind = type(value).__name__
                raise TdmError(f"channel {quote(self.name)} holds {kind} values, not {label}")
        return self.data

    def to_list(self) -> list[float] | list[str] | list[datetime]:
        """Return the values as a new list.

        >>> from tdmread import Channel
        >>> Channel("n", "", "", "eInt32Usi", (1, 2, 3)).to_list()
        [1, 2, 3]
        """
        return cast("list[float] | list[str] | list[datetime]", list(self.data))

    def to_numpy(self) -> Any:
        """Return the values as a NumPy array (``Any``: NumPy is an optional extra).

        The core library never imports NumPy; this raises :class:`TdmError` with an
        install hint when it is missing.

        >>> from tdmread import Channel, TdmError
        >>> channel = Channel("n", "", "", "eInt32Usi", (1, 2, 3))
        >>> try:
        ...     print(channel.to_numpy().tolist())
        ... except TdmError:
        ...     print([1, 2, 3])
        [1, 2, 3]
        """
        try:
            import numpy as np
        except ModuleNotFoundError as exc:
            raise TdmError(
                "NumPy is not installed; run 'pip install numpy' to use Channel.to_numpy()"
            ) from exc
        return np.asarray(self.data)

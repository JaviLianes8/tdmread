"""Exceptions raised while reading TDM/TDX files."""

from __future__ import annotations

# Text taken from a file is quoted in messages, but never more than this many characters,
# so a hostile header cannot turn an error message into a copy of itself.
_QUOTE_LIMIT = 40


class TdmError(Exception):
    """A TDM dataset is malformed or cannot be read.

    Every error tdmread raises for a bad dataset is a ``TdmError``; catching it is
    enough to handle any unreadable file.

    >>> from tdmread import Group, TdmError
    >>> try:
    ...     Group(name="G", channels=()).channel("missing")
    ... except TdmError as exc:
    ...     print(exc)
    no channel named 'missing' in group 'G'
    """


class TdmFileNotFoundError(TdmError, FileNotFoundError):
    """The .tdm header or the .tdx data file it needs is missing.

    It is both a :class:`TdmError` and a built-in :class:`FileNotFoundError`.

    >>> from tdmread import TdmFileNotFoundError, read_tdm
    >>> try:
    ...     read_tdm("no-such-file.tdm")
    ... except TdmFileNotFoundError as exc:
    ...     print(exc)
    TDM header not found: no-such-file.tdm
    """


class UnsupportedTdmError(TdmError):
    """The dataset uses a TDM feature outside the supported subset.

    tdmread raises this instead of guessing, so it never returns wrong numbers for a
    layout it does not understand.

    >>> from tdmread import TdmError, UnsupportedTdmError
    >>> issubclass(UnsupportedTdmError, TdmError)
    True
    """


def quote(text: object) -> str:
    """Return ``repr(text)`` cut to a bounded length for use in an error message."""
    shown = repr(text)
    if len(shown) <= _QUOTE_LIMIT:
        return shown
    return shown[: _QUOTE_LIMIT - 3] + "..."

"""Zero-dependency, typed reader for NI TDM/TDX files, using only the standard library."""

from __future__ import annotations

from ._errors import TdmError, TdmFileNotFoundError, UnsupportedTdmError
from ._model import Channel, Group, TdmFile
from ._reader import read_tdm

__version__ = "0.1.0"

__all__ = [
    "Channel",
    "Group",
    "TdmError",
    "TdmFile",
    "TdmFileNotFoundError",
    "UnsupportedTdmError",
    "read_tdm",
]

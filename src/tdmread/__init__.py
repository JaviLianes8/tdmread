"""Zero-dependency, typed reader for NI TDM/TDX files, using only the standard library."""

from __future__ import annotations

from ._binary import supported_value_types
from ._errors import TdmError, TdmFileNotFoundError, UnsupportedTdmError
from ._model import Channel, FileMetadata, Group, TdmFile
from ._reader import read_tdm

__version__ = "0.2.1"

__all__ = [
    "Channel",
    "FileMetadata",
    "Group",
    "TdmError",
    "TdmFile",
    "TdmFileNotFoundError",
    "UnsupportedTdmError",
    "read_tdm",
    "supported_value_types",
]

"""Exceptions raised while reading TDM/TDX files."""

from __future__ import annotations


class TdmError(Exception):
    """A TDM dataset is malformed or cannot be read."""


class TdmFileNotFoundError(TdmError, FileNotFoundError):
    """The .tdm header or its referenced .tdx data file is missing."""


class UnsupportedTdmError(TdmError):
    """The dataset uses a TDM feature outside the supported subset."""

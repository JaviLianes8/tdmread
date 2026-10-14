"""Locate the .tdx data file and read byte ranges from it on demand."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

from ._errors import TdmError, TdmFileNotFoundError, quote

StrPath = str | os.PathLike[str]


def locate(header: Path, url: str | None, override: StrPath | None) -> Path:
    """Return the .tdx path: `override` if given, else `url` next to the header.

    The header's `url` must name a file in the header's folder or below it; an absolute
    path, a drive, a URL scheme or a step out with ``..`` is refused, so a header cannot
    point the reader at an unrelated file. Pass `override` to read a .tdx elsewhere.
    """
    if override is not None:
        return Path(override)
    if not url:
        raise TdmError("the .tdm header does not name its .tdx file")
    posix, windows = PurePosixPath(url), PureWindowsPath(url)
    if (
        "\x00" in url
        or ":" in url
        or posix.is_absolute()
        or windows.is_absolute()
        or ".." in windows.parts
    ):
        raise TdmError(f"the .tdx location {quote(url)} is outside the header's folder")
    return header.parent / Path(*windows.parts)


class TdxSource:
    """Read ranges from a .tdx file, opening it only when a value is first needed."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: BinaryIO | None = None
        self._size = 0

    def __enter__(self) -> TdxSource:
        return self

    def __exit__(self, *exc: object) -> None:
        if self._handle is not None:
            self._handle.close()

    def read(self, start: int, end: int) -> bytes:
        """Return bytes ``start`` to ``end`` or raise when the file is shorter."""
        handle = self._open()
        if end > self._size:
            raise TdmError(
                f"a value block reaches byte {end} but the .tdx holds {self._size} bytes"
            )
        handle.seek(start)
        data = handle.read(end - start)
        if len(data) != end - start:
            raise TdmError("the .tdx file changed while it was being read")
        return data

    def _open(self) -> BinaryIO:
        if self._handle is None:
            try:
                self._handle = open(self._path, "rb")  # noqa: SIM115 - closed by __exit__
            except FileNotFoundError:
                raise TdmFileNotFoundError(
                    f"TDX data not found: {quote(str(self._path))}"
                ) from None
            except PermissionError:
                raise
            except OSError as exc:
                # A name the system cannot open (too long, reserved characters) is a bad
                # dataset, not an operating-system failure.
                raise TdmError(
                    f"cannot open the .tdx {quote(str(self._path))}: {exc.strerror}"
                ) from None
            self._size = os.fstat(self._handle.fileno()).st_size
        return self._handle

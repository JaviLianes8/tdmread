"""Locate the .tdx data file and read byte ranges from it on demand."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import BinaryIO

from ._errors import TdmError, TdmFileNotFoundError, quote

StrPath = str | os.PathLike[str]
# Characters no Windows file name can hold, and the drive or stream separator.
_FORBIDDEN = frozenset(':<>"|?*')


def locate(header: Path, url: str | None, override: StrPath | None) -> Path:
    """Return the .tdx path: `override` if given, else `url` next to the header.

    The header's `url` must name a file in the header's folder or below it; an absolute
    path, a drive, a URL scheme, a step out with ``..``, a name that is only dots or
    spaces, and characters no Windows file name can hold are refused, so a header cannot
    point the reader at an unrelated file. Pass `override` to read a .tdx elsewhere.
    """
    if override is not None:
        return Path(override)
    if not url:
        raise TdmError("the .tdm header does not name its .tdx file")
    posix, windows = PurePosixPath(url), PureWindowsPath(url)
    if ":" in url or posix.anchor or windows.anchor or ".." in windows.parts:
        raise TdmError(f"the .tdx location {quote(url)} is outside the header's folder")
    if (
        any(ord(char) < 32 or char in _FORBIDDEN for char in url)
        or url.replace("\\", "/").rsplit("/", 1)[-1].strip(" .") == ""
    ):
        raise TdmError(f"the .tdx location {quote(url)} is not a valid file name")
    return header.parent / Path(*windows.parts)


class TdxSource:
    """Read ranges from a .tdx file, opening it only when a value is first needed."""

    def __init__(self, path: Path, label: str = "") -> None:
        self._path = path
        # How messages name the file: the header's url (or the given path), quoted short.
        self._label = quote(label or str(path))
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

    def read_items(self, start: int, stride: int, size: int, count: int, end: int) -> bytes:
        """Return `count` items of `size` bytes, `stride` bytes apart from `start`.

        Close items are read as one range; sparse ones are read one by one, so the bytes
        read never exceed four times the bytes returned.
        """
        if stride <= 4 * size:
            span = self.read(start, end)
            return b"".join(span[i * stride : i * stride + size] for i in range(count))
        self.read(end - size, end)  # checks that the last item lies inside the file
        handle = self._open()
        pieces = []
        for index in range(count):
            handle.seek(start + index * stride)
            pieces.append(handle.read(size))
        return b"".join(pieces)

    def _open(self) -> BinaryIO:
        if self._handle is None:
            try:
                self._handle = open(self._path, "rb")  # noqa: SIM115 - closed by __exit__
            except FileNotFoundError:
                raise TdmFileNotFoundError(f"TDX data not found: {self._label}") from None
            except PermissionError:
                if self._path.is_dir():
                    raise TdmError(f"the .tdx {self._label} is a folder") from None
                raise
            except ValueError:
                raise TdmError(f"cannot open the .tdx {self._label}") from None
            except OSError as exc:
                # A name the system cannot open (too long, reserved characters) is a bad
                # dataset, not an operating-system failure.
                raise TdmError(f"cannot open the .tdx {self._label}: {exc.strerror}") from None
            self._size = os.fstat(self._handle.fileno()).st_size
        return self._handle

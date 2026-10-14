"""Parse a .tdm XML header and read its channel values."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from ._binary import byte_order_prefix
from ._channel import Channel
from ._errors import TdmError, TdmFileNotFoundError
from ._model import FileMetadata, Group, TdmFile
from ._numbers import is_float
from ._props import read_properties
from ._sequence import GENERATED_ALLOWANCE, Context, Sequence, read_sequence
from ._tdx import StrPath, TdxSource, locate
from ._xml import ElementMap, child_text, local_name, refs, resolve

_BLOCKS = frozenset({"block", "block_bm", "block_mr"})
_DTD_MARKS = ("<!DOCTYPE", "<!ENTITY")


def read_tdm(tdm_path: StrPath, tdx_path: StrPath | None = None) -> TdmFile:
    """Read the TDM dataset whose XML header is `tdm_path`.

    The .tdx data file is the one the header names, in the header's folder; pass
    `tdx_path` to read another one. The .tdx is opened only if a channel stores values
    in it, so a header whose values are all inline or generated needs none.

    Raises :class:`TdmFileNotFoundError` when the header or a needed .tdx is missing,
    :class:`UnsupportedTdmError` for a layout outside the supported subset, and
    :class:`TdmError` for any other malformed dataset.

    >>> import pathlib, tempfile
    >>> from tdmread import read_tdm
    >>> header = pathlib.Path(tempfile.mkdtemp()) / "demo.tdm"
    >>> _ = header.write_text(
    ...     '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
    ...     '<tdm_root id="r"><name>demo</name><channelgroups>#xpointer(id("g"))'
    ...     '</channelgroups></tdm_root><tdm_channelgroup id="g"><name>G</name>'
    ...     '<channels>#xpointer(id("c"))</channels></tdm_channelgroup>'
    ...     '<tdm_channel id="c"><name>U</name><unit_string>V</unit_string>'
    ...     '<local_columns>#xpointer(id("l"))</local_columns></tdm_channel>'
    ...     '<localcolumn id="l"><values>#xpointer(id("s"))</values></localcolumn>'
    ...     '<double_sequence id="s"><values>0.5 1.5</values></double_sequence>'
    ...     "</usi:data></usi:tdm>"
    ... )
    >>> dataset = read_tdm(header)
    >>> dataset.metadata.name, dataset.group("G").channel("U").data
    ('demo', (0.5, 1.5))
    """
    header = Path(tdm_path)
    if not header.is_file():
        raise TdmFileNotFoundError(f"TDM header not found: {header}")
    root = _parse(header.read_bytes())

    if local_name(root) != "tdm":
        raise TdmError("the file is XML but not a TDM header (its root is not <tdm>)")
    by_id: ElementMap = {}
    blocks: ElementMap = {}
    file_el: ET.Element | None = None
    tdm_root: ET.Element | None = None
    for element in root.iter():
        ident = element.get("id")
        name = local_name(element)
        if name == "file" and file_el is None:
            file_el = element
        if name == "tdm_root" and tdm_root is None:
            tdm_root = element
        if ident is None:
            continue
        if name in _BLOCKS:
            blocks.setdefault(ident, element)
        else:
            by_id.setdefault(ident, element)

    order = file_el.get("byteOrder", "littleEndian") if file_el is not None else "littleEndian"
    prefix = byte_order_prefix(order)
    url = file_el.get("url") if file_el is not None else None
    tdx = locate(header, url, tdx_path) if (blocks or tdx_path is not None) else header
    allowance = GENERATED_ALLOWANCE + (_size(tdx) if blocks else 0)
    with TdxSource(tdx) as source:
        ctx = Context(by_id, blocks, source, prefix, [allowance])
        groups = tuple(_read_groups(tdm_root, ctx))
    return TdmFile(
        groups=groups, metadata=_metadata(tdm_root), properties=read_properties(tdm_root)
    )


def _parse(data: bytes) -> ET.Element:
    # TDM headers never declare a DTD; refusing one rules out entity expansion and
    # external entities whatever XML library version runs underneath.
    for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
        if any(mark.encode(encoding) in data for mark in _DTD_MARKS):
            raise TdmError("the .tdm header declares a DTD, which TDM headers never use")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise TdmError(f"the .tdm header is not well-formed XML ({exc})") from None
    except LookupError:
        raise TdmError("the .tdm header declares an unknown text encoding") from None


def _size(path: Path) -> int:
    try:
        return os.stat(path).st_size
    except OSError:
        return 0


def _read_groups(tdm_root: ET.Element | None, ctx: Context) -> list[Group]:
    groups = []
    for gid in refs(child_text(tdm_root, "channelgroups")):
        group_el = ctx.by_id.get(gid)
        if group_el is None:
            continue
        channels = [
            _read_channel(ctx.by_id[cid], ctx)
            for cid in refs(child_text(group_el, "channels"))
            if cid in ctx.by_id
        ]
        groups.append(
            Group(
                name=child_text(group_el, "name"),
                channels=tuple(channels),
                description=child_text(group_el, "description"),
                properties=read_properties(group_el),
            )
        )
    return groups


def _read_channel(channel_el: ET.Element, ctx: Context) -> Channel:
    column = resolve(ctx.by_id, channel_el, "local_columns")
    sequence = Sequence("", "", ()) if column is None else read_sequence(channel_el, column, ctx)
    return Channel(
        name=child_text(channel_el, "name"),
        unit=child_text(channel_el, "unit_string"),
        description=child_text(channel_el, "description"),
        value_type=sequence.value_type,
        data=sequence.values,
        representation=sequence.representation,
        minimum=_optional_float(child_text(channel_el, "minimum")),
        maximum=_optional_float(child_text(channel_el, "maximum")),
        datatype=child_text(channel_el, "datatype"),
        properties=read_properties(channel_el),
    )


def _metadata(tdm_root: ET.Element | None) -> FileMetadata:
    return FileMetadata(
        name=child_text(tdm_root, "name"),
        title=child_text(tdm_root, "title"),
        description=child_text(tdm_root, "description"),
        author=child_text(tdm_root, "author"),
        datetime=child_text(tdm_root, "datetime"),
    )


def _optional_float(text: str) -> float | None:
    return float(text) if is_float(text) else None

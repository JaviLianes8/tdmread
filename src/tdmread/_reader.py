"""Parse a .tdm XML header and read its channel data from the .tdx binary."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ._binary import byte_order_prefix
from ._errors import TdmError, TdmFileNotFoundError
from ._model import Channel, Group, TdmFile
from ._sequence import Sequence, read_sequence
from ._xml import child_text, one_ref, read_metadata, refs

StrPath = str | Path

_ElementMap = dict[str | None, ET.Element]


def read_tdm(tdm_path: StrPath, tdx_path: StrPath | None = None) -> TdmFile:
    """Read a TDM dataset from `tdm_path`, locating the .tdx by the header reference.

    Pass `tdx_path` to override the data file the header points to. Explicit channels
    are decoded from the .tdx; implicit-linear channels are generated and need no .tdx,
    so the data file is only read when at least one explicit block refers to it.

    Raises :class:`TdmFileNotFoundError` when a required file is missing and
    :class:`UnsupportedTdmError` for features outside the supported subset.
    """
    header = Path(tdm_path)
    if not header.is_file():
        raise TdmFileNotFoundError(f"TDM header not found: {header}")

    root = ET.parse(header).getroot()
    # A purely implicit dataset generates every axis and has no binary file descriptor.
    file_el = root.find(".//{*}file")
    byte_order = file_el.get("byteOrder", "littleEndian") if file_el is not None else "littleEndian"
    prefix = byte_order_prefix(byte_order)

    blocks: _ElementMap = {b.get("id"): b for b in root.findall(".//{*}file/{*}block")}
    by_id: _ElementMap = {el.get("id"): el for el in root.iter() if el.get("id")}
    data = _read_tdx(header, file_el, tdx_path) if (blocks and file_el is not None) else b""

    groups = tuple(_read_groups(root, by_id, blocks, data, prefix))
    return TdmFile(groups=groups, metadata=read_metadata(root))


def _read_tdx(header: Path, file_el: ET.Element, override: StrPath | None) -> bytes:
    if override is not None:
        tdx = Path(override)
    else:
        url = file_el.get("url")
        if not url:
            raise TdmError("the .tdm header does not reference a .tdx file")
        tdx = header.parent / url
    try:
        return tdx.read_bytes()
    except FileNotFoundError as exc:
        raise TdmFileNotFoundError(f"TDX data not found: {tdx}") from exc


def _read_groups(
    root: ET.Element,
    by_id: _ElementMap,
    blocks: _ElementMap,
    data: bytes,
    prefix: str,
) -> list[Group]:
    tdm_root = root.find(".//{*}tdm_root")
    group_ids = refs(child_text(tdm_root, "channelgroups")) if tdm_root is not None else []
    groups = []
    for gid in group_ids:
        group_el = by_id.get(gid)
        if group_el is None:
            continue
        channels = [
            _read_channel(by_id[cid], by_id, blocks, data, prefix)
            for cid in refs(child_text(group_el, "channels"))
            if cid in by_id
        ]
        groups.append(
            Group(
                name=child_text(group_el, "name"),
                channels=tuple(channels),
                description=child_text(group_el, "description"),
            )
        )
    return groups


def _read_channel(
    channel_el: ET.Element,
    by_id: _ElementMap,
    blocks: _ElementMap,
    data: bytes,
    prefix: str,
) -> Channel:
    column = by_id.get(one_ref(child_text(channel_el, "local_columns")))
    if column is None:
        sequence = Sequence("", "", ())
    else:
        sequence = read_sequence(channel_el, column, by_id, blocks, data, prefix)
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
    )


def _optional_float(text: str) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None

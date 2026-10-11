"""Parse a .tdm XML header and read its channel data from the .tdx binary."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ._binary import byte_order_prefix, decode_block
from ._errors import TdmError, TdmFileNotFoundError, UnsupportedTdmError
from ._model import Channel, Group, TdmFile

_REF = re.compile(r'id\("([^"]+)"\)')

StrPath = str | Path


def read_tdm(tdm_path: StrPath, tdx_path: StrPath | None = None) -> TdmFile:
    """Read a TDM dataset from `tdm_path`, locating the .tdx by the header reference.

    Pass `tdx_path` to override the data file the header points to. Raises
    :class:`TdmFileNotFoundError` if either file is missing, and
    :class:`UnsupportedTdmError` for features outside the supported subset.
    """
    header = Path(tdm_path)
    if not header.is_file():
        raise TdmFileNotFoundError(f"TDM header not found: {header}")

    root = ET.parse(header).getroot()
    file_el = root.find(".//{*}file")
    if file_el is None:
        raise TdmError("the .tdm header has no <file> block descriptor")
    prefix = byte_order_prefix(file_el.get("byteOrder", "littleEndian"))

    data = _read_tdx(header, file_el, tdx_path)
    blocks = {b.get("id"): b for b in root.findall(".//{*}file/{*}block")}
    by_id = {el.get("id"): el for el in root.iter() if el.get("id")}

    return TdmFile(groups=tuple(_read_groups(root, by_id, blocks, data, prefix)))


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
    by_id: dict[str | None, ET.Element],
    blocks: dict[str | None, ET.Element],
    data: bytes,
    prefix: str,
) -> list[Group]:
    tdm_root = root.find(".//{*}tdm_root")
    group_ids = _refs(_child_text(tdm_root, "channelgroups")) if tdm_root is not None else []
    groups = []
    for gid in group_ids:
        group_el = by_id.get(gid)
        if group_el is None:
            continue
        name = _child_text(group_el, "name")
        channels = [
            _read_channel(by_id[cid], by_id, blocks, data, prefix)
            for cid in _refs(_child_text(group_el, "channels"))
            if cid in by_id
        ]
        groups.append(Group(name=name, channels=tuple(channels)))
    return groups


def _read_channel(
    channel_el: ET.Element,
    by_id: dict[str | None, ET.Element],
    blocks: dict[str | None, ET.Element],
    data: bytes,
    prefix: str,
) -> Channel:
    name = _child_text(channel_el, "name")
    unit = _child_text(channel_el, "unit_string")
    description = _child_text(channel_el, "description")
    value_type, values = _read_values(channel_el, by_id, blocks, data, prefix)
    return Channel(
        name=name,
        unit=unit,
        description=description,
        value_type=value_type,
        data=values,
    )


def _read_values(
    channel_el: ET.Element,
    by_id: dict[str | None, ET.Element],
    blocks: dict[str | None, ET.Element],
    data: bytes,
    prefix: str,
) -> tuple[str, tuple[float, ...]]:
    column = by_id.get(_one_ref(_child_text(channel_el, "local_columns")))
    if column is None:
        return "", ()
    representation = _child_text(column, "sequence_representation")
    if representation and representation != "explicit":
        raise UnsupportedTdmError(
            f"unsupported sequence representation {representation!r}; "
            "only 'explicit' channels are read"
        )
    sequence = by_id.get(_one_ref(_child_text(column, "values")))
    if sequence is None:
        return "", ()
    values_el = sequence.find("{*}values")
    block = blocks.get(values_el.get("external")) if values_el is not None else None
    if block is None:
        return "", ()
    value_type = block.get("valueType", "")
    byte_offset = int(block.get("byteOffset", "0"))
    length = int(block.get("length", "0"))
    return value_type, decode_block(data, prefix, value_type, byte_offset, length)


def _child_text(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    child = element.find(f"{{*}}{name}")
    return (child.text or "").strip() if child is not None else ""


def _refs(text: str) -> list[str]:
    return _REF.findall(text)


def _one_ref(text: str) -> str | None:
    found = _REF.findall(text)
    return found[0] if found else None

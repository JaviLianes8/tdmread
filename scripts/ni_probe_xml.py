"""Write one hand-made probe dataset (a .tdm header and its .tdx) for NI's reader to read.

Used by ``make_ni_probes.py``. Every probe holds one group ``G`` whose channels each get
their own value sequence, submatrix and local column, with ids NI's reader accepts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DATATYPES = {
    "byte_sequence": "DT_BYTE",
    "short_sequence": "DT_SHORT",
    "long_sequence": "DT_LONG",
    "longlong_sequence": "DT_LONGLONG",
    "float_sequence": "DT_FLOAT",
    "double_sequence": "DT_DOUBLE",
    "string_sequence": "DT_STRING",
    "time_sequence": "DT_DATE",
}
EXPLICIT = "<sequence_representation>explicit</sequence_representation>"
HEAD = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>'
    '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0" version="1.0">'
    "<usi:documentation><usi:exporter>probe</usi:exporter>"
    "<usi:exporterVersion>1</usi:exporterVersion></usi:documentation>"
    '<usi:model modelName="probe" modelVersion="1.0">'
    '<usi:include nsUri="http://www.ni.com/DataModels/USI/TDM/1_0"/></usi:model>'
)


def ref(*ids: str) -> str:
    """Return an ``#xpointer(...)`` reference to `ids`."""
    return "#xpointer(" + " ".join(f'id("{i}")' for i in ids) + ")"


def _channel(index: int, ch: dict[str, Any]) -> tuple[str, str, str]:
    base = 100 + index * 10
    cid, sid, lid, qid = (f"usi{base + k}" for k in range(4))
    name, seq_tag = ch["name"], ch.get("seq")
    sequence = f'<{seq_tag} id="{qid}">{ch.get("values", "")}</{seq_tag}>' if seq_tag else ""
    datatype = ch.get("datatype") or (DATATYPES[seq_tag] if seq_tag else "")
    dt_xml = f"<datatype>{datatype}</datatype>" if datatype else ""
    rows = ch.get("rows")
    rows_xml = f"<number_of_rows>{rows}</number_of_rows>" if rows is not None else ""
    values_ref = f"<values>{ref(qid)}</values>" if seq_tag else ""
    body = (
        f'<tdm_channel id="{cid}"><name>{name}</name><group>{ref("usi2")}</group>'
        f"{dt_xml}{ch.get('chan_extra', '')}<local_columns>{ref(lid)}</local_columns>"
        f'</tdm_channel><submatrix id="{sid}"><name>{name}</name>'
        f"<measurement>{ref('usi2')}</measurement>{rows_xml}"
        f"<local_columns>{ref(lid)}</local_columns></submatrix>"
        f'<localcolumn id="{lid}"><name>{name}</name>'
        f"<measurement_quantity>{ref(cid)}</measurement_quantity>"
        f"<submatrix>{ref(sid)}</submatrix><global_flag>15</global_flag>"
        f"<independent>0</independent>{ch.get('column', EXPLICIT)}{values_ref}</localcolumn>"
    )
    return sequence, body, cid


def write_probe(
    folder: Path,
    stem: str,
    channels: list[dict[str, Any]],
    blocks: str,
    tdx: bytes,
    byte_order: str | None = "littleEndian",
) -> None:
    """Write ``stem.tdm`` and ``stem.tdx`` into `folder`."""
    parts = [_channel(i, ch) for i, ch in enumerate(channels)]
    order = f'byteOrder="{byte_order}" ' if byte_order is not None else ""
    subs = [f"usi{100 + i * 10 + 1}" for i in range(len(channels))]
    xml = (
        HEAD
        + f'<usi:include><file {order}url="{stem}.tdx">{blocks}</file></usi:include><usi:data>'
        + "".join(p[0] for p in parts)
        + f'<tdm_root id="usi1"><name>{stem}</name>'
        + f"<channelgroups>{ref('usi2')}</channelgroups></tdm_root>"
        + f'<tdm_channelgroup id="usi2"><name>G</name><root>{ref("usi1")}</root>'
        + f"<channels>{ref(*(p[2] for p in parts))}</channels>"
        + f"<submatrices>{ref(*subs)}</submatrices></tdm_channelgroup>"
        + "".join(p[1] for p in parts)
        + "</usi:data></usi:tdm>"
    )
    (folder / f"{stem}.tdm").write_bytes(xml.encode("utf-8"))
    (folder / f"{stem}.tdx").write_bytes(tdx)

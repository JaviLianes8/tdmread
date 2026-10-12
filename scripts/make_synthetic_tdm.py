"""Write the hand-made TDM/TDX fixtures in tests/fixtures/synthetic.

The always-on tests run against these files. Every value is generated here from a
formula, so the files copy nothing from any third-party sample:

* ``Synthetic.tdm`` + ``.tdx``: little-endian. Group ``Amplitudes`` holds ``A = k`` with
  ``k * sin(STEP * i)``; group ``Frequencies`` holds ``F = k`` with ``sin(k * STEP * i)``.
* ``Synthetic-be.tdm`` + ``.tdx``: the same values stored big-endian.
* ``Synthetic_implicit.tdm``: the ``Amplitudes`` channels are implicit_linear
  (``OFFSET + INCREMENT * i``), lengths from ``NI_ChannelLength`` or the submatrix row
  count; the ``Frequencies`` channels stay explicit and read ``Synthetic.tdx``.

    python scripts/make_synthetic_tdm.py
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic"
LENGTH = 100
STEP = 0.05
OFFSET, INCREMENT = 0.25, 0.5
SCALES = (1, 2, 4, 8, 16)
GROUPS = (("Amplitudes", "A"), ("Frequencies", "F"))


def _values(group: str, k: int) -> list[float]:
    if group == "Amplitudes":
        return [k * math.sin(STEP * i) for i in range(LENGTH)]
    return [math.sin(k * STEP * i) for i in range(LENGTH)]


def _channels() -> list[tuple[str, str, list[float]]]:
    return [(g, f"{p} = {k}", _values(g, k)) for g, p in GROUPS for k in SCALES]


def _tdx(order: str) -> bytes:
    fmt = ("<" if order == "littleEndian" else ">") + f"{LENGTH}d"
    return b"".join(struct.pack(fmt, *values) for _, _, values in _channels())


def _refs(ids: list[str]) -> str:
    return "#xpointer(" + " ".join(f'id("{i}")' for i in ids) + ")"


def _channel_xml(n: int, group_id: str, name: str, values: list[float], implicit: bool) -> str:
    length_attr = (
        ""
        if implicit and n % 2
        else (f'        <long_attribute name="NI_ChannelLength">{LENGTH}</long_attribute>\n')
    )
    if implicit:
        column = (
            "      <sequence_representation>implicit_linear</sequence_representation>\n"
            f"      <generation_parameters>{OFFSET} {INCREMENT}</generation_parameters>\n"
        )
    else:
        column = (
            "      <sequence_representation>explicit</sequence_representation>\n"
            f"      <values>{_refs([f'seq{n}'])}</values>\n"
        )
    sequence = (
        ""
        if implicit
        else (f'    <double_sequence id="seq{n}"><values external="inc{n}"/></double_sequence>\n')
    )
    return (
        f'    <tdm_channel id="ch{n}">\n      <name>{name}</name>\n'
        f"      <group>{_refs([group_id])}</group>\n      <datatype>DT_DOUBLE</datatype>\n"
        f"      <minimum>{min(values)!r}</minimum>\n      <maximum>{max(values)!r}</maximum>\n"
        f"      <instance_attributes>\n{length_attr}      </instance_attributes>\n"
        f"      <local_columns>{_refs([f'lc{n}'])}</local_columns>\n    </tdm_channel>\n"
        f'    <submatrix id="sm{n}">\n      <number_of_rows>{LENGTH}</number_of_rows>\n'
        f"      <local_columns>{_refs([f'lc{n}'])}</local_columns>\n    </submatrix>\n"
        f'    <localcolumn id="lc{n}">\n      <measurement_quantity>{_refs([f"ch{n}"])}'
        f"</measurement_quantity>\n      <submatrix>{_refs([f'sm{n}'])}</submatrix>\n"
        f"{column}    </localcolumn>\n{sequence}"
    )


def _tdm(name: str, tdx: str, order: str, implicit: bool) -> str:
    channels = _channels()
    blocks = "".join(
        f'      <block id="inc{n}" valueType="eFloat64Usi" byteOffset="{n * LENGTH * 8}"'
        f' length="{LENGTH}"/>\n'
        for n in range(len(channels))
    )
    group_ids = {g: f"grp{gi}" for gi, (g, _) in enumerate(GROUPS)}
    body = "".join(
        _channel_xml(n, group_ids[g], c, v, implicit and g == "Amplitudes")
        for n, (g, c, v) in enumerate(channels)
    )
    groups = "".join(
        f'    <tdm_channelgroup id="grp{gi}">\n      <name>{g}</name>\n'
        f"      <root>{_refs(['root'])}</root>\n      <channels>"
        f"{_refs([f'ch{n}' for n, (cg, _, _) in enumerate(channels) if cg == g])}</channels>\n"
        f"    </tdm_channelgroup>\n"
        for gi, (g, _) in enumerate(GROUPS)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Hand-made tdmread test fixture, written by scripts/make_synthetic_tdm.py. -->\n"
        '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0" version="1.0">\n'
        f'  <usi:include>\n    <file url="{tdx}" byteOrder="{order}">\n{blocks}'
        "    </file>\n  </usi:include>\n  <usi:data>\n"
        f'    <tdm_root id="root">\n      <name>{name}</name>\n'
        "      <description>Generated sine signals for the tdmread tests.</description>\n"
        "      <author>tdmread test suite</author>\n"
        f"      <channelgroups>{_refs(['grp0', 'grp1'])}</channelgroups>\n    </tdm_root>\n"
        f"{groups}{body}  </usi:data>\n</usi:tdm>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, order in (("Synthetic", "littleEndian"), ("Synthetic-be", "bigEndian")):
        (OUT / f"{stem}.tdx").write_bytes(_tdx(order))
        tdm = _tdm(f"{stem}.TDM", f"{stem}.tdx", order, implicit=False)
        (OUT / f"{stem}.tdm").write_bytes(tdm.encode("utf-8"))
    implicit = _tdm("Synthetic_implicit.TDM", "Synthetic.tdx", "littleEndian", implicit=True)
    (OUT / "Synthetic_implicit.tdm").write_bytes(implicit.encode("utf-8"))


if __name__ == "__main__":
    main()

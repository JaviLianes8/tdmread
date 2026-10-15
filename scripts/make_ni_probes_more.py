"""Probe definitions for times, row counts, representations and block layouts.

Part of ``make_ni_probes.py``; run that script, not this one.
"""

from __future__ import annotations

import struct
from typing import Any

from make_ni_probes import OUT, blk, column, ext
from ni_probe_xml import write_probe

BM = "block_bm"


def times() -> None:
    le = struct.pack("<Qq", 2**63, 3874844079) + struct.pack("<Qq", 0, 0)
    le += struct.pack("<Qq", 0, -86400) + struct.pack("<Qq", 1, 0)
    chan = {"name": "t", "seq": "time_sequence", "values": ext("inc0"), "rows": 4}
    chan["datatype"] = "DT_DATE"
    write_probe(OUT, "p05_time", [chan], blk(0, 0, 4, "eTimeUsi"), le)
    be = struct.pack(">qQ", 3874844079, 2**63) + struct.pack(">qQ", 0, 0)
    be += struct.pack(">qQ", -86400, 2**62)
    chan = {"name": "t", "seq": "time_sequence", "values": ext("inc0"), "rows": 3}
    write_probe(OUT, "p05_time_be", [chan], blk(0, 0, 3, "eTimeUsi"), be, "bigEndian")
    raw = struct.pack("<6d", 1, 2, 3, 4, 5, 6)
    chans = [
        {"name": "rows3_len6", "seq": "double_sequence", "values": ext("inc0"), "rows": 3},
        {"name": "rows8_len6", "seq": "double_sequence", "values": ext("inc1"), "rows": 8},
        {"name": "norows_len6", "seq": "double_sequence", "values": ext("inc2"), "rows": None},
    ]
    blocks = "".join(blk(i, 0, 6, "eFloat64Usi") for i in range(3))
    write_probe(OUT, "p06_rows", chans, blocks, raw)


def representations() -> None:
    raw16, dbl = struct.pack("<3h", 0, 2, 4), struct.pack("<5d", 9, 9, 9, 9, 9)
    b16, bd = blk(0, 0, 3, "eInt16Usi"), blk(0, 0, 5, "eFloat64Usi")
    short = {"seq": "short_sequence", "values": ext("inc0"), "rows": 3, "datatype": "DT_DOUBLE"}
    stored = {"seq": "double_sequence", "values": ext("inc0"), "rows": 5}
    gen: dict[str, Any] = {"rows": 3, "datatype": "DT_DOUBLE"}
    cases: dict[str, tuple[dict[str, Any], str, bytes]] = {
        "a_lin_with_values": (stored | {"column": column("implicit_linear", "-0.5 1.2")}, bd, dbl),
        "b_lin_no_values": (
            gen | {"column": column("implicit_linear", "10 2"), "rows": 4},
            "",
            b"",
        ),
        "c_constant": (gen | {"column": column("implicit_constant", "7.5")}, "", b""),
        "d_raw_linear_1_05": (short | {"column": column("raw_linear", "1 0.5")}, b16, raw16),
        "e_raw_linear_3_2": (short | {"column": column("raw_linear", "3 2")}, b16, raw16),
        "f_raw_linear_external": (
            short | {"column": column("raw_linear_external", "3 2")},
            b16,
            raw16,
        ),
        "g_saw": (gen | {"column": column("implicit_saw", "0 1 3"), "rows": 7}, "", b""),
        "h_raw_poly": (short | {"column": column("raw_polynomial", "2 1 2 3")}, b16, raw16),
        "i_implicit_alias": (gen | {"column": column("implicit", "10 2"), "rows": 4}, "", b""),
        "j_lin_one_param": (gen | {"column": column("implicit_linear", "5")}, "", b""),
        "k_lin_no_param": (gen | {"column": column("implicit_linear")}, "", b""),
        "l_lin_long": (
            gen | {"column": column("implicit_linear", "10 2"), "rows": 4, "datatype": "DT_LONG"},
            "",
            b"",
        ),
        "m_lin_three_params": (gen | {"column": column("implicit_linear", "10 2 99")}, "", b""),
        "n_no_repr": (stored | {"column": ""}, bd, dbl),
        "o_const_no_values_long": (
            gen | {"column": column("implicit_constant", "7.5"), "datatype": "DT_LONG"},
            "",
            b"",
        ),
        "p_raw_linear_double": (
            stored | {"datatype": "DT_DOUBLE", "column": column("raw_linear", "3 2")},
            bd,
            dbl,
        ),
    }
    for stem, (chan, blocks, tdx) in cases.items():
        write_probe(OUT, "p07_" + stem, [chan | {"name": stem}], blocks, tdx)
    for i, (rows, length) in enumerate([(4, 6), (4, None), (None, 5)]):
        attr = f'<long_attribute name="NI_ChannelLength">{length}</long_attribute>'
        extra = f"<instance_attributes>{attr}</instance_attributes>" if length is not None else ""
        chan = gen | {"name": "x", "column": column("implicit_linear", "0 1"), "rows": rows}
        write_probe(OUT, f"p10_implen_{i}", [chan | {"chan_extra": extra}], "", b"")
    chan = gen | {"name": "x", "column": column("implicit_linear", "1e3 -0.25"), "rows": 5}
    write_probe(OUT, "p13_linear_negative", [chan], "", b"")
    raw32 = struct.pack("<3i", -10, 0, 7)
    chan = {"name": "x", "seq": "long_sequence", "values": ext("inc0"), "rows": 3}
    chan |= {"datatype": "DT_DOUBLE", "column": column("raw_linear", "-1.5 0.25 9")}
    write_probe(OUT, "p14_raw_int32", [chan], blk(0, 0, 3, "eInt32Usi"), raw32)


def _two(kind: str, extra_a: str, extra_b: str, offset_b: int = 8) -> str:
    first = blk(0, 0, 3, "eFloat64Usi", kind).replace(" valueType", f" {extra_a} valueType")
    second = blk(1, offset_b, 3, "eInt32Usi", kind)
    return first + second.replace(" valueType", f" {extra_b} valueType")


def layouts() -> None:
    rec = b"".join(struct.pack("<di", a, b) for a, b in [(1.5, 10), (2.5, 20), (3.5, 30)])
    a = {"name": "A", "seq": "double_sequence", "values": ext("inc0"), "rows": 3}
    b = {"name": "B", "seq": "long_sequence", "values": ext("inc1"), "rows": 3}
    off, size = "blockOffset", "blockSize"
    mr = ' valuesPerScan="2"'
    cases = {
        "bm_a_12_8": _two(BM, f'{off}="12" {size}="8"', f'{off}="12" {size}="4"'),
        "bm_b_8_12": _two(BM, f'{off}="8" {size}="12"', f'{off}="4" {size}="12"'),
        "bm_c_0_12": _two(BM, f'{off}="0" {size}="12"', f'{off}="8" {size}="12"', 0),
        "mr_a": _two("block_mr", f'{off}="0" {size}="12"{mr}', f'{off}="8" {size}="12"{mr}'),
        "blk_blocksize": _two("block", f'{size}="12"', f'{size}="12"'),
        "blk_blockoffset": _two("block", f'{off}="12"', f'{off}="12"'),
    }
    for stem, blocks in cases.items():
        write_probe(OUT, "p08_" + stem, [a, b], blocks, rec)
    texts = [b"ab\x00cde\x00\x00f\x00", "été\x00x\x00".encode(), b"ab\x00cd"]
    for i, raw in enumerate(texts):
        chan = {"name": "s", "seq": "string_sequence", "values": ext("inc0"), "rows": 3}
        write_probe(OUT, f"p09_strext_{i}", [chan], blk(0, 0, 3, "eStringUsi"), raw)
    write_probe(OUT, "p11_past_end", [a], blk(0, 20, 3, "eFloat64Usi"), rec)
    a2 = a | {"name": "A2", "values": ext("inc1")}
    blocks = blk(0, 0, 2, "eFloat64Usi") + blk(1, 4, 2, "eFloat64Usi")
    write_probe(OUT, "p11_overlap", [a, a2], blocks, rec)
    raw32 = struct.pack("<3i", -10, 0, 7)
    chan = {"name": "x", "seq": "long_sequence", "values": ext("inc0"), "rows": 3}
    write_probe(OUT, "p15_no_byteorder", [chan], blk(0, 0, 3, "eInt32Usi"), raw32, None)
    chan = {"name": "x", "seq": "float_sequence", "values": ext("inc0"), "rows": 2}
    raw = struct.pack("<2f", 0.1, 16777217.0)
    write_probe(OUT, "p16_float32_in_float", [chan], blk(0, 0, 2, "eFloat32Usi"), raw)

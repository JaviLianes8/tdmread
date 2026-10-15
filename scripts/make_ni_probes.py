"""Write the hand-made probe datasets in tests/fixtures/ni_probes.

Each probe isolates one layout question (byte signedness, inline values, byte order,
time values, row counts, sequence representations, interleaved blocks, .tdx strings).
The probes are ours; what NI's reader makes of them was recorded with
``capture_ni.py`` into ``tests/fixtures/ni_probes/ni_view.json``.

    python scripts/make_ni_probes.py
"""

from __future__ import annotations

import struct
from pathlib import Path

from ni_probe_xml import write_probe

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ni_probes"


def ext(block: str) -> str:
    return f'<values external="{block}"/>'


def blk(index: int, offset: int, length: int, value_type: str, kind: str = "block") -> str:
    return (
        f'<{kind} byteOffset="{offset}" id="inc{index}" length="{length}" '
        f'valueType="{value_type}"/>'
    )


def column(representation: str, parameters: str | None = None) -> str:
    text = f"<sequence_representation>{representation}</sequence_representation>"
    if parameters is not None:
        text += f"<generation_parameters>{parameters}</generation_parameters>"
    return text


def typed_blocks(stem: str, combos: list[tuple[str, str, bytes]], rows: int) -> None:
    chans, blocks, tdx = [], "", b""
    for i, (seq, value_type, raw) in enumerate(combos):
        blocks += blk(i, len(tdx), rows, value_type)
        chans.append({"name": f"{seq}:{value_type}", "seq": seq, "values": ext(f"inc{i}")})
        chans[-1]["rows"] = rows
        tdx += raw
    write_probe(OUT, stem, chans, blocks, tdx)


def basics() -> None:
    b4 = bytes([0x00, 0x7F, 0x80, 0xFF])
    byte_combos = [("byte_sequence", "eInt8Usi"), ("byte_sequence", "eUInt8Usi")]
    byte_combos += [("byte_sequence", "eSInt8Usi"), ("short_sequence", "eInt8Usi")]
    byte_combos += [("short_sequence", "eSInt8Usi"), ("long_sequence", "eUInt8Usi")]
    byte_combos += [("double_sequence", "eInt8Usi")]
    typed_blocks("p01_bytes", [(s, v, b4) for s, v in byte_combos], 4)
    v16 = struct.pack("<4H", 0, 1, 32768, 65535)
    v32 = struct.pack("<4I", 0, 1, 2**31, 2**32 - 1)
    v64 = struct.pack("<4Q", 0, 1, 2**63, 2**64 - 1)
    f32 = struct.pack("<4f", 0.5, -1.25, float("inf"), 3.0)
    typed_blocks(
        "p02_ints",
        [
            ("short_sequence", "eInt16Usi", v16),
            ("short_sequence", "eUInt16Usi", v16),
            ("long_sequence", "eUInt16Usi", v16),
            ("double_sequence", "eUInt16Usi", v16),
            ("long_sequence", "eInt32Usi", v32),
            ("long_sequence", "eUInt32Usi", v32),
            ("double_sequence", "eUInt32Usi", v32),
            ("double_sequence", "eInt64Usi", v64),
            ("double_sequence", "eUInt64Usi", v64),
            ("float_sequence", "eFloat32Usi", f32),
            ("double_sequence", "eFloat32Usi", f32),
            ("float_sequence", "eFloat64Usi", struct.pack("<4d", 0.5, -1.25, 1e300, 0.1)),
        ],
        4,
    )
    be = struct.pack(">h i d f", -2, 70000, 0.25, 1.5)
    seqs = [("i16", "short_sequence"), ("i32", "long_sequence")]
    seqs += [("f64", "double_sequence"), ("f32", "float_sequence")]
    chans = [
        {"name": n, "seq": s, "values": ext(f"inc{i}"), "rows": 1} for i, (n, s) in enumerate(seqs)
    ]
    blocks = blk(0, 0, 1, "eInt16Usi") + blk(1, 2, 1, "eInt32Usi")
    blocks += blk(2, 6, 1, "eFloat64Usi") + blk(3, 14, 1, "eFloat32Usi")
    write_probe(OUT, "p04_bigendian", chans, blocks, be, "bigEndian")


def inline() -> None:
    cases = [
        ("byte_sequence", "0 127 255"),
        ("short_sequence", "-5 0 32767"),
        ("long_sequence", "-7 2147483647 0"),
        ("double_sequence", "-9223372036854775808 1 9007199254740993"),
        ("float_sequence", "0.5 -1.25 1e10"),
        ("double_sequence", "0.1 -2.5e-3 INF"),
        ("double_sequence", "  1\n2\t3  "),
        ("string_sequence", "<s>a</s><s></s><s> b </s>"),
        ("time_sequence", "2026-10-14T12:00:00"),
        ("double_sequence", "1 2"),
        ("double_sequence", "1 2 3 4"),
        ("double_sequence", "1,5 2 3"),
        ("string_sequence", "<s>a</s><s>b</s>"),
        ("long_sequence", "1.5 2 3"),
        ("double_sequence", "NaN -INF 1e400"),
    ]
    for i, (seq, text) in enumerate(cases):
        chan = {"name": f"{seq}#{i}", "seq": seq, "values": f"<values>{text}</values>", "rows": 3}
        write_probe(OUT, f"p03_inline_{i:02d}", [chan], "", b"")
    chan = {"name": "t", "seq": "time_sequence", "rows": 2}
    chan["values"] = "<values>2026-10-14T12:00:00.123456789 1999-12-31T23:59:59</values>"
    write_probe(OUT, "p12_inline_time", [chan], "", b"")


if __name__ == "__main__":
    from make_ni_probes_more import layouts, representations, times

    OUT.mkdir(parents=True, exist_ok=True)
    for build in (basics, inline, times, representations, layouts):
        build()
    print(f"probes written to {OUT}")

"""Contracts from the ground-truth review: NI's time rounding, inline bytes and floats."""

from __future__ import annotations

import struct
from datetime import datetime, timedelta
from pathlib import Path

from tdm_builder import Dataset, block, inline, stored

from tdmread import read_tdm

PROP = '<instance_attributes><{0}_attribute name="p">{1}</{0}_attribute></instance_attributes>'


def test_tdx_times_round_to_the_nanosecond_like_nis_reader(tmp_path: Path) -> None:
    # LabVIEW stores 1.5 ms steps as fractions just below the exact value; NI reads them
    # as the exact microsecond (checked against NI's DataStore on 5000 such values).
    start = 3_850_070_400  # 2026-01-01 00:00:00 from 1904
    steps = [k * 1500 for k in range(5000)]  # microseconds
    raw = b""
    for micro in steps:
        seconds, rest = divmod(micro, 1_000_000)
        raw += struct.pack("<Qq", (rest << 64) // 1_000_000 - (1 if rest else 0), start + seconds)
    dataset = Dataset([stored(0, "time_sequence", "t")], block("t", 0, 5000, "eTimeUsi"), raw)
    data = read_tdm(dataset.write(tmp_path)).group("G").channel("ch0").times()
    first = datetime(2026, 1, 1)
    assert data == tuple(first + timedelta(microseconds=m) for m in steps)


def test_nis_example_fraction_reads_as_the_next_microsecond(tmp_path: Path) -> None:
    raw = struct.pack("<Qq", 0x0126E978D4FDF3B0, 3850074000)
    dataset = Dataset([stored(0, "time_sequence", "t")], block("t", 0, 1, "eTimeUsi"), raw)
    assert read_tdm(dataset.write(tmp_path)).group("G").channel("ch0").data == (
        datetime(2026, 1, 1, 1, 0, 0, 4500),
    )


def test_header_times_round_on_the_tenth_digit(tmp_path: Path) -> None:
    text = "2026-10-14T12:11:12.345677999999999985281 2026-10-14T12:11:12.9999999995"
    data = read_tdm(Dataset([inline(0, "time_sequence", text)]).write(tmp_path)).groups[0]
    assert data.channels[0].data == (
        datetime(2026, 10, 14, 12, 11, 12, 345678),
        datetime(2026, 10, 14, 12, 11, 13),
    )


def test_inline_bytes_are_unsigned_and_inline_floats_are_32_bit(tmp_path: Path) -> None:
    channels = [inline(0, "byte_sequence", "-128 -5 255"), inline(1, "float_sequence", "0.1 1e300")]
    channels[0].extra = PROP.format("byte", "-5")
    channels[1].extra = PROP.format("float", "0.1")
    group = read_tdm(Dataset(channels).write(tmp_path)).groups[0]
    assert group.channels[0].data == (128, 251, 255)
    assert group.channels[1].data == (0.10000000149011612, float("inf"))
    assert group.channels[0].properties["p"] == 251
    assert group.channels[1].properties["p"] == 0.10000000149011612


def test_a_string_property_keeps_its_first_part(tmp_path: Path) -> None:
    channel = inline(0, "double_sequence", "1")
    channel.extra = (
        '<instance_attributes><string_attribute name="p"><s>first</s><s>second</s>'
        "</string_attribute></instance_attributes>"
    )
    assert read_tdm(Dataset([channel]).write(tmp_path)).groups[0].channels[0].properties == {
        "p": "first"
    }

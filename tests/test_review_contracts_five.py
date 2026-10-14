"""Contracts from the third adversarial round: allowance accounts, sparse blocks, sharing."""

from __future__ import annotations

import struct
import time
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, stored

from tdmread import read_tdm
from tdmread._cli import main

LINEAR = "<sequence_representation>implicit_linear</sequence_representation>"
NS = 'xmlns:usi="http://www.ni.com/Schemas/USI/1_0"'


def test_raw_integers_their_scaled_copy_and_a_time_axis_fit_the_allowance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Shrunk allowance: 100 plus one per .tdx byte. 300 int8 values, scaled, plus a time
    # axis of 300 rows would exceed one shared account but fit the three accounts.
    monkeypatch.setattr("tdmread._reader.GENERATED_ALLOWANCE", 100)
    raw_column = (
        '<values>#xpointer(id("s0"))</values>'
        "<sequence_representation>raw_linear</sequence_representation>"
        "<generation_parameters>0 0.5</generation_parameters>"
    )
    data = stored(0, "byte_sequence", "b")
    data.column = raw_column
    axis = Chan("t", column=LINEAR + "<generation_parameters>0 0.01</generation_parameters>")
    axis.rows = 300
    header = Dataset([data, axis], block("b", 0, 300, "eInt8Usi"), bytes(range(256)) + bytes(44))
    group = read_tdm(header.write(tmp_path)).group("G")
    assert len(group.channel("ch0")) == 300 and group.channel("ch0").data[255] == 127.5
    assert len(group.channel("t")) == 300


def test_sparse_interleaved_blocks_read_only_their_items(tmp_path: Path) -> None:
    size = 8 << 20
    blocks = "".join(
        f'<block_bm id="b{i}" byteOffset="{i % 8}" length="2" blockOffset="0"'
        f' blockSize="{size - 16}" valueType="eFloat64Usi"/>'
        for i in range(400)
    )
    channels = [stored(i, "double_sequence", f"b{i}") for i in range(400)]
    header = Dataset(channels, blocks, bytes(size)).write(tmp_path)
    started = time.perf_counter()
    group = read_tdm(header).group("G")
    assert time.perf_counter() - started < 3.0
    assert all(c.data == (0.0, 0.0) for c in group)


def test_a_shared_padded_generated_column_costs_linear_time(tmp_path: Path) -> None:
    n = 3000
    junk = "<j/>" * n
    refs = " ".join(f'id("c{i}")' for i in range(n))
    channels = "".join(
        f'<tdm_channel id="c{i}"><name>c{i}</name>'
        '<local_columns>#xpointer(id("l"))</local_columns></tdm_channel>'
        for i in range(n)
    )
    header = tmp_path / "padded.tdm"
    header.write_text(
        f'<usi:tdm {NS}><usi:data><tdm_root id="r"><channelgroups>#xpointer(id("g"))'
        f'</channelgroups></tdm_root><tdm_channelgroup id="g"><name>G</name>'
        f"<channels>#xpointer({refs})</channels></tdm_channelgroup>{channels}"
        f'<submatrix id="m">{junk}<number_of_rows>0</number_of_rows></submatrix>'
        f'<localcolumn id="l">{junk}<submatrix>#xpointer(id("m"))</submatrix>'
        f"{LINEAR}<generation_parameters>0 1</generation_parameters></localcolumn>"
        "</usi:data></usi:tdm>",
        encoding="utf-8",
    )
    started = time.perf_counter()
    assert len(read_tdm(header).group("G")) == n
    assert time.perf_counter() - started < 2.0


@pytest.mark.parametrize("code", [0x85, 0x9B, 0x2028, 0x202E])
def test_listings_escape_every_unprintable_character(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], code: int
) -> None:
    channel = Chan(f"a{chr(code)}b", column='<values>#xpointer(id("s"))</values>')
    channel.sequence = '<double_sequence id="s"><values>1</values></double_sequence>'
    assert main(["channels", str(Dataset([channel]).write(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert chr(code) not in out and repr(chr(code))[1:-1] in out


def test_interleaved_values_in_close_records_still_read(tmp_path: Path) -> None:
    raw = b"".join(struct.pack("<di", a, b) for a, b in [(1.5, 10), (2.5, 20), (3.5, 30)])
    blocks = (
        '<block_bm id="a" byteOffset="0" blockSize="12" length="3" valueType="eFloat64Usi"/>'
        '<block_bm id="b" byteOffset="8" blockSize="12" length="3" valueType="eInt32Usi"/>'
    )
    channels = [stored(0, "double_sequence", "a"), stored(1, "long_sequence", "b")]
    group = read_tdm(Dataset(channels, blocks, raw).write(tmp_path)).group("G")
    assert [c.data for c in group] == [(1.5, 2.5, 3.5), (10, 20, 30)]

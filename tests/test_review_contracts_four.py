"""Contracts from the second adversarial round: overlapping blocks, repeated groups."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, stored

from tdmread import TdmError, read_tdm
from tdmread._cli import main

NS = 'xmlns:usi="http://www.ni.com/Schemas/USI/1_0"'


def test_overlapping_blocks_count_against_the_allowance(tmp_path: Path) -> None:
    size = 1 << 20
    channels = [stored(i, "byte_sequence", f"b{i}") for i in range(64)]
    blocks = "".join(block(f"b{i}", 0, size, "eInt8Usi") for i in range(64))
    header = Dataset(channels, blocks, bytes(size)).write(tmp_path)
    started = time.perf_counter()
    with pytest.raises(TdmError, match="limit"):
        read_tdm(header)
    assert time.perf_counter() - started < 5.0


def test_a_group_listed_many_times_is_read_once(tmp_path: Path) -> None:
    n = 2000
    groups = " ".join(['id("g")'] * n)
    channels = " ".join(f'id("c{i}")' for i in range(n))
    body = "".join(f'<tdm_channel id="c{i}"><name>c{i}</name></tdm_channel>' for i in range(n))
    header = tmp_path / "groups.tdm"
    header.write_text(
        f'<usi:tdm {NS}><usi:data><tdm_root id="r"><channelgroups>#xpointer({groups})'
        f'</channelgroups></tdm_root><tdm_channelgroup id="g"><name>G</name>'
        f"<channels>#xpointer({channels})</channels></tdm_channelgroup>{body}"
        "</usi:data></usi:tdm>",
        encoding="utf-8",
    )
    started = time.perf_counter()
    dataset = read_tdm(header)
    assert time.perf_counter() - started < 2.0
    assert len(dataset) == n and dataset.groups[0] is dataset.groups[-1]


def test_a_shared_generated_column_takes_each_channels_length(tmp_path: Path) -> None:
    column = (
        "<sequence_representation>implicit_linear</sequence_representation>"
        "<generation_parameters>0 1</generation_parameters>"
    )
    length = '<instance_attributes><long_attribute name="NI_ChannelLength">{}'
    length += "</long_attribute></instance_attributes>"
    first = Chan("a", column=column, extra=length.format(3))
    second = Chan("b", extra=length.format(5))
    header = Dataset([first, second]).write(tmp_path)
    text = header.read_text(encoding="utf-8")
    text = text.replace('<local_columns>#xpointer(id("l1"))', '<local_columns>#xpointer(id("l0"))')
    header.write_text(text, encoding="utf-8")
    group = read_tdm(header).group("G")
    assert [len(c) for c in group] == [3, 5]


def test_channel_listings_escape_control_characters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    channel = Chan("x&#9;y&#10;z", column='<values>#xpointer(id("s"))</values>')
    channel.sequence = '<double_sequence id="s"><values>1</values></double_sequence>'
    header = Dataset([channel]).write(tmp_path)
    assert main(["channels", str(header)]) == 0
    assert capsys.readouterr().out.splitlines() == ["G\tx\\ty\\nz\texplicit\t1"]

"""Contracts from the adversarial review: shared references, encodings, names, streams."""

from __future__ import annotations

import struct
import sys
import time
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, stored

from tdmread import TdmError, read_tdm
from tdmread._cli import main

NS = 'xmlns:usi="http://www.ni.com/Schemas/USI/1_0"'


def _shared(n: int) -> str:
    refs = " ".join(['id("c")'] * n)
    return (
        f'<usi:tdm {NS}><usi:data><tdm_root id="r"><channelgroups>#xpointer(id("g"))'
        f'</channelgroups></tdm_root><tdm_channelgroup id="g"><channels>#xpointer({refs})'
        '</channels></tdm_channelgroup><tdm_channel id="c"><local_columns>#xpointer(id("l"))'
        '</local_columns></tdm_channel><localcolumn id="l"><values>#xpointer(id("s"))'
        f'</values></localcolumn><double_sequence id="s"><values>{" ".join(["1"] * n)}'
        "</values></double_sequence></usi:data></usi:tdm>"
    )


def test_a_channel_listed_many_times_is_decoded_once(tmp_path: Path) -> None:
    header = tmp_path / "shared.tdm"
    header.write_text(_shared(3000), encoding="utf-8")
    started = time.perf_counter()
    group = read_tdm(header).groups[0]
    assert time.perf_counter() - started < 2.0
    assert len(group) == 3000 and group.channels[0] is group.channels[-1]


def test_many_channels_sharing_one_block_read_it_once(tmp_path: Path) -> None:
    count = 200_000
    channels = [stored(i, "double_sequence", "b") for i in range(40)]
    raw = struct.pack(f"<{count}d", *range(count))
    header = Dataset(channels, block("b", 0, count, "eFloat64Usi"), raw).write(tmp_path)
    started = time.perf_counter()
    group = read_tdm(header).group("G")
    assert time.perf_counter() - started < 3.0
    assert all(c.data is group.channels[0].data for c in group)


def test_scaled_channels_count_against_the_allowance(tmp_path: Path) -> None:
    raw = struct.pack("<4h", 1, 2, 3, 4)
    column = (
        '<values>#xpointer(id("s"))</values>'
        "<sequence_representation>raw_linear</sequence_representation>"
        "<generation_parameters>{} 1</generation_parameters>"
    )
    sequence = '<short_sequence id="s"><values external="b"/></short_sequence>'
    channels = [Chan(f"x{i}", column.format(i)) for i in range(3)]
    channels[0].sequence = sequence
    header = Dataset(channels, block("b", 0, 4, "eInt16Usi"), raw).write(tmp_path)
    group = read_tdm(header).group("G")
    assert [c.data for c in group] == [
        (1.0, 2.0, 3.0, 4.0),
        (2.0, 3.0, 4.0, 5.0),
        (3.0, 4.0, 5.0, 6.0),
    ]


@pytest.mark.parametrize(
    "declaration", ["utf-32", "utf-16", "shift_jis", "gbk", "utf-7", "idna", "punycode"]
)
def test_unreadable_encodings_raise_tdm_error(tmp_path: Path, declaration: str) -> None:
    header = tmp_path / "x.tdm"
    header.write_bytes(f'<?xml version="1.0" encoding="{declaration}"?><tdm/>'.encode("ascii"))
    with pytest.raises(TdmError, match="encoding"):
        read_tdm(header)


@pytest.mark.parametrize(
    "url", [".", " ", "sub/.", "a&lt;b.tdx", "a&quot;b.tdx", "a|b", "x&#9;y.tdx", "a?b", ".. "]
)
def test_names_no_file_can_have_are_refused(tmp_path: Path, url: str) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    dataset.url = "data.tdx"
    header = dataset.write(tmp_path)
    text = header.read_text(encoding="utf-8").replace('url="data.tdx"', f'url="{url}"')
    header.write_text(text, encoding="utf-8")
    with pytest.raises(TdmError, match=r"the .tdx location"):
        read_tdm(header)


def test_a_huge_url_attribute_is_a_short_tdm_error(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    dataset.url = "data.tdx"
    header = dataset.write(tmp_path)
    huge = "u" * 40_000 + ".tdx"
    header.write_text(header.read_text(encoding="utf-8").replace("data.tdx", huge), "utf-8")
    with pytest.raises(TdmError) as caught:
        read_tdm(header)
    assert len(str(caught.value)) < 120


def test_closed_standard_streams_do_not_crash_the_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = str(Path(__file__).parent / "fixtures" / "synthetic" / "Synthetic.tdm")
    monkeypatch.setattr(sys, "stdout", None)
    assert main(["channels", good]) == 0
    assert main(["dump", good, "-g", "Amplitudes", "-c", "A = 1"]) == 0
    monkeypatch.setattr(sys, "stderr", None)
    assert main(["info", str(tmp_path / "missing.tdm")]) == 1

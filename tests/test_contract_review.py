"""Contracts from the independent review: promises that no other test pinned."""

from __future__ import annotations

from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, stored

from tdmread import Group, TdmError, read_tdm


def test_a_block_without_byte_offset_starts_at_zero(tmp_path: Path) -> None:
    # R14: byteOffset made mandatory.
    plain = '<block id="b" length="2" valueType="eInt16Usi"/>'
    tdx = b"\x07\x00\x08\x00"
    header = Dataset([stored(0, "short_sequence", "b")], blocks=plain, tdx=tdx).write(tmp_path)
    assert read_tdm(header).group("G").channel("ch0").data == (7, 8)


def test_a_sequence_without_values_is_an_empty_channel(tmp_path: Path) -> None:
    # R15: a value sequence with no <values> child raises instead of reading as empty.
    chan = Chan(
        "e",
        column='<values>#xpointer(id("s0"))</values>',
        sequence='<double_sequence id="s0"></double_sequence>',
    )
    header = Dataset([chan]).write(tmp_path)
    channel = read_tdm(header).group("G").channel("e")
    assert channel.data == () and channel.value_type == ""


def test_a_block_one_byte_past_the_end_names_the_size(tmp_path: Path) -> None:
    # R16: the past-end check made one byte lenient (falls through to a different error).
    blocks = block("b", 0, 2, "eInt16Usi")
    header = Dataset([stored(0, "short_sequence", "b")], blocks=blocks, tdx=b"\x01\x00\x02").write(
        tmp_path
    )
    with pytest.raises(TdmError, match=r"reaches byte 4 but the \.tdx holds 3 bytes"):
        read_tdm(header)


def test_quoted_text_is_exactly_forty_characters() -> None:
    # R22: the quote cut three characters over its limit.
    with pytest.raises(TdmError) as caught:
        Group("G", ()).channel("x" * 100)
    message = str(caught.value)
    quoted = message.split("named ", 1)[1].split(" in group", 1)[0]
    assert quoted == "'" + "x" * 36 + "..."
    assert len(quoted) == 40

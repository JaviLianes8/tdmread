"""Contracts from the third independent review: promises no other test pinned."""

from __future__ import annotations

from pathlib import Path

import pytest
from tdm_builder import Dataset, inline, stored

from tdmread import TdmError, _tdx, read_tdm
from tdmread._cli import main


def _patch(header: Path, old: str, new: str) -> Path:
    text = header.read_text(encoding="utf-8")
    assert text.count(old) == 1
    header.write_text(text.replace(old, new), encoding="utf-8")
    return header


def test_floats_may_start_or_end_with_the_decimal_point(tmp_path: Path) -> None:
    # GUIDE accepts floats in decimal notation; guards against ".5" being refused.
    header = Dataset([inline(0, "double_sequence", ".5 -.25 5.")]).write(tmp_path)
    assert read_tdm(header).group("G").channel("ch0").data == (0.5, -0.25, 5.0)


def test_header_texts_are_read_without_surrounding_whitespace(tmp_path: Path) -> None:
    # Guards against child text kept with its padding.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    _patch(header, "<name>ch0</name>", "<name>\n  ch0  </name><unit_string> V </unit_string>")
    channel = read_tdm(header).group("G").channel("ch0")
    assert (channel.name, channel.unit) == ("ch0", "V")


def test_block_attributes_may_be_padded_with_whitespace(tmp_path: Path) -> None:
    # Guards against integer attributes parsed without stripping.
    blocks = '<block id="b" byteOffset=" 2 " length=" 1 " valueType="eInt16Usi"/>'
    header = Dataset(
        [stored(0, "short_sequence", "b")], blocks=blocks, tdx=b"\x00\x00\x07\x00"
    ).write(tmp_path)
    assert read_tdm(header).group("G").channel("ch0").data == (7,)


def test_a_block_without_length_is_empty(tmp_path: Path) -> None:
    # Guards against the length attribute made mandatory.
    blocks = '<block id="b" byteOffset="0" valueType="eInt16Usi"/>'
    header = Dataset([stored(0, "short_sequence", "b")], blocks=blocks, tdx=b"").write(tmp_path)
    channel = read_tdm(header).group("G").channel("ch0")
    assert channel.data == () and channel.value_type == "eInt16Usi"


def test_a_tdx_that_shrinks_while_open_is_a_tdm_error(tmp_path: Path) -> None:
    # Guards against a short read returned as if it were the requested range.
    path = tmp_path / "data.tdx"
    path.write_bytes(bytes(1 << 20))  # far larger than any read buffer
    with _tdx.TdxSource(path, "data.tdx") as source:
        assert source.read(0, 4) == bytes(4)
        with open(path, "r+b") as handle:
            handle.truncate(2)
        with pytest.raises(TdmError, match="changed while it was being read"):
            source.read(500_000, 500_008)


def test_group_description_and_dataset_datetime_are_read(tmp_path: Path) -> None:
    # Guards against the group description or the root datetime dropped.
    header = Dataset(
        [inline(0, "double_sequence", "1")],
        root_extra="<datetime>2026-10-15T08:00:00</datetime>",
        group_extra="<description>first run</description>",
    ).write(tmp_path)
    dataset = read_tdm(header)
    assert dataset.metadata.datetime == "2026-10-15T08:00:00"
    assert dataset.group("G").description == "first run"


def test_channels_escapes_unprintable_characters_in_units(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against the unit printed raw, which would split the line into extra columns.
    header = Dataset([inline(0, "double_sequence", "1 2")]).write(tmp_path)
    _patch(header, "<name>ch0</name>", "<name>ch0</name><unit_string>m\ts</unit_string>")
    assert main(["channels", str(header)]) == 0
    line = capsys.readouterr().out.splitlines()[0]
    assert line.split("\t") == ["G", "ch0 [m\\ts]", "explicit", "2"]

"""Contracts from the fourth independent review: promises no other test pinned."""

from __future__ import annotations

import gc
import math
import warnings
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import Channel, Group, TdmError, TdmFile, read_tdm
from tdmread._cli import main


def _patch(header: Path, old: str, new: str) -> Path:
    text = header.read_text(encoding="utf-8")
    assert text.count(old) == 1
    header.write_text(text.replace(old, new), encoding="utf-8")
    return header


def test_a_utf16_header_opening_with_a_dtd_is_refused(tmp_path: Path) -> None:
    # Guards against the UTF-16 little-endian DTD mark left unchecked: right after the
    # byte order mark the big-endian check cannot see it.
    xml = (
        '<!DOCTYPE tdm><usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
        '<tdm_root id="r"><name>d</name></tdm_root></usi:data></usi:tdm>'
    )
    header = tmp_path / "dtd.tdm"
    header.write_bytes(b"\xff\xfe" + xml.encode("utf-16-le"))
    with pytest.raises(TdmError, match="DTD"):
        read_tdm(header)


@pytest.mark.parametrize("representation", ["implicit_constant", "implicit_linear"])
def test_a_constant_channel_repeats_its_value_exactly(tmp_path: Path, representation: str) -> None:
    # Guards against constants generated as start + i * 0.0, which turns -0.0 into 0.0.
    column = (
        f"<sequence_representation>{representation}</sequence_representation>"
        "<generation_parameters>-0.0</generation_parameters>"
    )
    header = Dataset([Chan("x", column=column, rows=3)]).write(tmp_path)
    data = read_tdm(header).group("G").channel("x").numbers()
    assert len(data) == 3 and all(math.copysign(1.0, value) == -1.0 for value in data)


def test_an_override_tdx_path_with_a_nul_is_a_tdm_error(tmp_path: Path) -> None:
    # Guards against the ValueError of an unopenable path escaping untyped.
    header = Dataset(
        [stored(0, "double_sequence", "b")], blocks=block("b", 0, 1, "eFloat64Usi")
    ).write(tmp_path)
    with pytest.raises(TdmError, match="cannot open"):
        read_tdm(header, tdx_path=str(tmp_path / "da\x00ta.tdx"))


def test_the_tdx_is_closed_when_reading_returns(tmp_path: Path) -> None:
    # Guards against the .tdx handle left open after read_tdm.
    dataset = Dataset(
        [stored(0, "double_sequence", "b")],
        blocks=block("b", 0, 1, "eFloat64Usi"),
        tdx=bytes(8),
    )
    header = dataset.write(tmp_path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert read_tdm(header).group("G").channel("ch0").data == (0.0,)
        gc.collect()
    assert not [w for w in caught if issubclass(w.category, ResourceWarning)]
    moved = tmp_path / "moved.tdx"
    (tmp_path / "data.tdx").rename(moved)  # an open file cannot be renamed on Windows
    assert moved.exists()


def test_channels_marks_a_channel_without_any_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against an empty kind column for a channel with no local column at all.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    _patch(header, '<local_columns>#xpointer(id("l0"))</local_columns>', "")
    assert main(["channels", str(header)]) == 0
    assert capsys.readouterr().out.splitlines() == ["G\tch0\t?\t0"]


def test_dataset_channels_walk_groups_in_order() -> None:
    # Guards against channels() visiting the groups in any other order.
    first = Group("A", (Channel("a1", "", "", "", ()), Channel("a2", "", "", "", ())))
    second = Group("B", (Channel("b1", "", "", "", ()),))
    pairs = [(g.name, c.name) for g, c in TdmFile((first, second)).channels()]
    assert pairs == [("A", "a1"), ("A", "a2"), ("B", "b1")]


def test_block_attributes_and_row_counts_may_carry_a_plus_sign(tmp_path: Path) -> None:
    # Guards against a leading '+' refused in integer attributes and row counts.
    blocks = '<block id="b" byteOffset="+2" length="+1" valueType="eInt16Usi"/>'
    header = Dataset(
        [stored(0, "short_sequence", "b")], blocks=blocks, tdx=b"\x00\x00\x07\x00"
    ).write(tmp_path)
    assert read_tdm(header).group("G").channel("ch0").data == (7,)
    column = (
        "<sequence_representation>implicit_constant</sequence_representation>"
        "<generation_parameters>2</generation_parameters>"
    )
    header = Dataset([Chan("x", column=column)]).write(tmp_path, "rows")
    _patch(
        header,
        '<submatrix id="m0"></submatrix>',
        '<submatrix id="m0"><number_of_rows>+2</number_of_rows></submatrix>',
    )
    assert read_tdm(header).group("G").channel("x").data == (2.0, 2.0)

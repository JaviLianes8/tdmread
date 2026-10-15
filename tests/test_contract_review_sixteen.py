"""Contracts from the sixteenth independent review: CLI paths, required fields, exact limits."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
from tdm_builder import Dataset, inline, stored

from tdmread import Channel, TdmError, TdmFile, UnsupportedTdmError, read_tdm
from tdmread._cli import main


def _split_dataset(tmp_path: Path) -> tuple[Path, Path]:
    # The header names data.tdx, which does not exist; the values sit in other.tdx.
    data = Dataset(
        [stored(0, "long_sequence", "b")],
        blocks='<block id="b" byteOffset="0" length="1" valueType="eInt32Usi"/>',
    )
    header = data.write(tmp_path)
    other = tmp_path / "other.tdx"
    other.write_bytes((9).to_bytes(4, "little"))
    return header, other


def test_info_reads_the_tdx_given_on_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header, other = _split_dataset(tmp_path)
    assert main(["info", str(header), "--tdx", str(other)]) == 0
    captured = capsys.readouterr()
    assert "  G (1 channels)" in captured.out.splitlines()
    assert captured.err == ""


def test_channels_reads_the_tdx_given_on_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header, other = _split_dataset(tmp_path)
    assert main(["channels", str(header), "--tdx", str(other)]) == 0
    captured = capsys.readouterr()
    assert captured.out == "G\tch0\teInt32Usi\t1\n"
    assert captured.err == ""


def test_dump_still_reads_the_given_tdx_in_a_split_dataset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header, other = _split_dataset(tmp_path)
    args = ["dump", str(header), "--tdx", str(other), "-g", "G", "-c", "ch0", "-f", "json"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["data"] == [9]


def test_an_empty_header_path_is_a_read_error_with_a_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["info", ""]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("tdmread: error: TDM header not found")


def test_channel_data_and_dataset_groups_are_required() -> None:
    assert inspect.signature(Channel).parameters["data"].default is inspect.Parameter.empty
    assert inspect.signature(TdmFile).parameters["groups"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        Channel("a", "V", "", "")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        TdmFile()  # type: ignore[call-arg]


def test_a_four_hundred_digit_integer_is_read_and_longer_text_is_refused(tmp_path: Path) -> None:
    longest = "9" * 400
    header = Dataset([inline(0, "longlong_sequence", longest)]).write(tmp_path)
    assert read_tdm(header).group("G").channel("ch0").data == (int(longest),)
    header = Dataset([inline(0, "longlong_sequence", "9" * 401)]).write(tmp_path)
    with pytest.raises(TdmError, match="invalid integer value"):
        read_tdm(header)


def test_a_block_bm_one_byte_narrower_than_its_value_is_refused(tmp_path: Path) -> None:
    blocks = (
        '<block_bm id="b" byteOffset="0" blockOffset="0" blockSize="3" length="2" '
        'valueType="eInt32Usi"/>'
    )
    header = Dataset([stored(0, "long_sequence", "b")], blocks=blocks, tdx=bytes(16)).write(
        tmp_path
    )
    with pytest.raises(UnsupportedTdmError, match="blockSize 3 cannot hold a 4-byte value"):
        read_tdm(header)


def test_group_lookup_is_case_sensitive(tmp_path: Path) -> None:
    dataset = read_tdm(Dataset([inline(0, "double_sequence", "1")]).write(tmp_path))
    assert dataset.group("G").name == "G"
    with pytest.raises(TdmError, match="no group named 'g'"):
        dataset.group("g")

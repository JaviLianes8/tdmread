"""Contracts from the fifth independent review: promises no other test pinned."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, inline, stored

from tdmread import Channel, TdmError, UnsupportedTdmError, read_tdm
from tdmread._cli import main


def test_times_refuses_numbers() -> None:
    # Guards against times() handing back floats as if they were datetimes.
    with pytest.raises(TdmError, match="not times"):
        Channel("t", "", "", "", (1.5, 2.5)).times()


def test_info_labels_the_dataset_time_and_description(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against a wrong label for the datetime line and the description read from
    # another element.
    extra = (
        "<title>the title</title><description>the description</description>"
        "<datetime>2026-10-15T08:00:00</datetime>"
    )
    header = Dataset([inline(0, "double_sequence", "1")], root_extra=extra).write(tmp_path)
    meta = read_tdm(header).metadata
    assert (meta.title, meta.description) == ("the title", "the description")
    assert main(["info", str(header)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "datetime: 2026-10-15T08:00:00" in lines
    assert "description: the description" in lines


def test_a_closed_standard_output_does_not_break_the_exit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against the ValueError a closed stream raises on flush escaping main().
    closed = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    closed.close()
    monkeypatch.setattr(sys, "stdout", closed)
    assert main(["info", str(tmp_path / "missing.tdm")]) == 1
    assert "not found" in capsys.readouterr().err


def test_dump_matches_the_channel_name_exactly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against the CLI trimming or otherwise loosening the requested name.
    header = Dataset([inline(0, "double_sequence", "1 2")]).write(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", " ch0 "]) == 1
    assert "no channel named" in capsys.readouterr().err


def test_dump_json_carries_the_unit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Guards against the JSON unit field filled from another attribute.
    chan = inline(0, "double_sequence", "1")
    chan.extra = "<unit_string>V</unit_string><description>volts in</description>"
    header = Dataset([chan]).write(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unit"] == "V"


def test_a_longlong_property_stays_an_exact_integer(tmp_path: Path) -> None:
    # Guards against 64-bit integer properties read as floats (which lose digits).
    big = 2**60 + 1
    attrs = (
        "<instance_attributes>"
        f'<longlong_attribute name="n">{big}</longlong_attribute>'
        "</instance_attributes>"
    )
    header = Dataset([Chan("x", extra=attrs)]).write(tmp_path)
    value = read_tdm(header).group("G").channel("x").properties["n"]
    assert type(value) is int and value == big


def test_a_block_bm_without_block_size_is_malformed_not_unsupported(tmp_path: Path) -> None:
    # Guards against a missing required attribute read as 0 (then reported as unsupported).
    blocks = '<block_bm id="b" byteOffset="0" length="1" valueType="eFloat64Usi"/>'
    header = Dataset([stored(0, "double_sequence", "b")], blocks=blocks, tdx=bytes(8)).write(
        tmp_path
    )
    with pytest.raises(TdmError, match="missing its 'blockSize'") as caught:
        read_tdm(header)
    assert not isinstance(caught.value, UnsupportedTdmError)

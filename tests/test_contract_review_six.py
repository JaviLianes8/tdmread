"""Contracts from the sixth independent review: promises no other test pinned."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, UnsupportedTdmError, read_tdm
from tdmread._cli import main
from tdmread._props import Properties


def test_dump_reads_the_tdx_given_on_the_command_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against the CLI ignoring --tdx and reading the file the header names.
    data = Dataset(
        [stored(0, "long_sequence", "b")],
        blocks=block("b", 0, 1, "eInt32Usi"),
        tdx=(7).to_bytes(4, "little"),
    )
    header = data.write(tmp_path)
    other = tmp_path / "other.tdx"
    other.write_bytes((9).to_bytes(4, "little"))
    args = ["dump", str(header), "--tdx", str(other), "-g", "G", "-c", "ch0", "-f", "json"]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["data"] == [9]


def test_info_and_channels_escape_group_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against a control character in a group name reaching the output raw.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    text = header.read_text(encoding="utf-8").replace("<name>G</name>", "<name>G&#9;H</name>")
    header.write_text(text, encoding="utf-8")
    assert main(["info", str(header)]) == 0
    assert "  G\\tH (1 channels)" in capsys.readouterr().out.splitlines()
    assert main(["channels", str(header)]) == 0
    assert capsys.readouterr().out.startswith("G\\tH\tch0\t")


def test_dump_json_carries_the_representation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against the JSON representation field filled from another attribute.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert (payload["representation"], payload["value_type"]) == ("explicit", "")


class _GoneReader(io.StringIO):
    def write(self, text: str) -> int:
        exc = OSError("the pipe is being closed")
        exc.winerror = 232  # type: ignore[attr-defined,unused-ignore]
        raise exc


def test_a_closed_windows_pipe_is_a_quiet_broken_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against Windows error 232 (the reader closed the pipe) shown as an error.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    monkeypatch.setattr(sys, "stdout", _GoneReader())
    assert main(["info", str(header)]) == 1
    assert capsys.readouterr().err == ""


def test_a_block_without_value_type_is_unsupported(tmp_path: Path) -> None:
    # Guards against a missing valueType read as some default type.
    blocks = '<block id="b" byteOffset="0" length="1"/>'
    data = Dataset([stored(0, "double_sequence", "b")], blocks=blocks, tdx=bytes(8))
    with pytest.raises(UnsupportedTdmError, match="unsupported value type"):
        read_tdm(data.write(tmp_path))


def test_properties_copy_the_mapping_they_are_given() -> None:
    # Guards against Properties sharing (and so changing with) the caller's dict.
    source: dict[str, str | int | float] = {"a": 1}
    props = Properties(source)
    source["a"] = 2
    source["b"] = 3
    assert dict(props) == {"a": 1}


def test_unparsed_and_unknown_properties_keep_their_text(tmp_path: Path) -> None:
    # Guards against the raw text of a non-number double or an unknown kind being altered.
    attrs = (
        "<instance_attributes>"
        '<double_attribute name="d">Hello World</double_attribute>'
        '<custom_attribute name="u">MiXeD Case</custom_attribute>'
        "</instance_attributes>"
    )
    header = Dataset([Chan("x", extra=attrs)]).write(tmp_path)
    props = read_tdm(header).group("G").channel("x").properties
    assert (props["d"], props["u"]) == ("Hello World", "MiXeD Case")


def test_an_empty_tdx_url_is_reported_as_unnamed(tmp_path: Path) -> None:
    # Guards against an empty url treated as a file name instead of a missing one.
    data = Dataset([stored(0, "double_sequence", "b")], blocks=block("b", 0, 1, "eFloat64Usi"))
    data.url = ""
    with pytest.raises(TdmError, match="does not name its"):
        read_tdm(data.write(tmp_path))


def test_references_match_ids_exactly(tmp_path: Path) -> None:
    # Guards against id references matched without regard to case.
    xml = (
        '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
        '<tdm_root id="r"><name>n</name><channelgroups>#xpointer(id("g"))</channelgroups>'
        '</tdm_root><tdm_channelgroup id="g"><name>G</name>'
        '<channels>#xpointer(id("c"))</channels></tdm_channelgroup>'
        '<tdm_channel id="c"><name>U</name>'
        '<local_columns>#xpointer(id("L"))</local_columns></tdm_channel>'
        '<localcolumn id="L"><values>#xpointer(id("s1"))</values></localcolumn>'
        '<localcolumn id="l"><values>#xpointer(id("s2"))</values></localcolumn>'
        '<double_sequence id="s1"><values>1</values></double_sequence>'
        '<double_sequence id="s2"><values>2</values></double_sequence>'
        "</usi:data></usi:tdm>"
    )
    header = tmp_path / "case.tdm"
    header.write_text(xml, encoding="utf-8")
    assert read_tdm(header).group("G").channel("U").data == (1.0,)

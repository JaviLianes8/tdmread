"""Contracts from the eleventh independent review: help, empty block ids, read-only defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdmread import Channel, Group, TdmError, TdmFile, read_tdm
from tdmread._cli import main


def _help(capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    return capsys.readouterr().out


def test_help_shows_the_usage_line_and_the_program_description(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = _help(capsys).splitlines()
    assert lines[0] == "usage: tdmread [-h] [--version] command ..."
    assert "Read NI TDM/TDX measurement files (XML .tdm header plus binary .tdx)." in lines


def test_help_describes_each_command(capsys: pytest.CaptureFixture[str]) -> None:
    lines = [line.split() for line in _help(capsys).splitlines()]
    expected = {
        "info": "print dataset metadata and a group summary",
        "channels": "list every channel with its type and length",
        "dump": "dump one channel's values to CSV or JSON",
    }
    for command, text in expected.items():
        assert [command, *text.split()] in lines


def test_help_keeps_the_examples_one_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    out = _help(capsys)
    assert (
        "examples:\n"
        "  tdmread info measurement.tdm\n"
        "  tdmread channels measurement.tdm\n"
        '  tdmread dump measurement.tdm --group Amplitudes --channel "A = 1" --format csv\n'
        '  tdmread dump measurement.tdm -g Amplitudes -c "A = 1" -f json -o values.json\n'
        "\n"
        "exit status: 0 on success, 1 when a file cannot be read, 2 for a usage error,\n"
        "130 when interrupted.\n"
    ) in out


_HEADER = (
    '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
    '<tdm_root id="r"><channelgroups>#xpointer(id("g"))</channelgroups></tdm_root>'
    '<tdm_channelgroup id="g"><name>G</name><channels>#xpointer(id("c"))</channels>'
    '</tdm_channelgroup><tdm_channel id="c"><name>U</name>'
    '<local_columns>#xpointer(id("l"))</local_columns></tdm_channel>'
    '<localcolumn id="l"><values>#xpointer(id("s"))</values></localcolumn>'
    '<double_sequence id="s"><values external="">1.5</values></double_sequence>'
    "</usi:data></usi:tdm>"
)


def test_an_empty_external_block_id_is_a_dangling_reference(tmp_path: Path) -> None:
    header = tmp_path / "empty.tdm"
    header.write_text(_HEADER, encoding="utf-8")
    with pytest.raises(TdmError, match="block that does not exist"):
        read_tdm(header)


def test_default_properties_are_read_only() -> None:
    owners = (Channel("U", "V", "", "", ()), Group("G", ()), TdmFile(()))
    for owner in owners:
        with pytest.raises(TypeError):
            owner.properties["key"] = "value"  # type: ignore[index]
        hash(owner.properties)

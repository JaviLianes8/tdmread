"""The command-line interface, run in process."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from tdm_builder import Dataset, inline

from tdmread import __version__
from tdmread._cli import main
from tdmread._cli_output import emit

FIXTURES = Path(__file__).parent / "fixtures"
SINE = str(FIXTURES / "synthetic" / "Synthetic.tdm")
EVENT = str(FIXTURES / "labview2026" / "Example Event File.tdm")
TYPES = str(FIXTURES / "labview2026" / "gt_types_0.tdm")


def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"tdmread {__version__}"


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "usage" in out.lower() and "exit status" in out


def test_info_reports_metadata_and_groups(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", SINE]) == 0
    out = capsys.readouterr().out
    assert "author: tdmread test suite" in out
    assert "Amplitudes (5 channels)" in out
    assert "groups: 2" in out


def test_channels_lists_every_channel_with_kind_and_length(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["channels", EVENT]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "Untitled\tData\teFloat64Usi\t10000",
        "Untitled\tHistogram\teFloat64Usi\t80",
        "Untitled\tEvent Time\teInt32Usi\t8",
        "Untitled\tEvent Type\texplicit\t8",
    ]


def test_channels_shows_units(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["channels", TYPES]) == 0
    assert "Ints\ti8 [count]\teInt16Usi\t6" in capsys.readouterr().out


def test_dump_csv_writes_round_trip_numbers(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", SINE, "-g", "Amplitudes", "-c", "A = 1", "-f", "csv"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "index,A = 1" and lines[1] == "0,0.0" and len(lines) == 101


def test_dump_csv_writes_text_and_times(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", TYPES, "-g", "Text", "-c", "strings"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("index,strings\n0,plain\n1,\n2,with space \n")
    assert '7,"line\nbreak"' in out
    assert main(["dump", TYPES, "-g", "Time", "-c", "stamps"]) == 0
    assert "0,2026-10-14T17:34:39.500000" in capsys.readouterr().out


def test_dump_json_writes_every_kind_as_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "values.json"
    assert main(["dump", TYPES, "-g", "Floats", "-c", "f64", "-f", "json", "-o", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["data"][6:9] == ["inf", "-inf", "nan"]
    assert payload["datatype"] == "DT_DOUBLE" and payload["length"] == 10
    assert main(["dump", TYPES, "-g", "Time", "-c", "stamps", "-f", "json"]) == 0
    stamps = json.loads(capsys.readouterr().out)
    assert stamps["data"][1] == "1904-01-01T01:00:00"
    assert stamps["value_type"] == "eTimeUsi"


def test_unicode_survives_a_file_and_a_narrow_console(tmp_path: Path) -> None:
    header = Dataset([inline(0, "string_sequence", "<s>café 日</s>")]).write(tmp_path)
    out = tmp_path / "v.json"
    assert main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "json", "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["data"] == ["café 日"]
    raw = io.BytesIO()
    narrow = io.TextIOWrapper(raw, encoding="cp1252", newline="")
    emit(chr(0x65E5) + " ok\n", narrow)
    narrow.flush()
    assert raw.getvalue() == b"\\u65e5 ok\n"


@pytest.mark.parametrize(
    "args",
    [
        ["info", "nope.tdm"],
        ["dump", SINE, "-g", "Amplitudes", "-c", "missing"],
        ["dump", SINE, "-g", "missing", "-c", "x"],
        ["channels", str(FIXTURES / "ni_probes" / "p11_past_end.tdm")],
        ["dump", SINE, "-g", "Amplitudes", "-c", "A = 1", "-o", str(FIXTURES)],
    ],
)
def test_errors_go_to_stderr_with_exit_one(
    capsys: pytest.CaptureFixture[str], args: list[str]
) -> None:
    assert main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("tdmread: error: ") and len(captured.err) < 400


def test_a_huge_name_is_cut_in_the_message(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", SINE, "-g", "Amplitudes", "-c", "x" * 100_000]) == 1
    assert len(capsys.readouterr().err) < 400


@pytest.mark.parametrize("args", [["dump", SINE], ["frobnicate"], ["dump", SINE, "-f", "xml"]])
def test_usage_errors_exit_two(args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_a_closed_output_pipe_exits_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    class Closed(io.StringIO):
        def write(self, text: str) -> int:
            raise BrokenPipeError

    monkeypatch.setattr(sys, "stdout", Closed())
    assert main(["channels", SINE]) == 1


def test_an_interrupt_exits_130(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted(*args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("tdmread._cli.read_tdm", interrupted)
    assert main(["info", SINE]) == 130

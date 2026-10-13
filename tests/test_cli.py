from __future__ import annotations

import json
from pathlib import Path

import pytest

from tdmread._cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"
SINE = str(FIXTURES / "Synthetic.tdm")


def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "tdmread" in capsys.readouterr().out


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_info_reports_metadata_and_groups(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", SINE]) == 0
    out = capsys.readouterr().out
    assert "author: tdmread test suite" in out
    assert "Amplitudes (5 channels)" in out


def test_channels_lists_every_channel(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["channels", SINE]) == 0
    out = capsys.readouterr().out
    assert len(out.strip().splitlines()) == 10
    assert "Amplitudes\tA = 1" in out


def test_dump_csv_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", SINE, "-g", "Amplitudes", "-c", "A = 1", "-f", "csv"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0] == "index,A = 1"
    assert lines[1] == "0,0.0"
    assert len(lines) == 101


def test_dump_json_to_file(tmp_path: Path) -> None:
    out = tmp_path / "values.json"
    code = main(["dump", SINE, "-g", "Amplitudes", "-c", "A = 1", "-f", "json", "-o", str(out)])
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["name"] == "A = 1"
    assert payload["value_type"] == "eFloat64Usi"
    assert len(payload["data"]) == 100


def test_missing_file_errors_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", str(FIXTURES / "nope.tdm")]) == 1
    assert "error" in capsys.readouterr().err.lower()


def test_unknown_channel_errors(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dump", SINE, "-g", "Amplitudes", "-c", "missing"]) == 1
    assert "error" in capsys.readouterr().err.lower()

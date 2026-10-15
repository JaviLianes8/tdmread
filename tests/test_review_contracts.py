"""Contracts added after the independent reviews: names, encodings and command output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tdm_builder import Dataset, block, inline, stored

from tdmread import TdmError, TdmFileNotFoundError, read_tdm
from tdmread._cli import main

REPO = Path(__file__).resolve().parent.parent
TEXT = "caf" + chr(0xE9) + " " + chr(0x3A9) + " " + chr(0x1F600)


@pytest.mark.parametrize(
    "url",
    ["/".join(["abcdefgh"] * 3000) + ".tdx", "x" * 300 + ".tdx", "a?b.tdx", "a*b.tdx"],
)
def test_a_tdx_name_the_system_cannot_open_is_a_short_tdm_error(tmp_path: Path, url: str) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    dataset.url = url
    header = dataset.write(tmp_path)
    with pytest.raises(TdmError) as caught:
        read_tdm(header)
    assert len(str(caught.value)) < 120


def test_a_missing_tdx_names_it_briefly(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    with pytest.raises(TdmFileNotFoundError, match="TDX data not found"):
        read_tdm(dataset.write(tmp_path))


def test_json_dump_is_ascii_and_round_trips_any_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header = Dataset([inline(0, "string_sequence", f"<s>{TEXT}</s>")]).write(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "json"]) == 0
    out = capsys.readouterr().out
    assert out.isascii() and json.loads(out)["data"] == [TEXT]


@pytest.mark.parametrize("fmt", ["csv", "json"])
def test_dump_to_a_non_utf8_stdout_keeps_the_data_exact(tmp_path: Path, fmt: str) -> None:
    header = Dataset([inline(0, "string_sequence", f"<s>{TEXT}</s>")]).write(tmp_path)
    src = REPO / "src"
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    if src.is_dir():
        env["PYTHONPATH"] = str(src)
    command = [sys.executable, "-m", "tdmread", "dump", str(header), "-g", "G", "-c", "ch0"]
    done = subprocess.run([*command, "-f", fmt], capture_output=True, env=env, timeout=60)
    assert done.returncode == 0, done.stderr
    text = done.stdout.decode("utf-8")
    if fmt == "json":
        assert json.loads(text)["data"] == [TEXT]
    else:
        assert text.replace("\r\n", "\n") == f"index,ch0\n0,{TEXT}\n"


def test_channels_names_the_datatype_of_header_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    channel = inline(0, "string_sequence", "<s>a</s>")
    channel.extra = "<datatype>DT_STRING</datatype>"
    assert main(["channels", str(Dataset([channel]).write(tmp_path))]) == 0
    assert capsys.readouterr().out == "G\tch0\tDT_STRING\t1\n"

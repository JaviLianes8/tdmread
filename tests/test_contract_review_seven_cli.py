"""Contracts from the seventh independent review (command line and model): unpinned promises."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, inline

from tdmread import Channel, TdmError, read_tdm
from tdmread._cli import main
from tdmread._cli_output import emit, emit_data
from tdmread._props import Properties

_LINEAR = "<sequence_representation>implicit_linear</sequence_representation>"


def _dump(header: Path, *extra: str) -> list[str]:
    return ["dump", str(header), "-g", "G", "-c", "ch0", *extra]


class _NoEncoding(io.StringIO):
    encoding = None  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.refused = False

    def write(self, text: str) -> int:
        if not self.refused and not text.isascii():
            self.refused = True
            raise UnicodeEncodeError("ascii", text, 0, 1, "refused once")
        return super().write(text)


def test_a_stream_without_encoding_falls_back_to_utf8() -> None:
    # Guards against a stream that names no encoding being written as escaped ASCII.
    stream = _NoEncoding()
    text = "caf" + chr(0xE9) + "\n"
    emit(text, stream)
    assert stream.getvalue() == text


def test_data_follows_text_already_written(monkeypatch: pytest.MonkeyPatch) -> None:
    # Guards against data bytes overtaking text still held in the stdout text layer.
    raw = io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="utf-8", newline="")
    monkeypatch.setattr(sys, "stdout", out)
    out.write("head\n")
    emit_data("data\n")
    assert raw.getvalue() == b"head\ndata\n"


def test_dump_json_keeps_the_raw_channel_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against the JSON name escaped like the text listings (JSON escapes it itself).
    header = Dataset([Chan("a&#9;b", column="")]).write(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", "a\tb", "-f", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["name"] == "a\tb"


def test_a_closed_own_stdout_does_not_break_the_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against a closed process stdout (flush and fileno raise ValueError) escaping main.
    closed = open(tmp_path / "out.txt", "w", encoding="utf-8")  # noqa: SIM115
    closed.close()
    monkeypatch.setattr(sys, "stdout", closed)
    monkeypatch.setattr(sys, "__stdout__", closed)
    assert main(["info", "no-such-file.tdm"]) == 1


def test_dump_requires_a_group(tmp_path: Path) -> None:
    # Guards against --group made optional (a usage error turned into a read error).
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    with pytest.raises(SystemExit) as caught:
        main(["dump", str(header), "-c", "ch0"])
    assert caught.value.code == 2


def test_dump_with_an_empty_output_name_writes_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Guards against -o "" treated as a file name.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    assert main(_dump(header, "-o", "")) == 0
    assert capsys.readouterr().out == "index,ch0\n0,1.0\n"


def test_info_escapes_metadata(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Guards against a control character in the dataset metadata reaching the output raw.
    data = Dataset([inline(0, "double_sequence", "1")], root_extra="<title>a&#9;b</title>")
    assert main(["info", str(data.write(tmp_path))]) == 0
    assert "title: a\\tb" in capsys.readouterr().out.splitlines()


def test_generation_parameters_split_on_any_whitespace(tmp_path: Path) -> None:
    # Guards against parameters separated by a tab or a newline being refused.
    column = _LINEAR + "<generation_parameters>1&#9;2\n</generation_parameters>"
    header = Dataset([Chan("ch0", column=column, rows=3)]).write(tmp_path)
    assert read_tdm(header).group("G").channel("ch0").data == (1.0, 3.0, 5.0)


def test_a_generated_channel_without_rows_says_so(tmp_path: Path) -> None:
    # Guards against a missing row count reported as a malformed integer.
    column = _LINEAR + "<generation_parameters>1 2</generation_parameters>"
    header = Dataset([Chan("ch0", column=column)]).write(tmp_path)
    with pytest.raises(TdmError, match="has no row count"):
        read_tdm(header)


def test_properties_refuse_new_attributes() -> None:
    # Guards against the read-only mapping growing an instance dictionary.
    props = Properties({"a": 1})
    with pytest.raises(AttributeError):
        props.extra = 1  # type: ignore[attr-defined]


def test_to_numpy_keeps_integers() -> None:
    # Guards against integer channels converted to floating point.
    pytest.importorskip("numpy")
    array = Channel("n", "", "", "eInt32Usi", (1, 2, 3)).to_numpy()
    assert array.dtype.kind == "i"
    assert array.tolist() == [1, 2, 3]

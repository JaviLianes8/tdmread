"""Contracts from the fourteenth independent review: error types, causes and help output."""

from __future__ import annotations

import argparse
import builtins
from pathlib import Path

import pytest

from tdmread import Channel, TdmError, read_tdm
from tdmread._cli import main

_GENERATED = (
    '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
    '<tdm_root id="r"><name>demo</name><channelgroups>#xpointer(id("g"))'
    '</channelgroups></tdm_root><tdm_channelgroup id="g"><name>G</name>'
    '<channels>#xpointer(id("c"))</channels></tdm_channelgroup>'
    '<tdm_channel id="c"><name>U</name>'
    '<local_columns>#xpointer(id("l"))</local_columns></tdm_channel>'
    '<localcolumn id="l"><submatrix>#xpointer(id("m"))</submatrix>'
    "<sequence_representation>implicit_linear</sequence_representation>"
    "<generation_parameters>0 1</generation_parameters></localcolumn>"
    '<submatrix id="m"><number_of_rows>20000000</number_of_rows></submatrix>'
    "</usi:data></usi:tdm>"
)


def test_a_dataset_over_the_value_allowance_is_a_plain_tdm_error(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    header.write_text(_GENERATED, encoding="utf-8")
    with pytest.raises(TdmError, match="would need 20000000 more values") as info:
        read_tdm(header)
    assert type(info.value) is TdmError


def test_to_numpy_keeps_the_import_failure_as_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__
    failure = ImportError("numpy cannot be loaded here")

    def no_numpy(name: str, *args: object, **kwargs: object) -> object:
        if name == "numpy":
            raise failure
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_numpy)
    with pytest.raises(TdmError, match="pip install numpy") as info:
        Channel("n", "", "", "", (1.0,)).to_numpy()
    assert info.value.__cause__ is failure


@pytest.mark.parametrize("args", [["--help"], ["--version"], []])
def test_help_to_a_gone_stream_does_not_fail(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    # Python 3.10's argparse lets a failed write of help or usage text raise; later
    # versions swallow it. The command must behave the same on every supported version.
    def gone(self: argparse.ArgumentParser, message: str, file: object = None) -> None:
        raise BrokenPipeError("the reader went away")

    monkeypatch.setattr(argparse.ArgumentParser, "_print_message", gone)
    if args:
        with pytest.raises(SystemExit) as info:
            main(args)
        assert info.value.code == 0
    else:
        assert main(args) == 0

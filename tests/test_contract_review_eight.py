"""Contracts from the eighth independent review: promises no other test pinned."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, UnsupportedTdmError, read_tdm
from tdmread._cli import main
from tdmread._inline import inline_values

_LINEAR = "<sequence_representation>implicit_linear</sequence_representation>"


@pytest.mark.parametrize("command", ["info", "channels", "dump"])
def test_the_header_path_is_required(command: str) -> None:
    # Guards against a missing header path reaching the reader instead of a usage error.
    with pytest.raises(SystemExit) as caught:
        main([command])
    assert caught.value.code == 2


def test_dump_requires_a_channel(tmp_path: Path) -> None:
    # Guards against `dump` without --channel looking up a channel named None.
    header = Dataset([inline(0, "double_sequence", "1 2")]).write(tmp_path)
    with pytest.raises(SystemExit) as caught:
        main(["dump", str(header), "-g", "G"])
    assert caught.value.code == 2


def test_an_error_with_stderr_closed_is_not_written_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Guards against the error text falling back to standard output when stderr is gone.
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", None)
    assert main(["info", "no-such-file.tdm"]) == 1
    assert out.getvalue() == ""


def test_a_reference_to_a_missing_block_is_malformed_not_unsupported(tmp_path: Path) -> None:
    # Guards against a dangling block reference reported as an unsupported TDM feature.
    data = Dataset(
        [stored(0, "double_sequence", "missing")],
        blocks=block("b", 0, 1, "eFloat64Usi"),
        tdx=bytes(8),
    )
    with pytest.raises(TdmError, match="does not exist") as caught:
        read_tdm(data.write(tmp_path))
    assert not isinstance(caught.value, UnsupportedTdmError)


def test_channel_length_is_found_among_other_properties(tmp_path: Path) -> None:
    # Guards against NI_ChannelLength honoured only when it is the first property.
    props = (
        '<instance_attributes><string_attribute name="note"><s>x</s></string_attribute>'
        '<long_attribute name="NI_ChannelLength">3</long_attribute></instance_attributes>'
    )
    chan = Chan(
        "ch0",
        column=_LINEAR + "<generation_parameters>0 1</generation_parameters>",
        extra=props,
    )
    dataset = read_tdm(Dataset([chan]).write(tmp_path))
    assert dataset.group("G").channel("ch0").data == (0.0, 1.0, 2.0)


def test_a_shared_inline_sequence_is_decoded_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Guards against a value sequence decoded again for every column that refers to it.
    calls: list[int] = []

    def counting(*args: object) -> object:
        calls.append(1)
        return inline_values(*args)  # type: ignore[arg-type]

    monkeypatch.setattr("tdmread._explicit.inline_values", counting)
    first = inline(0, "double_sequence", "1 2 3")
    second = Chan("ch1", column='<values>#xpointer(id("s0"))</values>')
    dataset = read_tdm(Dataset([first, second]).write(tmp_path))
    group = dataset.group("G")
    assert group.channel("ch0").data == group.channel("ch1").data == (1.0, 2.0, 3.0)
    assert len(calls) == 1

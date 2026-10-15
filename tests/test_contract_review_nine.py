"""Contracts from the ninth independent review: promises no other test pinned."""

from __future__ import annotations

import errno
import io
import struct
import sys
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, UnsupportedTdmError, read_tdm
from tdmread._cli import main
from tdmread._sequence import GENERATED_ALLOWANCE

_VALUES = '<values>#xpointer(id("s0"))</values>'


def test_usage_text_names_the_command(capsys: pytest.CaptureFixture[str]) -> None:
    # Guards against help and usage errors naming a program other than `tdmread`.
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert capsys.readouterr().out.startswith("usage: tdmread ")
    with pytest.raises(SystemExit):
        main(["info"])
    assert "usage: tdmread info" in capsys.readouterr().err


def test_the_limit_message_reports_the_account_that_ran_out(tmp_path: Path) -> None:
    # Guards against the generated-values limit reported from the stored-values account.
    tdx = struct.pack("<4d", 1, 2, 3, 4)
    first = stored(0, "double_sequence", "b0")
    second = Chan(
        "ch1",
        column="<sequence_representation>implicit_linear</sequence_representation>"
        "<generation_parameters>0 1</generation_parameters>",
        rows=10**9,
    )
    data = Dataset([first, second], blocks=block("b0", 0, 4, "eFloat64Usi"), tdx=tdx)
    with pytest.raises(TdmError) as caught:
        read_tdm(data.write(tmp_path))
    assert f"is {GENERATED_ALLOWANCE + len(tdx)} more" in str(caught.value)


def test_a_narrow_block_bm_message_gives_stride_then_value_size(tmp_path: Path) -> None:
    # Guards against the blockSize and the value size swapped in the refusal.
    bm = (
        '<block_bm id="b0" byteOffset="0" blockOffset="0" blockSize="4" length="2" '
        'valueType="eFloat64Usi"/>'
    )
    data = Dataset([stored(0, "double_sequence", "b0")], blocks=bm, tdx=bytes(16))
    with pytest.raises(UnsupportedTdmError, match="blockSize 4 cannot hold a 8-byte value"):
        read_tdm(data.write(tmp_path))


@pytest.mark.parametrize("kind", ["longlong_sequence", "ulonglong_sequence", "ushort_sequence"])
@pytest.mark.parametrize("token", ["1_0", "٣"])
def test_wide_inline_integers_are_ascii_decimal_only(tmp_path: Path, kind: str, token: str) -> None:
    # Guards against inline integers parsed with int(), which takes underscores and
    # non-ASCII digits that no TDM writer produces.
    with pytest.raises(TdmError, match="invalid integer value"):
        read_tdm(Dataset([inline(0, kind, f"1 {token}")]).write(tmp_path))


def test_properties_behave_as_a_mapping_for_absent_names(tmp_path: Path) -> None:
    # Guards against a missing property name read as None instead of a KeyError.
    props = '<instance_attributes><long_attribute name="n">3</long_attribute></instance_attributes>'
    chan = inline(0, "double_sequence", "1")
    chan.extra = props
    found = read_tdm(Dataset([chan]).write(tmp_path)).group("G").channel("ch0").properties
    assert found["n"] == 3
    assert "absent" not in found
    assert found.get("absent", 7) == 7
    with pytest.raises(KeyError):
        found["absent"]


def test_elements_without_properties_have_none(tmp_path: Path) -> None:
    # Guards against an element with no instance_attributes reporting a property anyway.
    dataset = read_tdm(Dataset([inline(0, "double_sequence", "1")]).write(tmp_path))
    group = dataset.group("G")
    assert dict(dataset.properties) == {}
    assert dict(group.properties) == {}
    assert dict(group.channel("ch0").properties) == {}


def test_the_parameter_message_names_the_count_needed(tmp_path: Path) -> None:
    # Guards against the raw_linear refusal stating the wrong number of parameters.
    chan = inline(0, "double_sequence", "1 2")
    chan.column = (
        "<sequence_representation>raw_linear</sequence_representation>"
        "<generation_parameters>2</generation_parameters>" + _VALUES
    )
    with pytest.raises(TdmError, match=r"needs 2 generation parameter\(s\)"):
        read_tdm(Dataset([chan]).write(tmp_path))


class _FailingBuffer:
    def __init__(self, error: OSError) -> None:
        self.error = error

    def write(self, data: bytes) -> int:
        raise self.error

    def flush(self) -> None:
        pass


class _Stdout:
    encoding = "utf-8"

    def __init__(self, error: OSError) -> None:
        self.buffer = _FailingBuffer(error)

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


@pytest.mark.parametrize(
    "error",
    [BrokenPipeError(errno.EPIPE, "gone"), OSError(errno.ENOSPC, "No space left on device")],
)
def test_a_failed_data_write_is_not_reported_as_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: OSError
) -> None:
    # Guards against write errors on the data stream swallowed so `dump` exits 0.
    header = Dataset([inline(0, "double_sequence", "1 2")]).write(tmp_path)
    err = io.StringIO()
    monkeypatch.setattr(sys, "stdout", _Stdout(error))
    monkeypatch.setattr(sys, "stderr", err)
    assert main(["dump", str(header), "-g", "G", "-c", "ch0"]) == 1
    if not isinstance(error, BrokenPipeError):
        assert "No space left on device" in err.getvalue()

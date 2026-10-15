"""Contracts from the second blind mutation round: each pins a promise no test checked."""

from __future__ import annotations

import errno
import io
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from tdmread import TdmError, TdmFileNotFoundError, _cli, _tdx, read_tdm
from tdmread._cli_output import MESSAGE_LIMIT, short

NS = 'xmlns:usi="http://www.ni.com/Schemas/USI/1_0"'
DATA = (
    '<tdm_root id="r"><name>n</name>{props}<channelgroups>#xpointer(id("g"))</channelgroups>'
    '</tdm_root><tdm_channelgroup id="g"><name>G</name><channels>#xpointer(id("c"))'
    '</channels></tdm_channelgroup><tdm_channel id="c"><name>U</name><local_columns>'
    '#xpointer(id("l"))</local_columns></tdm_channel><localcolumn id="l"><values>'
    '#xpointer(id("s"))</values></localcolumn>{seq}'
)


def _write(folder: Path, include: str, seq: str, props: str = "") -> Path:
    body = DATA.format(props=props, seq=seq)
    inner = f"<usi:include>{include}</usi:include><usi:data>{body}</usi:data>"
    text = f"<usi:tdm {NS}>{inner}</usi:tdm>"
    header = folder / "h.tdm"
    header.write_text(text, encoding="utf-8")
    return header


def _external(folder: Path, blocks: str, url: str = "d.tdx", files: str = "") -> Path:
    include = f'<file byteOrder="littleEndian" url="{url}">{blocks}</file>{files}'
    return _write(folder, include, '<byte_sequence id="s"><values external="b"/></byte_sequence>')


def _inline(folder: Path, seq: str, props: str = "") -> Path:
    return _write(folder, "", seq, props)


def _bm(stride: int, length: int = 3, offset: int = 0) -> str:
    return (
        f'<block_bm id="b" byteOffset="{offset}" length="{length}" blockSize="{stride}" '
        'blockOffset="0" valueType="eInt8Usi"/>'
    )


def _values(header: Path, tdx: Path | None = None) -> tuple[Any, ...]:
    return read_tdm(header, tdx).group("G").channel("U").data


def test_infinity_spelled_out_is_a_float(tmp_path: Path) -> None:
    seq = '<double_sequence id="s"><values>infinity -Infinity</values></double_sequence>'
    assert _values(_inline(tmp_path, seq)) == (math.inf, -math.inf)


def test_empty_property_name_is_kept(tmp_path: Path) -> None:
    attr = '<string_attribute name=""><s>x</s></string_attribute>'
    props = f"<instance_attributes>{attr}</instance_attributes>"
    seq = '<double_sequence id="s"><values>1</values></double_sequence>'
    assert dict(read_tdm(_inline(tmp_path, seq, props)).properties) == {"": "x"}


def test_first_file_element_names_the_tdx(tmp_path: Path) -> None:
    (tmp_path / "d.tdx").write_bytes(bytes([7, 8, 9]))
    second = '<file byteOrder="bigEndian" url="other.tdx"/>'
    block = '<block id="b" byteOffset="0" length="3" valueType="eInt8Usi"/>'
    assert _values(_external(tmp_path, block, files=second)) == (7, 8, 9)


def test_first_block_with_a_repeated_id_wins(tmp_path: Path) -> None:
    (tmp_path / "d.tdx").write_bytes(bytes(range(10)))
    blocks = (
        '<block id="b" byteOffset="0" length="2" valueType="eInt8Usi"/>'
        '<block id="b" byteOffset="5" length="2" valueType="eInt8Usi"/>'
    )
    assert _values(_external(tmp_path, blocks)) == (0, 1)


@pytest.mark.parametrize("stem", ["x" * 36, "y" * 37])
def test_missing_tdx_label_is_the_url_tail(tmp_path: Path, stem: str) -> None:
    url = stem + ".tdx"
    expected = repr(url) if len(url) <= 40 else repr("..." + url[-37:])
    with pytest.raises(TdmFileNotFoundError) as caught:
        _values(_external(tmp_path, _bm(1), url=url))
    assert str(caught.value) == f"TDX data not found: {expected}"


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("..\\up.tdx", "is outside the header's folder"),
        ("a\x1fb.tdx", "is not a valid file name"),
        ("data\\...", "is not a valid file name"),
        ("data\\ . ", "is not a valid file name"),
    ],
)
def test_url_refused_before_opening(tmp_path: Path, url: str, reason: str) -> None:
    with pytest.raises(TdmError) as caught:
        _tdx.locate(tmp_path / "h.tdm", url, None)
    assert type(caught.value) is TdmError
    assert reason in str(caught.value)


def test_sparse_items_are_stride_apart(tmp_path: Path) -> None:
    (tmp_path / "d.tdx").write_bytes(bytes(range(101)))
    assert _values(_external(tmp_path, _bm(50))) == (0, 50, 100)


def test_sparse_block_past_the_end_is_a_tdm_error(tmp_path: Path) -> None:
    (tmp_path / "d.tdx").write_bytes(bytes(range(60)))
    with pytest.raises(TdmError, match="reaches byte 101"):
        _values(_external(tmp_path, _bm(50)))


class _Counting(io.FileIO):
    total = 0

    def read(self, size: int | None = -1, /) -> bytes:
        data = super().read(size)
        _Counting.total += len(data or b"")
        return data or b""


def test_sparse_reads_stay_within_four_times_the_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "d.tdx").write_bytes(bytes(range(101)))
    _Counting.total = 0
    monkeypatch.setattr(_tdx, "open", lambda path, mode: _Counting(path, "rb"), raising=False)
    assert _values(_external(tmp_path, _bm(50))) == (0, 50, 100)
    assert 0 < _Counting.total <= 4 * 3


def test_silence_leaves_a_callers_stream_alone(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    with target.open("w", encoding="utf-8") as stream:
        stream.write("a")
        stream.flush()
        _cli._silence(stream)
        stream.write("b")
    assert target.read_text(encoding="utf-8") == "ab"


def test_message_of_exactly_the_limit_is_not_cut() -> None:
    text = "m" * MESSAGE_LIMIT
    assert short(text) == text
    assert short(text + "x") == "m" * (MESSAGE_LIMIT - 3) + "..."


class _DeadErr:
    encoding = "utf-8"

    def write(self, text: str) -> int:
        raise OSError(errno.EIO, "stderr is gone")

    def flush(self) -> None:
        return None


def test_failing_stderr_still_exits_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", _DeadErr())
    assert _cli.main(["info", str(tmp_path / "missing.tdm")]) == 1


def test_dump_to_a_stream_without_buffer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seq = '<double_sequence id="s"><values>0.5 1.5</values></double_sequence>'
    header = _inline(tmp_path, seq)
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert _cli.main(["dump", str(header), "-g", "G", "-c", "U"]) == 0
    assert out.getvalue() == "index,U\n0,0.5\n1,1.5\n"

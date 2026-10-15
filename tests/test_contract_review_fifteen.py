"""Contracts from the fifteenth independent review: references, allowance, output shape."""

from __future__ import annotations

import json
import os
import re
import sys
import types
from pathlib import Path
from typing import IO, Any

import pytest

from tdmread import TdmError, _cli, _tdx, read_tdm, supported_value_types

NS = 'xmlns:usi="http://www.ni.com/Schemas/USI/1_0"'
BODY = (
    '<tdm_root id="r"><name>n</name><channelgroups>#xpointer(id("g"))</channelgroups>'
    '</tdm_root><tdm_channelgroup id="g"><name>G</name><channels>#xpointer(id("c"))'
    '</channels></tdm_channelgroup><tdm_channel id="c"><name>U</name><local_columns>'
    '#xpointer(id("l"))</local_columns></tdm_channel><localcolumn id="l">{column}'
    "</localcolumn>{extra}"
)


def _header(folder: Path, column: str, extra: str = "", include: str = "") -> Path:
    body = BODY.format(column=column, extra=extra)
    inner = f"<usi:include>{include}</usi:include><usi:data>{body}</usi:data>"
    text = f"<usi:tdm {NS}>{inner}</usi:tdm>"
    header = folder / "h.tdm"
    header.write_text(text, encoding="utf-8")
    return header


def _file(blocks: str) -> str:
    return f'<file byteOrder="littleEndian" url="d.tdx">{blocks}</file>'


def test_supported_value_types_are_exactly_the_decoded_ones() -> None:
    assert supported_value_types() == frozenset(
        {
            "eInt8Usi",
            "eSInt8Usi",
            "eUInt8Usi",
            "eInt16Usi",
            "eUInt16Usi",
            "eInt32Usi",
            "eUInt32Usi",
            "eInt64Usi",
            "eUInt64Usi",
            "eFloat32Usi",
            "eFloat64Usi",
            "eTimeUsi",
        }
    )


def test_a_value_reference_never_resolves_to_a_block(tmp_path: Path) -> None:
    # Blocks and value sequences live in separate id spaces: a reference naming only a
    # block is a missing value sequence, not an empty channel.
    # The block carries a child element so it is not an empty (false) element.
    block = '<block id="s" byteOffset="0" length="1" valueType="eInt8Usi"><x/></block>'
    blocks = _file(block)
    header = _header(tmp_path, '<values>#xpointer(id("s"))</values>', include=blocks)
    (tmp_path / "d.tdx").write_bytes(b"\x07")
    with pytest.raises(TdmError, match="value sequence that does not exist: 's'"):
        read_tdm(header)


def test_an_empty_value_reference_is_a_missing_sequence(tmp_path: Path) -> None:
    header = _header(tmp_path, '<values>#xpointer(id(""))</values>')
    with pytest.raises(TdmError, match="value sequence that does not exist: ''"):
        read_tdm(header)


def test_a_missing_tdx_grants_no_extra_allowance(tmp_path: Path) -> None:
    # The allowance grows with the .tdx size; a .tdx that cannot be found adds nothing.
    column = (
        "<sequence_representation>implicit_constant</sequence_representation>"
        '<generation_parameters>1</generation_parameters><submatrix>#xpointer(id("m"))'
        "</submatrix>"
    )
    extra = '<submatrix id="m"><number_of_rows>10000001</number_of_rows></submatrix>'
    unused = _file('<block id="b" byteOffset="0" length="1" valueType="eInt8Usi"/>')
    header = _header(tmp_path, column, extra, include=unused)
    message = "would need 10000001 more values; the limit for this file is 10000000 more"
    with pytest.raises(TdmError, match=message):
        read_tdm(header)


def test_a_generated_channel_without_rows_names_both_sources(tmp_path: Path) -> None:
    column = (
        "<sequence_representation>implicit_linear</sequence_representation>"
        "<generation_parameters>0 1</generation_parameters>"
    )
    expected = "a generated channel has no row count (submatrix number_of_rows or NI_ChannelLength)"
    with pytest.raises(TdmError, match=f"^{re.escape(expected)}$"):
        read_tdm(_header(tmp_path, column))


def test_sparse_items_are_read_through_the_one_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    real_open = open

    def counting(path: Any, mode: str = "r", *args: Any, **kwargs: Any) -> IO[Any]:
        opened.append(str(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(_tdx, "open", counting, raising=False)
    block = (
        '<block_bm id="b" byteOffset="0" length="3" blockSize="64" blockOffset="0" '
        'valueType="eInt8Usi"/>'
    )
    seq = '<byte_sequence id="s"><values external="b"/></byte_sequence>'
    header = _header(tmp_path, '<values>#xpointer(id("s"))</values>', seq, _file(block))
    raw = bytearray(129)
    raw[0], raw[64], raw[128] = 1, 2, 3
    (tmp_path / "d.tdx").write_bytes(bytes(raw))
    assert read_tdm(header).group("G").channel("U").data == (1, 2, 3)
    assert opened == [str(tmp_path / "d.tdx")]


def test_dump_json_has_exactly_the_documented_keys(tmp_path: Path) -> None:
    seq = '<double_sequence id="s"><values>0.5 1.5</values></double_sequence>'
    header = _header(tmp_path, '<values>#xpointer(id("s"))</values>', seq)
    out = tmp_path / "out.json"
    args = ["dump", str(header), "-g", "G", "-c", "U", "-f", "json", "-o", str(out)]
    assert _cli.main(args) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    keys = ["name", "unit", "value_type", "representation", "datatype", "length", "data"]
    assert list(payload) == keys
    assert payload["data"] == [0.5, 1.5]


def test_silencing_a_gone_stream_closes_the_null_device(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = sys.__stdout__
    if stream is None:
        pytest.skip("no process standard output")
    try:
        target = stream.fileno()
    except (OSError, ValueError):
        pytest.skip("standard output has no descriptor")
    calls: list[tuple[object, ...]] = []
    fake = types.SimpleNamespace(
        devnull=os.devnull,
        O_WRONLY=os.O_WRONLY,
        open=lambda path, flags: target + 1000,
        dup2=lambda source, dest: calls.append(("dup2", source, dest)),
        close=lambda fd: calls.append(("close", fd)),
    )
    monkeypatch.setattr(_cli, "os", fake)
    _cli._silence(stream)
    assert calls == [("dup2", target + 1000, target), ("close", target + 1000)]

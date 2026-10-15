"""Contracts from the twelfth independent review: namespaces, shared columns, odd inputs."""

from __future__ import annotations

import os
import shutil
import stat
import struct
from pathlib import Path

import pytest

from tdmread import TdmError, read_tdm

FIXTURES = Path(__file__).parent / "fixtures" / "labview2026"


def _channel(index: int, name: str, column: str) -> str:
    return (
        f'<tdm_channel id="c{index}"><name>{name}</name>'
        f'<local_columns>#xpointer(id("{column}"))</local_columns></tdm_channel>'
    )


def _header(body: str, channels: list[str], blocks: str = "", root: str = "") -> str:
    refs = " ".join(f'id("c{i}")' for i in range(len(channels)))
    return (
        f'<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"{root} version="1.0">'
        f'<usi:include><file byteOrder="littleEndian" url="data.tdx">{blocks}</file>'
        '</usi:include><usi:data><tdm_root id="r"><name>n</name>'
        '<channelgroups>#xpointer(id("g"))</channelgroups></tdm_root>'
        f'<tdm_channelgroup id="g"><name>G</name><channels>#xpointer({refs})</channels>'
        "</tdm_channelgroup>" + "".join(channels) + body + "</usi:data></usi:tdm>"
    )


_TWO_KINDS = (
    '<localcolumn id="l0"><values>#xpointer(id("s0"))</values></localcolumn>'
    '<double_sequence id="s0"><values external="b"/></double_sequence>'
    '<localcolumn id="l1"><values>#xpointer(id("s1"))</values></localcolumn>'
    '<double_sequence id="s1"><values>1.5 2.5</values></double_sequence>'
)
_BLOCK = '<block id="b" byteOffset="0" length="2" valueType="eFloat64Usi"/>'


@pytest.mark.parametrize("root", ["", ' xmlns="urn:example:tdm"'])
def test_a_default_namespace_on_every_element_reads_the_same(tmp_path: Path, root: str) -> None:
    header = tmp_path / "data.tdm"
    channels = [_channel(0, "A", "l0"), _channel(1, "B", "l1")]
    header.write_text(_header(_TWO_KINDS, channels, _BLOCK, root), encoding="utf-8")
    (tmp_path / "data.tdx").write_bytes(struct.pack("<2d", 0.25, -4.0))
    dataset = read_tdm(header)
    assert dataset.metadata.name == "n"
    group = dataset.group("G")
    assert group.channel("A").data == (0.25, -4.0)
    assert group.channel("A").value_type == "eFloat64Usi"
    assert group.channel("B").data == (1.5, 2.5)


_SCALED = (
    '<localcolumn id="l0"><sequence_representation>raw_linear</sequence_representation>'
    "<generation_parameters>1 2</generation_parameters>"
    '<values>#xpointer(id("s0"))</values></localcolumn>'
    '<byte_sequence id="s0"><values external="b"/></byte_sequence>'
)


def _shared_scaled(tmp_path: Path, channels: int, length: int) -> Path:
    header = tmp_path / "data.tdm"
    names = [_channel(i, f"ch{i}", "l0") for i in range(channels)]
    block = f'<block id="b" byteOffset="0" length="{length}" valueType="eInt8Usi"/>'
    header.write_text(_header(_SCALED, names, block), encoding="utf-8")
    (tmp_path / "data.tdx").write_bytes((bytes(range(256)) * (length // 256 + 1))[:length])
    return header


def test_a_scaled_column_shared_by_many_channels_is_decoded_once(tmp_path: Path) -> None:
    group = read_tdm(_shared_scaled(tmp_path, 3, 4)).group("G")
    first = group.channels[0].data
    assert first == (1.0, 3.0, 5.0, 7.0)
    assert all(channel.data is first for channel in group.channels)


def test_a_shared_scaled_column_is_charged_once_against_the_allowance(tmp_path: Path) -> None:
    # Twelve channels share one column of a million values: one scaled copy fits the
    # allowance, twelve copies would not.
    group = read_tdm(_shared_scaled(tmp_path, 12, 1_000_000)).group("G")
    assert len(group) == 12 and all(len(channel) == 1_000_000 for channel in group)


def test_a_scaled_column_storing_text_is_malformed_not_unsupported(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    body = (
        '<localcolumn id="l0"><sequence_representation>raw_linear</sequence_representation>'
        "<generation_parameters>0 1</generation_parameters>"
        '<values>#xpointer(id("s0"))</values></localcolumn>'
        '<string_sequence id="s0"><values><s>a</s></values></string_sequence>'
    )
    header.write_text(_header(body, [_channel(0, "A", "l0")]), encoding="utf-8")
    with pytest.raises(TdmError, match="raw_linear channel must store numbers") as info:
        read_tdm(header)
    assert type(info.value) is TdmError


def test_an_empty_tdx_path_is_not_replaced_by_the_headers_url(tmp_path: Path) -> None:
    for name in ("gt_types_0.tdm", "gt_types_0.tdx"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    with pytest.raises(TdmError):
        read_tdm(tmp_path / "gt_types_0.tdm", "")


def test_a_read_only_tdx_is_read(tmp_path: Path) -> None:
    for name in ("gt_types_0.tdm", "gt_types_0.tdx"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    tdx = tmp_path / "gt_types_0.tdx"
    expected = read_tdm(tmp_path / "gt_types_0.tdm")
    os.chmod(tdx, stat.S_IREAD)
    try:
        # repr, not ==: the fixture holds NaN values, which never compare equal.
        assert repr(read_tdm(tmp_path / "gt_types_0.tdm")) == repr(expected)
    finally:
        os.chmod(tdx, stat.S_IREAD | stat.S_IWRITE)


def test_an_empty_time_property_is_kept_as_its_text(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    root = (
        "<instance_attributes>"
        '<time_attribute name="empty"></time_attribute>'
        '<time_attribute name="blank">  </time_attribute>'
        "</instance_attributes>"
    )
    text = _header("", []).replace("<name>n</name>", "<name>n</name>" + root)
    header.write_text(text, encoding="utf-8")
    assert dict(read_tdm(header).properties) == {"empty": "", "blank": ""}


def test_the_allowance_message_names_the_values_asked_for(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    body = (
        '<localcolumn id="l0"><submatrix>#xpointer(id("m"))</submatrix>'
        "<sequence_representation>implicit_linear</sequence_representation>"
        "<generation_parameters>0 1</generation_parameters></localcolumn>"
        '<submatrix id="m"><number_of_rows>20000000</number_of_rows></submatrix>'
    )
    header.write_text(_header(body, [_channel(0, "A", "l0")]), encoding="utf-8")
    with pytest.raises(TdmError, match="would need 20000000 more values"):
        read_tdm(header)

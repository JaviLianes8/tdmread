from __future__ import annotations

import struct
from pathlib import Path

import pytest

from tdmread import (
    TdmError,
    TdmFileNotFoundError,
    UnsupportedTdmError,
    read_tdm,
)

_TDM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0" version="1.0">
  <usi:include>
    <file url="{url}" byteOrder="{order}">
      <block id="inc0" valueType="eFloat64Usi" byteOffset="0" length="3"/>
      <block id="inc1" valueType="eInt32Usi" byteOffset="24" length="3"/>
    </file>
  </usi:include>
  <usi:data>
    <tdm_root id="root0">
      <name>root</name>
      <channelgroups>id("grp0")</channelgroups>
    </tdm_root>
    <tdm_channelgroup id="grp0">
      <name>Measurements</name>
      <channels>id("ch0") id("ch1")</channels>
    </tdm_channelgroup>
    <tdm_channel id="ch0">
      <name>voltage</name>
      <unit_string>V</unit_string>
      <description>line voltage</description>
      <local_columns>id("lc0")</local_columns>
    </tdm_channel>
    <tdm_channel id="ch1">
      <name>count</name>
      <unit_string></unit_string>
      <description></description>
      <local_columns>id("lc1")</local_columns>
    </tdm_channel>
    <localcolumn id="lc0">
      <sequence_representation>explicit</sequence_representation>
      <values>id("seq0")</values>
    </localcolumn>
    <localcolumn id="lc1">
      <sequence_representation>explicit</sequence_representation>
      <values>id("seq1")</values>
    </localcolumn>
    <double_sequence id="seq0"><values external="inc0"/></double_sequence>
    <long_sequence id="seq1"><values external="inc1"/></long_sequence>
  </usi:data>
</usi:tdm>
"""

_FLOATS = (1.5, 2.5, 3.5)
_INTS = (10, 20, 30)


def _write_pair(directory: Path, order: str = "littleEndian", url: str = "sample.tdx") -> Path:
    endian = "<" if order == "littleEndian" else ">"
    payload = struct.pack(f"{endian}3d", *_FLOATS) + struct.pack(f"{endian}3i", *_INTS)
    tdx = directory / url
    tdx.parent.mkdir(parents=True, exist_ok=True)
    tdx.write_bytes(payload)
    tdm = directory / "sample.tdm"
    tdm.write_text(_TDM_TEMPLATE.format(url=url, order=order), encoding="utf-8")
    return tdm


def test_reads_groups_and_channel_names(tmp_path: Path) -> None:
    result = read_tdm(_write_pair(tmp_path))
    group = result.group("Measurements")
    assert [channel.name for channel in group.channels] == ["voltage", "count"]


def test_reads_float_channel_values_and_metadata(tmp_path: Path) -> None:
    group = read_tdm(_write_pair(tmp_path)).group("Measurements")
    voltage = group.channel("voltage")
    assert voltage.data == _FLOATS
    assert voltage.unit == "V"
    assert voltage.description == "line voltage"
    assert voltage.value_type == "eFloat64Usi"


def test_reads_integer_channel_values(tmp_path: Path) -> None:
    group = read_tdm(_write_pair(tmp_path)).group("Measurements")
    assert group.channel("count").data == _INTS


def test_big_endian_is_decoded_correctly(tmp_path: Path) -> None:
    group = read_tdm(_write_pair(tmp_path, order="bigEndian")).group("Measurements")
    assert group.channel("voltage").data == _FLOATS
    assert group.channel("count").data == _INTS


def test_tdx_is_located_by_the_header_reference(tmp_path: Path) -> None:
    group = read_tdm(_write_pair(tmp_path, url="data/other.tdx")).group("Measurements")
    assert group.channel("voltage").data == _FLOATS


def test_missing_tdx_raises(tmp_path: Path) -> None:
    tdm = _write_pair(tmp_path)
    (tmp_path / "sample.tdx").unlink()
    with pytest.raises(TdmFileNotFoundError):
        read_tdm(tdm)


def test_missing_tdm_header_raises(tmp_path: Path) -> None:
    with pytest.raises(TdmFileNotFoundError):
        read_tdm(tmp_path / "absent.tdm")


def test_unsupported_sequence_representation_raises(tmp_path: Path) -> None:
    tdm = _write_pair(tmp_path)
    tdm.write_text(
        tdm.read_text(encoding="utf-8").replace(
            "<sequence_representation>explicit</sequence_representation>",
            "<sequence_representation>implicit_saw</sequence_representation>",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedTdmError):
        read_tdm(tdm)


def test_unknown_value_type_raises(tmp_path: Path) -> None:
    tdm = _write_pair(tmp_path)
    tdm.write_text(
        tdm.read_text(encoding="utf-8").replace("eFloat64Usi", "eExtendedUsi"),
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedTdmError):
        read_tdm(tdm)


def test_unknown_byte_order_raises(tmp_path: Path) -> None:
    tdm = _write_pair(tmp_path)
    tdm.write_text(
        tdm.read_text(encoding="utf-8").replace('byteOrder="littleEndian"', 'byteOrder="middle"'),
        encoding="utf-8",
    )
    with pytest.raises(UnsupportedTdmError):
        read_tdm(tdm)


def test_truncated_tdx_raises(tmp_path: Path) -> None:
    tdm = _write_pair(tmp_path)
    (tmp_path / "sample.tdx").write_bytes(b"\x00\x00")
    with pytest.raises(TdmError):
        read_tdm(tdm)

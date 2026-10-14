"""Synthetic tests for implicit-linear sequence generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdmread import TdmError, read_tdm

_IMPLICIT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0" version="1.0">
  <usi:data>
    <tdm_root id="root0">
      <name>root</name>
      <channelgroups>id("grp0")</channelgroups>
    </tdm_root>
    <tdm_channelgroup id="grp0">
      <name>Axis</name>
      <channels>id("ch0")</channels>
    </tdm_channelgroup>
    <tdm_channel id="ch0">
      <name>time</name>
      <instance_attributes>
        <long_attribute name="NI_ChannelLength">{count}</long_attribute>
      </instance_attributes>
      <local_columns>id("lc0")</local_columns>
    </tdm_channel>
    <localcolumn id="lc0">
      <sequence_representation>implicit_linear</sequence_representation>
      {params}
      <values>id("seq0")</values>
    </localcolumn>
    <double_sequence id="seq0"><values external="inc0"/></double_sequence>
  </usi:data>
</usi:tdm>
"""


def _write(directory: Path, count: int, params: str) -> Path:
    tdm = directory / "axis.tdm"
    tdm.write_text(_IMPLICIT_TEMPLATE.format(count=count, params=params), encoding="utf-8")
    return tdm


def test_generates_offset_and_increment(tmp_path: Path) -> None:
    tdm = _write(tmp_path, 5, "<generation_parameters>10 2.5</generation_parameters>")
    channel = read_tdm(tdm).group("Axis").channel("time")
    assert channel.representation == "implicit_linear"
    assert channel.value_type == ""
    assert channel.data == (10.0, 12.5, 15.0, 17.5, 20.0)


def test_missing_generation_parameters_and_stored_values_raise(tmp_path: Path) -> None:
    # NI's reader takes missing parameters from the stored values; here there are none.
    tdm = _write(tmp_path, 4, "")
    with pytest.raises(TdmError):
        read_tdm(tdm)


def test_implicit_channel_needs_no_tdx(tmp_path: Path) -> None:
    tdm = _write(tmp_path, 3, "<generation_parameters>0 1</generation_parameters>")
    # No .tdx file exists next to the header; implicit axes must still read.
    assert read_tdm(tdm).group("Axis").channel("time").data == (0.0, 1.0, 2.0)


def test_implicit_without_length_raises(tmp_path: Path) -> None:
    tdm = tmp_path / "axis.tdm"
    body = _IMPLICIT_TEMPLATE.format(count=3, params="")
    body = body.replace('<long_attribute name="NI_ChannelLength">3</long_attribute>', "")
    tdm.write_text(body, encoding="utf-8")
    with pytest.raises(TdmError):
        read_tdm(tdm)

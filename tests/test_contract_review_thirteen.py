"""Contracts from the thirteenth independent review: error types and exact header bytes."""

from __future__ import annotations

from pathlib import Path

import pytest

from tdmread import TdmError, TdmFileNotFoundError, UnsupportedTdmError, read_tdm

_HEADER = (
    '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
    '<tdm_root id="r"><name>demo</name><channelgroups>#xpointer(id("g"))'
    '</channelgroups></tdm_root><tdm_channelgroup id="g"><name>G</name>'
    '<channels>#xpointer(id("c"))</channels></tdm_channelgroup>'
    '<tdm_channel id="c"><name>U</name>'
    '<local_columns>#xpointer(id("l"))</local_columns></tdm_channel>'
    '<localcolumn id="l"><values>#xpointer(id("s"))</values></localcolumn>'
    '<double_sequence id="s"><values>0.5 1.5</values></double_sequence>'
    "</usi:data></usi:tdm>"
)


def test_the_error_classes_derive_only_from_what_they_promise() -> None:
    assert TdmError.__mro__ == (TdmError, Exception, BaseException, object)
    assert UnsupportedTdmError.__bases__ == (TdmError,)
    assert TdmFileNotFoundError.__bases__ == (TdmError, FileNotFoundError)
    assert not issubclass(TdmError, (ValueError, LookupError, OSError))


def test_a_dtd_is_a_plain_tdm_error_not_a_missing_file(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    header.write_text('<!DOCTYPE tdm [<!ENTITY e "x">]>' + _HEADER, encoding="utf-8")
    with pytest.raises(TdmError, match="declares a DTD") as info:
        read_tdm(header)
    assert type(info.value) is TdmError
    assert not isinstance(info.value, FileNotFoundError)


def test_text_before_the_xml_declaration_is_not_well_formed(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    header.write_bytes(b' \n<?xml version="1.0" encoding="UTF-8"?>' + _HEADER.encode())
    with pytest.raises(TdmError, match="not well-formed XML") as info:
        read_tdm(header)
    assert type(info.value) is TdmError


def test_a_utf16_header_ending_in_a_newline_is_read(tmp_path: Path) -> None:
    header = tmp_path / "data.tdm"
    text = '<?xml version="1.0" encoding="UTF-16"?>' + _HEADER + "\n"
    header.write_bytes(b"\xfe\xff" + text.encode("utf-16-be"))
    assert read_tdm(header).group("G").channel("U").data == (0.5, 1.5)

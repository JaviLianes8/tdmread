"""Contracts from the seventh independent review (reading): promises no other test pinned."""

from __future__ import annotations

from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, TdmFileNotFoundError, read_tdm

_LINEAR = "<sequence_representation>implicit_linear</sequence_representation>"


def _dump(header: Path, *extra: str) -> list[str]:
    return ["dump", str(header), "-g", "G", "-c", "ch0", *extra]


def test_a_relative_tdx_override_is_taken_from_the_working_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Guards against a caller's relative --tdx/tdx_path resolved against the header folder.
    (tmp_path / "h").mkdir()
    (tmp_path / "w").mkdir()
    data = Dataset([stored(0, "long_sequence", "b")], blocks=block("b", 0, 1, "eInt32Usi"))
    header = data.write(tmp_path / "h")
    (tmp_path / "w" / "mine.tdx").write_bytes((5).to_bytes(4, "little"))
    monkeypatch.chdir(tmp_path / "w")
    assert read_tdm(header, "mine.tdx").group("G").channel("ch0").data == (5,)


def test_an_invalid_tdx_name_is_malformed_not_missing(tmp_path: Path) -> None:
    # Guards against a forbidden character in the url reported as a missing file.
    data = Dataset([stored(0, "double_sequence", "b")], blocks=block("b", 0, 1, "eFloat64Usi"))
    data.url = "a|b.tdx"
    with pytest.raises(TdmError, match="not a valid file name") as caught:
        read_tdm(data.write(tmp_path))
    assert not isinstance(caught.value, TdmFileNotFoundError)


def test_a_denied_tdx_propagates_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Guards against a permission failure of the system dressed up as a bad dataset.
    data = Dataset([stored(0, "double_sequence", "b")], blocks=block("b", 0, 1, "eFloat64Usi"))
    header = data.write(tmp_path)

    def denied(*args: object, **kwargs: object) -> object:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr("tdmread._tdx.open", denied, raising=False)
    with pytest.raises(PermissionError) as caught:
        read_tdm(header)
    assert not isinstance(caught.value, TdmError)


def test_windows_invalid_name_error_is_a_bad_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Guards against Windows error 123 (invalid name) propagating as a system failure.
    data = Dataset([stored(0, "double_sequence", "b")], blocks=block("b", 0, 1, "eFloat64Usi"))
    header = data.write(tmp_path)

    def bad_name(*args: object, **kwargs: object) -> object:
        exc = OSError("The filename syntax is incorrect")
        exc.winerror = 123  # type: ignore[attr-defined,unused-ignore]
        raise exc

    monkeypatch.setattr("tdmread._tdx.open", bad_name, raising=False)
    with pytest.raises(TdmError, match=r"cannot open the \.tdx"):
        read_tdm(header)


def test_sparse_block_bm_items_keep_their_byte_order(tmp_path: Path) -> None:
    # Guards against items read one by one (stride over four items) being reassembled wrongly.
    blocks = (
        '<block_bm id="b" byteOffset="0" blockOffset="0" blockSize="64" length="2" '
        'valueType="eInt32Usi"/>'
    )
    raw = bytearray(68)
    raw[0:4] = (1).to_bytes(4, "little")
    raw[64:68] = (258).to_bytes(4, "little")
    data = Dataset([stored(0, "long_sequence", "b")], blocks=blocks, tdx=bytes(raw))
    assert read_tdm(data.write(tmp_path)).group("G").channel("ch0").data == (1, 258)


def test_an_empty_id_is_still_an_id(tmp_path: Path) -> None:
    # Pins current behaviour: id("") resolves to the element whose id is the empty string.
    xml = (
        '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0"><usi:data>'
        '<tdm_root id="r"><name>n</name><channelgroups>#xpointer(id("g"))</channelgroups>'
        '</tdm_root><tdm_channelgroup id="g"><name>G</name>'
        '<channels>#xpointer(id(""))</channels></tdm_channelgroup>'
        '<tdm_channel id=""><name>U</name></tdm_channel>'
        "</usi:data></usi:tdm>"
    )
    header = tmp_path / "empty-id.tdm"
    header.write_text(xml, encoding="utf-8")
    assert read_tdm(header).group("G").channel_names == ("U",)


def test_an_empty_byte_offset_is_malformed(tmp_path: Path) -> None:
    # Guards against byteOffset="" taken as an absent attribute (offset 0).
    blocks = '<block id="b" byteOffset="" length="1" valueType="eFloat64Usi"/>'
    data = Dataset([stored(0, "double_sequence", "b")], blocks=blocks, tdx=bytes(8))
    with pytest.raises(TdmError, match="byteOffset"):
        read_tdm(data.write(tmp_path))


def test_case_folded_infinity_is_not_a_float(tmp_path: Path) -> None:
    # Guards against Unicode case folding letting a dotless i through to float().
    word = chr(0x131) + "nf"
    with pytest.raises(TdmError, match="invalid floating-point value"):
        read_tdm(Dataset([inline(0, "double_sequence", word)]).write(tmp_path, "a"))
    attrs = f'<instance_attributes><double_attribute name="d">{word}</double_attribute>'
    attrs += "</instance_attributes>"
    header = Dataset([Chan("x", extra=attrs)]).write(tmp_path, "b")
    assert read_tdm(header).group("G").channel("x").properties["d"] == word

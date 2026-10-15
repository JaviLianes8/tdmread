"""Contracts from the second independent review: promises no other test pinned."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

import tdmread._reader as reader_module
from tdmread import Group, TdmError, _tdx, read_tdm


def _patch(header: Path, old: str, new: str) -> Path:
    text = header.read_text(encoding="utf-8")
    assert text.count(old) == 1
    header.write_text(text.replace(old, new), encoding="utf-8")
    return header


def test_a_name_the_system_finds_too_long_is_a_tdm_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Guards against ENAMETOOLONG dropped from the names mapped to TdmError.
    def too_long(path: object, mode: str) -> None:
        raise OSError(errno.ENAMETOOLONG, "File name too long")

    monkeypatch.setattr(_tdx, "open", too_long, raising=False)
    header = Dataset(
        [stored(0, "short_sequence", "b")], blocks=block("b", 0, 1, "eInt16Usi"), tdx=b"\x01\x00"
    ).write(tmp_path)
    with pytest.raises(TdmError, match=r"cannot open the .tdx"):
        read_tdm(header)


def test_a_quote_of_exactly_forty_characters_is_not_cut() -> None:
    # Guards against the quote cut at 40 characters instead of above 40.
    with pytest.raises(TdmError) as caught:
        Group("G", ()).channel("x" * 38)
    assert "'" + "x" * 38 + "'" in str(caught.value)


def test_exponents_have_at_most_six_digits(tmp_path: Path) -> None:
    # Guards against GUIDE promises exponents of at most 6 digits.
    ok = Dataset([inline(0, "double_sequence", "1e100000 1e-999999")]).write(tmp_path)
    assert read_tdm(ok).group("G").channel("ch0").data == (float("inf"), 0.0)
    bad = Dataset([inline(0, "double_sequence", "1e1000000")]).write(tmp_path, "bad")
    with pytest.raises(TdmError, match="invalid floating-point value"):
        read_tdm(bad)


def test_the_first_of_two_name_children_is_read(tmp_path: Path) -> None:
    # Guards against child() returning the last matching element.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    _patch(header, "<name>ch0</name>", "<name>ch0</name><name>other</name>")
    assert read_tdm(header).group("G").channel_names == ("ch0",)


def test_a_forty_digit_offset_is_parsed_and_forty_one_digits_are_too_large(
    tmp_path: Path,
) -> None:
    # Guards against the digit limit made exclusive.
    chan = stored(0, "double_sequence", "b")
    forty = Dataset([chan], blocks=block("b", 10**39, 1, "eFloat64Usi"), tdx=b"").write(tmp_path)
    with pytest.raises(TdmError, match="reaches byte"):
        read_tdm(forty)
    big = Dataset([chan], blocks=block("b", 10**40, 1, "eFloat64Usi"), tdx=b"")
    with pytest.raises(TdmError, match="too large"):
        read_tdm(big.write(tmp_path, "big"))


def test_properties_without_a_name_are_ignored_and_strings_keep_only_s_parts(
    tmp_path: Path,
) -> None:
    # Guards against an unnamed property kept under None; and non-<s> children read as parts.
    extra = (
        "<instance_attributes><string_attribute><s>x</s></string_attribute>"
        '<string_attribute name="k"><t>junk</t><s>v</s></string_attribute>'
        "</instance_attributes>"
    )
    chan = Chan(
        "c",
        column='<values>#xpointer(id("s0"))</values>',
        sequence='<double_sequence id="s0"><values>1</values></double_sequence>',
        extra=extra,
    )
    channel = read_tdm(Dataset([chan]).write(tmp_path)).group("G").channel("c")
    assert dict(channel.properties) == {"k": "v"}


def test_an_entity_declaration_alone_is_refused_as_a_dtd(tmp_path: Path) -> None:
    # Guards against only <!DOCTYPE checked (the bare declaration then fails as malformed XML).
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    _patch(header, "<usi:data>", '<!ENTITY e "x"><usi:data>')
    with pytest.raises(TdmError, match="declares a DTD"):
        read_tdm(header)


def test_the_first_tdm_root_is_the_dataset(tmp_path: Path) -> None:
    # Guards against the last tdm_root element winning.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    _patch(header, "</tdm_root>", '</tdm_root><tdm_root id="r2"><name>second</name></tdm_root>')
    dataset = read_tdm(header)
    assert dataset.metadata.name == "data" and dataset.group_names == ("G",)


def test_a_dangling_group_reference_is_skipped(tmp_path: Path) -> None:
    # Guards against a missing group read as an empty unnamed group.
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    _patch(header, '#xpointer(id("g"))', '#xpointer(id("g") id("nope"))')
    assert read_tdm(header).group_names == ("G",)


def test_an_empty_block_keeps_its_value_type(tmp_path: Path) -> None:
    # Guards against a zero-length block returning an empty value type.
    header = Dataset(
        [stored(0, "short_sequence", "b")], blocks=block("b", 0, 0, "eInt16Usi"), tdx=b""
    ).write(tmp_path)
    channel = read_tdm(header).group("G").channel("ch0")
    assert channel.data == () and channel.value_type == "eInt16Usi"


def test_stored_values_are_charged_exactly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Guards against each stored block charged one value short.
    monkeypatch.setattr(reader_module, "GENERATED_ALLOWANCE", 0)
    tdx = b"\x01\x02\x03\x04"
    fits = Dataset([stored(0, "byte_sequence", "a")], blocks=block("a", 0, 4, "eUInt8Usi"), tdx=tdx)
    assert read_tdm(fits.write(tmp_path)).group("G").channel("ch0").data == (1, 2, 3, 4)
    over = Dataset(
        [stored(0, "byte_sequence", "a"), stored(1, "byte_sequence", "b")],
        blocks=block("a", 0, 4, "eUInt8Usi") + block("b", 0, 1, "eUInt8Usi"),
        tdx=tdx,
    )
    with pytest.raises(TdmError, match="limit for this file"):
        read_tdm(over.write(tmp_path, "over"))

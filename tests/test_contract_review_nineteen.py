"""Contracts from the nineteenth independent review: exact spellings, classes and escapes."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, read_tdm
from tdmread._cli import main


def _values(tmp_path: Path, sequence: str, text: str) -> tuple[object, ...]:
    header = Dataset([inline(0, sequence, text)]).write(tmp_path)
    return read_tdm(header).group("G").channel("ch0").data


def _plain(header: Path, match: str, tdx_path: str | None = None) -> None:
    with pytest.raises(TdmError, match=match) as exc:
        read_tdm(header, tdx_path)
    assert type(exc.value) is TdmError


def _root_props(tmp_path: Path, attrs: str) -> dict[str, object]:
    extra = f"<instance_attributes>{attrs}</instance_attributes>"
    header = Dataset([inline(0, "double_sequence", "1")], root_extra=extra).write(tmp_path)
    return dict(read_tdm(header).properties)


def test_a_lone_dot_is_not_a_float(tmp_path: Path) -> None:
    with pytest.raises(TdmError, match="invalid floating-point value"):
        _values(tmp_path, "double_sequence", ".")
    extra = "<minimum>.</minimum>"
    chan = Chan("ch0", extra=extra)
    header = Dataset([chan]).write(tmp_path, "m")
    assert read_tdm(header).group("G").channel("ch0").minimum is None


@pytest.mark.parametrize(
    "text", ["26-10-14T00:00:00", "2026-10-14T00:00:00,5", "2026-10-14 00:00:00"]
)
def test_header_times_are_read_only_in_the_exact_form(tmp_path: Path, text: str) -> None:
    with pytest.raises(TdmError, match="invalid time"):
        _values(tmp_path, "time_sequence", text)
    assert _root_props(tmp_path, f'<time_attribute name="t">{text}</time_attribute>') == {"t": text}


def test_an_impossible_header_date_is_a_plain_tdm_error(tmp_path: Path) -> None:
    header = Dataset([inline(0, "time_sequence", "2026-02-30T00:00:00")]).write(tmp_path)
    _plain(header, "invalid time")


def test_property_numbers_are_stripped_of_any_whitespace(tmp_path: Path) -> None:
    props = _root_props(
        tmp_path,
        '<long_attribute name="n">\n\t5\n</long_attribute>'
        '<double_attribute name="d">NaN</double_attribute>'
        f'<double_attribute name="w">{"1" * 401}</double_attribute>',
    )
    assert props["n"] == 5
    assert isinstance(props["d"], float) and math.isnan(props["d"])
    assert props["w"] == "1" * 401


def test_a_401_character_minimum_is_not_a_number(tmp_path: Path) -> None:
    chan = Chan("ch0", extra=f"<minimum>{'1' * 401}</minimum><maximum>{'1' * 400}</maximum>")
    channel = read_tdm(Dataset([chan]).write(tmp_path)).group("G").channel("ch0")
    assert channel.minimum is None
    assert channel.maximum == float("1" * 400)


def test_a_one_row_constant_keeps_the_sign_of_zero(tmp_path: Path) -> None:
    column = (
        "<sequence_representation>implicit_constant</sequence_representation>"
        "<generation_parameters>-0.0</generation_parameters>"
    )
    header = Dataset([Chan("ch0", column=column, rows=1)]).write(tmp_path)
    (value,) = read_tdm(header).group("G").channel("ch0").data
    assert isinstance(value, float)
    assert value == 0.0 and math.copysign(1.0, value) == -1.0


def test_a_row_count_with_two_signs_is_refused(tmp_path: Path) -> None:
    column = (
        "<sequence_representation>implicit_linear</sequence_representation>"
        "<generation_parameters>0 1</generation_parameters>"
    )
    extra = (
        '<instance_attributes><long_attribute name="NI_ChannelLength">++3'
        "</long_attribute></instance_attributes>"
    )
    header = Dataset([Chan("ch0", column=column, extra=extra)]).write(tmp_path)
    _plain(header, "row count is not an integer")


def test_a_missing_block_and_a_bad_tdx_path_are_plain_tdm_errors(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "nope")], block("b0", 0, 1, "eFloat64Usi"))
    dataset.tdx = b"\0" * 8
    header = dataset.write(tmp_path)
    _plain(header, "block that does not exist")
    good = Dataset([stored(0, "double_sequence", "b0")], block("b0", 0, 1, "eFloat64Usi"))
    _plain(good.write(tmp_path, "g"), "cannot open", str(tmp_path / "a\0b.tdx"))


def test_the_root_element_name_is_case_sensitive(tmp_path: Path) -> None:
    header = tmp_path / "upper.tdm"
    header.write_text("<TDM/>", encoding="utf-8")
    _plain(header, "not a TDM header")


def test_channel_lookup_is_case_sensitive(tmp_path: Path) -> None:
    group = read_tdm(Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)).group("G")
    assert group.channel("ch0").name == "ch0"
    with pytest.raises(TdmError, match="no channel named 'CH0'"):
        group.channel("CH0")


def test_a_one_character_unprintable_name_is_escaped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dataset = Dataset([inline(0, "double_sequence", "1")])
    dataset.channels[0].name = "&#173;"
    header = dataset.write(tmp_path)
    assert main(["channels", str(header)]) == 0
    assert capsys.readouterr().out == "G\t\\xad\texplicit\t1\n"

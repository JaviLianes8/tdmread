"""Contracts from the eighteenth independent review: spellings, names, exact error classes."""

from __future__ import annotations

import json
import pickle
import struct
from datetime import datetime
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, TdmFileNotFoundError, read_tdm
from tdmread._cli import main


def _values(tmp_path: Path, sequence: str, text: str) -> tuple[object, ...]:
    header = Dataset([inline(0, sequence, text)]).write(tmp_path)
    return read_tdm(header).group("G").channel("ch0").data


def _plain_tdm_error(tmp_path: Path, dataset: Dataset, match: str) -> None:
    with pytest.raises(TdmError, match=match) as exc:
        read_tdm(dataset.write(tmp_path))
    assert type(exc.value) is TdmError


def test_little_endian_time_fraction_is_unsigned(tmp_path: Path) -> None:
    raw = struct.pack("<Qq", 2**63, 3_874_844_079)
    dataset = Dataset([stored(0, "time_sequence", "b0")], block("b0", 0, 1, "eTimeUsi"), raw)
    channel = read_tdm(dataset.write(tmp_path)).group("G").channel("ch0")
    assert channel.data == (datetime(2026, 10, 14, 17, 34, 39, 500000),)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("+1.5", 1.5), ("1.", 1.0), ("1e+2", 100.0), ("+.5e-1", 0.05)],
)
def test_float_spellings_the_guide_accepts(tmp_path: Path, text: str, expected: float) -> None:
    assert _values(tmp_path, "double_sequence", text) == (expected,)


def test_negative_inline_integers_are_read(tmp_path: Path) -> None:
    assert _values(tmp_path, "longlong_sequence", "-7 -0") == (-7, 0)


def test_a_float_of_401_characters_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TdmError, match="invalid floating-point value"):
        _values(tmp_path, "double_sequence", "-" + "1" * 400)
    assert _values(tmp_path, "double_sequence", "-" + "0" * 399) == (-0.0,)


@pytest.mark.parametrize("url", ["da&#9;ta.tdx", "da*ta.tdx"])
def test_tdx_names_with_a_tab_or_a_star_are_refused(tmp_path: Path, url: str) -> None:
    dataset = Dataset([stored(0, "double_sequence", "b0")], block("b0", 0, 1, "eFloat64Usi"))
    dataset.url = url
    _plain_tdm_error(tmp_path, dataset, "not a valid file name")


def test_a_tdx_that_is_a_folder_is_a_plain_tdm_error(tmp_path: Path) -> None:
    (tmp_path / "data.tdx").mkdir()
    dataset = Dataset([stored(0, "double_sequence", "b0")], block("b0", 0, 1, "eFloat64Usi"))
    with pytest.raises(TdmError, match="is a folder") as exc:
        read_tdm(dataset.write(tmp_path))
    assert not isinstance(exc.value, FileNotFoundError)
    assert not isinstance(exc.value, TdmFileNotFoundError)


def test_a_header_that_names_no_tdx_is_refused_not_guessed(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "b0")], block("b0", 0, 1, "eFloat64Usi"))
    dataset.url = ""
    header = dataset.write(tmp_path, stem="other")
    (tmp_path / "other.tdx").write_bytes(b"\0" * 8)
    _plain_tdm_error_path(header, "does not name its .tdx")


def _plain_tdm_error_path(header: Path, match: str) -> None:
    with pytest.raises(TdmError, match=match) as exc:
        read_tdm(header)
    assert type(exc.value) is TdmError


def test_properties_unpickle_as_the_read_only_mapping(tmp_path: Path) -> None:
    extra = '<instance_attributes><long_attribute name="n">5</long_attribute></instance_attributes>'
    header = Dataset([inline(0, "double_sequence", "1")], root_extra=extra).write(tmp_path)
    props = read_tdm(header).properties
    back = pickle.loads(pickle.dumps(props))
    assert type(back) is type(props)
    assert back == {"n": 5}
    assert hash(back) == hash(props)
    with pytest.raises(TypeError):
        back["n"] = 6  # type: ignore[index]


def test_malformed_datasets_raise_plain_tdm_error(tmp_path: Path) -> None:
    missing = Chan("ch0", column='<values>#xpointer(id("nowhere"))</values>')
    _plain_tdm_error(tmp_path / "a", _mk(tmp_path / "a", Dataset([missing])), "does not exist")
    negative = Chan(
        "ch0",
        column="<sequence_representation>implicit_linear"
        "</sequence_representation><generation_parameters>0 1"
        "</generation_parameters>",
        rows=-2,
    )
    _plain_tdm_error(tmp_path / "b", _mk(tmp_path / "b", Dataset([negative])), "negative row count")
    raw = struct.pack("<Qq", 0, 10**12)
    late = Dataset([stored(0, "time_sequence", "b0")], block("b0", 0, 1, "eTimeUsi"), raw)
    _plain_tdm_error(tmp_path / "c", _mk(tmp_path / "c", late), "outside the years 1 to 9999")
    count = Dataset(
        [stored(0, "double_sequence", "b0")],
        block("b0", 0, 1, "eFloat64Usi").replace('length="1"', 'length="x1"'),
        b"\0" * 8,
    )
    _plain_tdm_error(tmp_path / "d", _mk(tmp_path / "d", count), "not an integer")


def _mk(folder: Path, dataset: Dataset) -> Dataset:
    folder.mkdir()
    return dataset


def test_a_dtd_is_refused_as_a_plain_tdm_error(tmp_path: Path) -> None:
    header = tmp_path / "dtd.tdm"
    header.write_text('<!DOCTYPE tdm><tdm xmlns="x"/>', encoding="utf-8")
    _plain_tdm_error_path(header, "declares a DTD")


def test_readme_long_options_and_info_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    extra = "<author>lab</author>"
    header = Dataset([inline(0, "double_sequence", "1.5")], root_extra=extra).write(tmp_path)
    args = ["dump", str(header), "--group", "G", "--channel", "ch0", "--format", "json"]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unit"] == ""
    assert payload["data"] == [1.5]
    assert main(["info", str(header)]) == 0
    assert "author: lab\n" in capsys.readouterr().out
    assert main(["channels", str(header)]) == 0
    assert capsys.readouterr().out == "G\tch0\texplicit\t1\n"


def test_json_writes_non_finite_floats_in_lower_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header = Dataset([inline(0, "double_sequence", "INF -INF NaN")]).write(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"] == ["inf", "-inf", "nan"]


def test_strings_keep_their_surrounding_spaces(tmp_path: Path) -> None:
    text = "<s> a </s><s>\tb\t</s>"
    assert _values(tmp_path, "string_sequence", text) == (" a ", "\tb\t")
    extra = '<instance_attributes><string_attribute name="s"><s> x </s></string_attribute>'
    header = Dataset([], root_extra=extra + "</instance_attributes>").write(tmp_path, "p")
    assert read_tdm(header).properties["s"] == " x "

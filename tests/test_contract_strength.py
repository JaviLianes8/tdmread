"""Contracts pinning behaviour an independent mutation round found unguarded (hand-written)."""

from __future__ import annotations

import json
import struct
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, TdmFileNotFoundError, read_tdm
from tdmread._channel import Values
from tdmread._cli import main

GEN = "<sequence_representation>{0}</sequence_representation>"
PARAMS = "<generation_parameters>{0}</generation_parameters>"
VALUES = '<values>#xpointer(id("s0"))</values>'
PROP = '<instance_attributes><{0}_attribute name="p">{1}</{0}_attribute></instance_attributes>'
INTS = ("byte", "ubyte", "short", "ushort", "long", "ulong", "longlong", "ulonglong")


def _one(folder: Path, chan: Chan, blocks: str = "", tdx: bytes | None = None) -> Values:
    return read_tdm(Dataset([chan], blocks, tdx).write(folder)).group("G").channels[0].data


def _patched(folder: Path, data: Dataset, old: str, new: str) -> Path:
    header = data.write(folder)
    text = header.read_text(encoding="utf-8")
    assert text.count(old) == 1
    header.write_text(text.replace(old, new), encoding="utf-8")
    return header


def test_float_tokens_of_exactly_400_characters_are_numbers(tmp_path: Path) -> None:
    token = "0" * 399 + "5"
    chan = inline(0, "double_sequence", token)
    chan.extra = f"<minimum>{token}</minimum>"
    assert _one(tmp_path, chan) == (5.0,)
    assert read_tdm(tmp_path / "data.tdm").group("G").channels[0].minimum == 5.0
    with pytest.raises(TdmError):
        _one(tmp_path, inline(0, "double_sequence", "0" + token))


def test_integers_may_carry_a_plus_sign(tmp_path: Path) -> None:
    chan = inline(0, "long_sequence", "+5 -3")
    chan.extra = PROP.format("long", "+7")
    assert _one(tmp_path, chan) == (5, -3)
    assert read_tdm(tmp_path / "data.tdm").group("G").channels[0].properties["p"] == 7


@pytest.mark.parametrize("kind", INTS)
def test_every_inline_integer_sequence_is_read(tmp_path: Path, kind: str) -> None:
    assert _one(tmp_path, inline(0, f"{kind}_sequence", "7 18446744073709551615")) == (
        7,
        18446744073709551615,
    )


@pytest.mark.parametrize("kind", ("byte", "short", "long", "longlong"))
def test_integer_properties_are_ints(tmp_path: Path, kind: str) -> None:
    chan = inline(0, "double_sequence", "1")
    chan.extra = PROP.format(kind, "-12")
    _one(tmp_path, chan)
    assert read_tdm(tmp_path / "data.tdm").group("G").channels[0].properties["p"] == -12


def test_iso_fractions_are_right_padded(tmp_path: Path) -> None:
    chan = inline(0, "time_sequence", "2026-01-02T03:04:05.5 2026-01-02T03:04:05.123")
    chan.extra = PROP.format("time", "2026-01-02T03:04:05.25")
    t = datetime(2026, 1, 2, 3, 4, 5)
    assert _one(tmp_path, chan) == (t.replace(microsecond=500000), t.replace(microsecond=123000))
    props = read_tdm(tmp_path / "data.tdm").group("G").channels[0].properties
    assert props["p"] == t.replace(microsecond=250000)


def test_tdx_times_at_both_ends_of_the_datetime_range(tmp_path: Path) -> None:
    epoch, second = datetime(1904, 1, 1), timedelta(seconds=1)
    low, high = (datetime.min - epoch) // second, (datetime.max - epoch) // second
    tdx = struct.pack("<QqQq", 0, low, 0, high)
    chan = stored(0, "time_sequence", "b0")
    got = _one(tmp_path, chan, blocks=block("b0", 0, 2, "eTimeUsi"), tdx=tdx)
    assert got == (datetime(1, 1, 1), datetime(9999, 12, 31, 23, 59, 59))
    bad = struct.pack("<Qq", 0, high + 1)
    with pytest.raises(TdmError):
        _one(tmp_path, chan, blocks=block("b0", 0, 1, "eTimeUsi"), tdx=bad)


def test_string_sequences_keep_only_s_children(tmp_path: Path) -> None:
    chan = inline(0, "string_sequence", "<s>a</s><x>b</x><s>c</s>")
    assert _one(tmp_path, chan) == ("a", "c")


def test_an_empty_block_needs_no_tdx_bytes(tmp_path: Path) -> None:
    chan = stored(0, "double_sequence", "b0")
    assert _one(tmp_path, chan, blocks=block("b0", 1000, 0, "eFloat64Usi")) == ()
    assert _one(tmp_path, chan, blocks=block("b0", 1000, 0, "eFloat64Usi"), tdx=b"x") == ()


def test_raw_linear_needs_two_parameters(tmp_path: Path) -> None:
    chan = inline(0, "double_sequence", "1 2")
    chan.column = GEN.format("raw_linear") + PARAMS.format("2") + VALUES
    with pytest.raises(TdmError):
        _one(tmp_path, chan)


@pytest.mark.parametrize(
    "head", [GEN.format("raw_linear") + PARAMS.format("0 1"), GEN.format("implicit_constant")]
)
def test_scaled_or_generated_channels_refuse_strings(tmp_path: Path, head: str) -> None:
    chan = inline(0, "string_sequence", "<s>a</s>")
    chan.column = head + VALUES
    chan.rows = 2
    with pytest.raises(TdmError):
        _one(tmp_path, chan)


def _constant(rows: int) -> Chan:
    column = GEN.format("implicit_constant") + PARAMS.format("1.5")
    return Chan("k", column=column, rows=rows)


def test_the_generated_allowance_is_inclusive_and_rows_are_not_negative(tmp_path: Path) -> None:
    assert len(_one(tmp_path, _constant(10_000_000))) == 10_000_000
    for rows in (10_000_001, -1):
        with pytest.raises(TdmError):
            _one(tmp_path, _constant(rows))


def test_huge_counts_give_short_messages(tmp_path: Path) -> None:
    with pytest.raises(TdmError) as rows:
        _one(tmp_path, _constant(int("9" * 1000)))
    chan = stored(0, "double_sequence", "b0")
    with pytest.raises(TdmError) as offset:
        _one(tmp_path, chan, blocks=block("b0", int("9" * 1000), 1, "eFloat64Usi"), tdx=b"")
    assert len(str(rows.value)) < 200 and len(str(offset.value)) < 200


def test_child_lookup_matches_whole_names(tmp_path: Path) -> None:
    data = Dataset([inline(0, "double_sequence", "1")])
    old = '<tdm_channel id="c0"><name>'
    new = old.replace("<name>", "<display_name>no</display_name><name>")
    header = _patched(tmp_path, data, old, new)
    assert read_tdm(header).group("G").channel_names == ("ch0",)


def test_the_first_of_several_references_is_followed(tmp_path: Path) -> None:
    data = Dataset([inline(0, "double_sequence", "1"), inline(1, "double_sequence", "2")])
    old = '<local_columns>#xpointer(id("l0"))'
    header = _patched(tmp_path, data, old, '<local_columns>#xpointer(id("l0") id("l1"))')
    assert read_tdm(header).group("G").channels[0].data == (1.0,)


def test_the_first_element_with_an_id_wins(tmp_path: Path) -> None:
    chan = inline(0, "double_sequence", "1")
    chan.sequence += '<double_sequence id="s0"><values>2</values></double_sequence>'
    assert _one(tmp_path, chan) == (1.0,)


def test_dangling_channel_references_are_skipped(tmp_path: Path) -> None:
    data = Dataset([inline(0, "double_sequence", "1")])
    header = _patched(tmp_path, data, '#xpointer(id("c0"))', '#xpointer(id("c0") id("ghost"))')
    assert read_tdm(header).group("G").channel_names == ("ch0",)


def test_an_unparsable_minimum_is_none(tmp_path: Path) -> None:
    chan = inline(0, "double_sequence", "1")
    chan.extra = "<minimum>abc</minimum><maximum>2.5</maximum>"
    _one(tmp_path, chan)
    got = read_tdm(tmp_path / "data.tdm").group("G").channels[0]
    assert (got.minimum, got.maximum) == (None, 2.5)


def test_a_missing_header_is_a_builtin_file_not_found(tmp_path: Path) -> None:
    assert issubclass(TdmFileNotFoundError, FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        read_tdm(tmp_path / "nope.tdm")


def test_cli_info_skips_empty_fields(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    header = Dataset([inline(0, "double_sequence", "1")]).write(tmp_path)
    assert main(["info", str(header)]) == 0
    assert capsys.readouterr().out == "name: data\ngroups: 1\n  G (1 channels)\n"


def test_cli_dump_files_are_utf8_lf_with_a_value_header(tmp_path: Path) -> None:
    named = inline(0, "double_sequence", "1 2")
    named.name = "Ü"
    blank = inline(9, "double_sequence", "3")
    blank.name = ""
    header = Dataset([named, blank]).write(tmp_path)
    csv_out, json_out = tmp_path / "o.csv", tmp_path / "o.json"
    assert main(["dump", str(header), "-g", "G", "-c", "Ü", "-o", str(csv_out)]) == 0
    assert csv_out.read_bytes() == "index,Ü\n0,1.0\n1,2.0\n".encode()
    assert main(["dump", str(header), "-g", "G", "-c", "", "-o", str(csv_out)]) == 0
    assert csv_out.read_text(encoding="utf-8").splitlines()[0] == "index,value"
    assert main(["dump", str(header), "-g", "G", "-c", "Ü", "-f", "json", "-o", str(json_out)]) == 0
    written = json_out.read_text(encoding="utf-8")
    assert written.isascii() and json.loads(written)["name"] == "Ü"

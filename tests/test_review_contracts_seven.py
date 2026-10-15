"""Contracts from the second ground-truth round: second boundaries and narrow integers."""

from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

import pytest
from tdm_builder import Dataset, block, inline, stored

from tdmread import TdmError, read_tdm

PROP = '<instance_attributes><{0}_attribute name="p">{1}</{0}_attribute></instance_attributes>'


def test_times_never_round_into_the_next_second(tmp_path: Path) -> None:
    text = (
        "2026-10-14T23:59:59.9999999996 2026-12-31T23:59:59.99999999951 "
        "2026-10-14T12:00:00.0000009995 9999-12-31T23:59:59.9999999999"
    )
    channel = inline(0, "time_sequence", text)
    channel.extra = PROP.format("time", "2026-10-14T23:59:59.9999999996")
    group = read_tdm(Dataset([channel]).write(tmp_path)).groups[0]
    assert group.channels[0].data == (
        datetime(2026, 10, 14, 23, 59, 59, 999999),
        datetime(2026, 12, 31, 23, 59, 59, 999999),
        datetime(2026, 10, 14, 12, 0),
        datetime(9999, 12, 31, 23, 59, 59, 999999),
    )
    assert group.channels[0].properties["p"] == datetime(2026, 10, 14, 23, 59, 59, 999999)


def test_tdx_fractions_near_a_whole_second_stay_in_it(tmp_path: Path) -> None:
    raw = struct.pack("<Qq", 2**64 - 1, 40) + struct.pack("<Qq", 2**64 - 2**30, 40)
    dataset = Dataset([stored(0, "time_sequence", "t")], block("t", 0, 2, "eTimeUsi"), raw)
    data = read_tdm(dataset.write(tmp_path)).groups[0].channels[0].data
    assert data == (datetime(1904, 1, 1, 0, 0, 40, 999999),) * 2


def test_inline_shorts_wrap_and_longs_clamp_as_in_nis_reader(tmp_path: Path) -> None:
    shorts = inline(0, "short_sequence", "32768 -32769 65535")
    shorts.extra = PROP.format("short", "40000")
    longs = inline(1, "long_sequence", "2147483648 -2147483649")
    longs.extra = PROP.format("long", "3000000000")
    group = read_tdm(Dataset([shorts, longs]).write(tmp_path)).groups[0]
    assert group.channels[0].data == (-32768, 32767, -1)
    assert group.channels[1].data == (2147483647, -2147483648)
    assert group.channels[0].properties["p"] == -25536
    assert group.channels[1].properties["p"] == 2147483647


def test_a_string_property_without_parts_is_empty(tmp_path: Path) -> None:
    channel = inline(0, "double_sequence", "1")
    channel.extra = (
        '<instance_attributes><string_attribute name="a"></string_attribute>'
        '<string_attribute name="b">plain</string_attribute></instance_attributes>'
    )
    props = read_tdm(Dataset([channel]).write(tmp_path)).groups[0].channels[0].properties
    assert dict(props) == {"a": "", "b": ""}


@pytest.mark.parametrize("url", ["\\Windows\\win.ini", "\\x.tdx", "/x.tdx"])
def test_a_rooted_tdx_location_is_refused(tmp_path: Path, url: str) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    dataset.url = "data.tdx"
    header = dataset.write(tmp_path)
    header.write_text(header.read_text("utf-8").replace("data.tdx", url), "utf-8")
    with pytest.raises(TdmError, match="outside the header's folder"):
        read_tdm(header)


def test_a_tdx_that_is_a_folder_or_missing_is_named_by_its_url(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    dataset.url = "sub/x.tdx"
    header = dataset.write(tmp_path)
    with pytest.raises(TdmError, match=r"'sub/x\.tdx'"):
        read_tdm(header)
    (tmp_path / "sub" / "x.tdx").mkdir(parents=True)
    with pytest.raises(TdmError, match=r"is a folder|cannot open"):
        read_tdm(header)


def test_a_given_tdx_path_is_named_in_full(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    header = dataset.write(tmp_path)
    missing = tmp_path / "somewhere" / "deeper" / "still" / "my_measurement_data.tdx"
    with pytest.raises(TdmError) as caught:
        read_tdm(header, missing)
    assert str(missing) in str(caught.value)


def test_operating_system_failures_opening_the_tdx_propagate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    header = dataset.write(tmp_path)

    def failing(*args: object, **kwargs: object) -> object:
        raise OSError(errno.EMFILE, "Too many open files")

    monkeypatch.setattr("tdmread._tdx.open", failing, raising=False)
    with pytest.raises(OSError) as caught:
        read_tdm(header)
    assert not isinstance(caught.value, TdmError)

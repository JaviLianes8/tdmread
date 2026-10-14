"""Contracts from the third ground-truth round: NI's header time and integer rules."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from tdm_builder import Dataset, inline

from tdmread import TdmError, read_tdm


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-10-14T12:00:00.7777779995", datetime(2026, 10, 14, 12, 0, 0, 777778)),
        ("2026-10-14T12:00:00.123456999500000001", datetime(2026, 10, 14, 12, 0, 0, 123456)),
        ("2026-10-14T12:00:00.500000999500000001", datetime(2026, 10, 14, 12, 0, 0, 500000)),
        ("2026-10-14T23:59:59.99999999999999995", datetime(2026, 10, 15)),
        ("2026-02-28T23:59:59.99999999999999999999", datetime(2026, 3, 1)),
        ("2026-10-14T23:59:59.9999999996", datetime(2026, 10, 14, 23, 59, 59, 999999)),
    ],
)
def test_header_times_follow_nis_double_conversion(
    tmp_path: Path, text: str, expected: datetime
) -> None:
    channel = read_tdm(Dataset([inline(0, "time_sequence", text)]).write(tmp_path)).groups[0]
    assert channel.channels[0].data == (expected,)


def test_a_header_time_that_rounds_past_year_9999_raises(tmp_path: Path) -> None:
    header = Dataset([inline(0, "time_sequence", "9999-12-31T23:59:59." + "9" * 45)])
    with pytest.raises(TdmError, match="outside the years"):
        read_tdm(header.write(tmp_path))


@pytest.mark.parametrize(
    ("kind", "text", "expected"),
    [
        ("byte", "3000000000 -2147483649 4294967296", (255, 0, 255)),
        ("short", "3000000000 -3000000000 2147483648 18446744073709551621", (-1, 0, -1, -1)),
        ("short", "-9223372036854775809 -2147483649", (0, 0)),
    ],
)
def test_bytes_and_shorts_clamp_to_32_bits_before_narrowing(
    tmp_path: Path, kind: str, text: str, expected: tuple[int, ...]
) -> None:
    header = Dataset([inline(0, f"{kind}_sequence", text)]).write(tmp_path)
    assert read_tdm(header).groups[0].channels[0].data == expected


def test_a_repeated_property_name_takes_its_last_value(tmp_path: Path) -> None:
    channel = inline(0, "double_sequence", "1")
    channel.extra = (
        '<instance_attributes><long_attribute name="n">1</long_attribute>'
        '<long_attribute name="n">2</long_attribute>'
        '<short_attribute name="s">3000000000</short_attribute></instance_attributes>'
    )
    props = read_tdm(Dataset([channel]).write(tmp_path)).groups[0].channels[0].properties
    assert dict(props) == {"n": 2, "s": -1}

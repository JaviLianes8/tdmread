"""The full promise of read_tdm: every value kind, representation, layout and refusal."""

from __future__ import annotations

import os
import struct
from datetime import datetime
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, TdmFileNotFoundError, UnsupportedTdmError, read_tdm

LINEAR = "<sequence_representation>implicit_linear</sequence_representation>"


def _one(folder: Path, dataset: Dataset) -> object:
    return read_tdm(dataset.write(folder)).group("G").channels[0].data


@pytest.mark.parametrize(
    ("value_type", "code", "values"),
    [
        ("eInt8Usi", "B", (0, 127, 128, 255)),
        ("eUInt8Usi", "B", (0, 255)),
        ("eSInt8Usi", "b", (-128, -1, 0, 127)),
        ("eInt16Usi", "h", (-32768, 32767)),
        ("eUInt16Usi", "H", (0, 65535)),
        ("eInt32Usi", "i", (-(2**31), 2**31 - 1)),
        ("eUInt32Usi", "I", (0, 2**32 - 1)),
        ("eInt64Usi", "q", (-(2**63), 2**63 - 1)),
        ("eUInt64Usi", "Q", (0, 2**64 - 1)),
        ("eFloat32Usi", "f", (0.5, -1.25)),
        ("eFloat64Usi", "d", (0.1, -2.5e300)),
    ],
)
@pytest.mark.parametrize("order", ["littleEndian", "bigEndian"])
def test_every_value_type_decodes_in_both_byte_orders(
    tmp_path: Path, value_type: str, code: str, values: tuple[float, ...], order: str
) -> None:
    prefix = "<" if order == "littleEndian" else ">"
    raw = b"\x00" * 3 + struct.pack(f"{prefix}{len(values)}{code}", *values)
    dataset = Dataset(
        [stored(0, "double_sequence", "inc0")],
        block("inc0", 3, len(values), value_type),
        raw,
        order,
    )
    data = _one(tmp_path, dataset)
    assert data == values
    assert all(type(v) is (float if code in "fd" else int) for v in data)


def test_times_are_naive_local_datetimes_cut_to_microseconds(tmp_path: Path) -> None:
    raw = struct.pack("<Qq", 2**64 - 1, 0) + struct.pack("<Qq", 2**63, 60)
    dataset = Dataset([stored(0, "time_sequence", "t")], block("t", 0, 2, "eTimeUsi"), raw)
    assert _one(tmp_path, dataset) == (
        datetime(1904, 1, 1, 0, 0, 0, 999999),
        datetime(1904, 1, 1, 0, 1, 0, 500000),
    )


def test_inline_values_of_every_sequence_kind(tmp_path: Path) -> None:
    channels = [
        inline(0, "byte_sequence", "0 255"),
        inline(1, "long_sequence", " -7\n\t8 "),
        inline(2, "double_sequence", "0.5 -INF nan 1e3"),
        inline(3, "string_sequence", "<s>a</s><s/><s> b </s>"),
        inline(4, "time_sequence", "2026-10-14T12:00:00.1234567 1999-01-02T03:04:05"),
    ]
    group = read_tdm(Dataset(channels).write(tmp_path)).group("G")
    data = [c.data for c in group]
    assert data[0] == (0, 255) and data[1] == (-7, 8)
    assert data[2][:2] == (0.5, float("-inf")) and data[2][3] == 1000.0
    assert data[3] == ("a", "", " b ")
    assert data[4] == (datetime(2026, 10, 14, 12, 0, 0, 123456), datetime(1999, 1, 2, 3, 4, 5))
    assert [c.value_type for c in group] == [""] * 5
    assert [c.representation for c in group] == ["explicit"] * 5


@pytest.mark.parametrize(
    ("column", "rows", "expected"),
    [
        (LINEAR + "<generation_parameters>10 2.5</generation_parameters>", 3, (10.0, 12.5, 15.0)),
        (LINEAR + "<generation_parameters>4</generation_parameters>", 2, (4.0, 4.0)),
        (LINEAR + "<generation_parameters>1 1 9</generation_parameters>", 2, (1.0, 2.0)),
        (
            "<sequence_representation>implicit_constant</sequence_representation>"
            "<generation_parameters>7.5</generation_parameters>",
            3,
            (7.5, 7.5, 7.5),
        ),
        (LINEAR + "<generation_parameters>0 1</generation_parameters>", 0, ()),
    ],
)
def test_generated_channels(tmp_path: Path, column: str, rows: int, expected: object) -> None:
    channel = Chan("x", column=column, rows=rows)
    data = read_tdm(Dataset([channel]).write(tmp_path)).group("G").channel("x")
    assert data.data == expected and data.value_type == ""


def test_raw_linear_scales_stored_values(tmp_path: Path) -> None:
    for representation in ("raw_linear", "raw_linear_external"):
        ch = stored(0, "short_sequence", "inc0")
        ch.column += (
            f"<sequence_representation>{representation}</sequence_representation>"
            "<generation_parameters>3 2</generation_parameters>"
        )
        raw = struct.pack("<3h", 0, 2, -4)
        dataset = Dataset([ch], block("inc0", 0, 3, "eInt16Usi"), raw)
        channel = read_tdm(dataset.write(tmp_path)).group("G").channel("ch0")
        assert channel.data == (3.0, 7.0, -5.0)
        assert (channel.value_type, channel.representation) == ("eInt16Usi", representation)


def test_block_bm_reads_interleaved_values(tmp_path: Path) -> None:
    raw = b"".join(struct.pack("<di", a, b) for a, b in [(1.5, 10), (2.5, 20)])
    blocks = (
        '<block_bm id="a" byteOffset="0" blockOffset="0" blockSize="12" length="2"'
        ' valueType="eFloat64Usi"/><block_bm id="b" byteOffset="4" blockOffset="4"'
        ' blockSize="12" length="2" valueType="eInt32Usi"/>'
    )
    channels = [stored(0, "double_sequence", "a"), stored(1, "long_sequence", "b")]
    group = read_tdm(Dataset(channels, blocks, raw).write(tmp_path)).group("G")
    assert [c.data for c in group] == [(1.5, 2.5), (10, 20)]


def test_values_only_in_the_header_need_no_tdx(tmp_path: Path) -> None:
    dataset = Dataset([inline(0, "double_sequence", "1 2")], url="missing.tdx")
    assert read_tdm(dataset.write(tmp_path)).group("G").channel("ch0").data == (1.0, 2.0)


def test_tdx_path_overrides_the_header(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    header = dataset.write(tmp_path)
    other = tmp_path / "elsewhere.bin"
    other.write_bytes(struct.pack("<d", 4.25))
    assert read_tdm(str(header), os.fspath(other)).group("G").channel("ch0").data == (4.25,)
    with pytest.raises(TdmFileNotFoundError):
        read_tdm(header)


@pytest.mark.parametrize("url", ["../x.tdx", "/etc/x.tdx", "C:/x.tdx", "file:x.tdx", "a/../../x"])
def test_a_tdx_outside_the_header_folder_is_refused(tmp_path: Path, url: str) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eFloat64Usi"))
    dataset.url = "data.tdx"
    header = dataset.write(tmp_path)
    header.write_text(header.read_text().replace('url="data.tdx"', f'url="{url}"'))
    with pytest.raises(TdmError, match="outside"):
        read_tdm(header)


@pytest.mark.parametrize(
    ("column", "error"),
    [
        ("<sequence_representation>implicit_saw</sequence_representation>", UnsupportedTdmError),
        (LINEAR, TdmError),
        (LINEAR + "<generation_parameters>x 1</generation_parameters>", TdmError),
    ],
)
def test_bad_columns_raise(tmp_path: Path, column: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        read_tdm(Dataset([Chan("x", column=column, rows=2)]).write(tmp_path))


def test_a_generated_channel_needs_a_row_count(tmp_path: Path) -> None:
    column = LINEAR + "<generation_parameters>0 1</generation_parameters>"
    with pytest.raises(TdmError, match="row count"):
        read_tdm(Dataset([Chan("x", column=column)]).write(tmp_path))
    extra = '<instance_attributes><long_attribute name="NI_ChannelLength">2'
    extra += "</long_attribute></instance_attributes>"
    dataset = Dataset([Chan("x", column=column, extra=extra)])
    assert read_tdm(dataset.write(tmp_path)).group("G").channel("x").data == (0.0, 1.0)

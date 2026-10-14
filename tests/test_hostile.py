"""Hostile, huge and malformed input: only TdmError (or a missing-file error), fast, short."""

from __future__ import annotations

import random
import struct
import time
from pathlib import Path

import pytest
from tdm_builder import Chan, Dataset, block, inline, stored

from tdmread import TdmError, TdmFileNotFoundError, UnsupportedTdmError, read_tdm

FIXTURES = Path(__file__).parent / "fixtures"
LINEAR = "<sequence_representation>implicit_linear</sequence_representation>"


def _fails(header: Path, error: type[Exception] = TdmError) -> str:
    with pytest.raises(error) as caught:
        read_tdm(header)
    return str(caught.value)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not xml at all",
        "<svg/>",
        "<usi:tdm xmlns:usi='u'><unclosed></usi:tdm>",
        '<?xml version="1.0"?><!DOCTYPE t [<!ENTITY a "x">]><tdm/>',
        "<!DOCTYPE tdm SYSTEM 'http://example.invalid/x.dtd'><tdm/>",
    ],
)
def test_text_that_is_not_a_tdm_header_raises_tdm_error(tmp_path: Path, text: str) -> None:
    header = tmp_path / "x.tdm"
    header.write_text(text, encoding="utf-8")
    assert len(_fails(header)) < 300


def test_a_utf16_dtd_is_refused_too(tmp_path: Path) -> None:
    header = tmp_path / "x.tdm"
    header.write_bytes('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE t><tdm/>'.encode("utf-16"))
    assert "DTD" in _fails(header)


def test_a_folder_is_not_a_header(tmp_path: Path) -> None:
    _fails(tmp_path, TdmFileNotFoundError)


def test_a_huge_generated_channel_is_refused_at_once(tmp_path: Path) -> None:
    column = LINEAR + "<generation_parameters>0 1</generation_parameters>"
    header = Dataset([Chan("x", column=column, rows=10**15)]).write(tmp_path)
    started = time.perf_counter()
    assert "limit" in _fails(header)
    assert time.perf_counter() - started < 1.0


def test_generated_channels_share_one_allowance(tmp_path: Path) -> None:
    column = LINEAR + "<generation_parameters>0 1</generation_parameters>"
    channels = [Chan(f"x{i}", column=column, rows=6_000_000) for i in range(2)]
    assert "limit" in _fails(Dataset(channels).write(tmp_path))


@pytest.mark.parametrize(
    "blocks",
    [
        block("i", 0, 10**18, "eFloat64Usi"),
        block("i", 10**30, 1, "eFloat64Usi"),
        block("i", -1, 1, "eFloat64Usi"),
        block("i", 0, 1, "eFloat64Usi").replace('length="1"', 'length="1' + "0" * 60 + '"'),
        block("i", 0, 1, "eFloat64Usi").replace('length="1"', 'length="' + chr(0x661) + '"'),
        block("i", 0, 1, "e" + "X" * 5000),
        '<block_bm id="i" byteOffset="0" length="2" valueType="eFloat64Usi"/>',
        '<block_bm id="i" byteOffset="0" blockSize="4" length="2" valueType="eFloat64Usi"/>',
        '<block_mr id="i" byteOffset="0" blockSize="8" length="1" valueType="eFloat64Usi"/>',
        block("i", 0, 1, "eStringUsi"),
        "",
    ],
)
def test_bad_blocks_raise_quickly_with_short_messages(tmp_path: Path, blocks: str) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], blocks, b"\x00" * 64)
    started = time.perf_counter()
    assert len(_fails(dataset.write(tmp_path))) < 300
    assert time.perf_counter() - started < 1.0


def test_unsupported_layouts_say_so(tmp_path: Path) -> None:
    dataset = Dataset([stored(0, "double_sequence", "i")], block("i", 0, 1, "eStringUsi"))
    assert "strings stored in the .tdx" in _fails(dataset.write(tmp_path), UnsupportedTdmError)


@pytest.mark.parametrize(
    "seconds", [2**62, -(2**62), 253402300800 + 2082844800, -2082844800 - 62135596801]
)
def test_times_outside_the_datetime_range_raise(tmp_path: Path, seconds: int) -> None:
    raw = struct.pack("<Qq", 0, seconds)
    dataset = Dataset([stored(0, "time_sequence", "t")], block("t", 0, 1, "eTimeUsi"), raw)
    assert "outside" in _fails(dataset.write(tmp_path))


@pytest.mark.parametrize(
    ("sequence", "text"),
    [
        ("double_sequence", "1_000"),
        ("double_sequence", chr(0x661)),
        ("double_sequence", "1" * 500),
        ("long_sequence", "9" * 100),
        ("time_sequence", "2026-02-30T00:00:00"),
        ("time_sequence", "2026-10-14 12:00:00"),
        ("tuple_sequence", "1"),
    ],
)
def test_bad_inline_values_raise(tmp_path: Path, sequence: str, text: str) -> None:
    dataset = Dataset([inline(0, sequence, text)])
    assert len(_fails(dataset.write(tmp_path))) < 300


def test_a_missing_value_sequence_or_block_reference_raises(tmp_path: Path) -> None:
    ch = Chan("x", column='<values>#xpointer(id("nowhere"))</values>')
    assert "does not exist" in _fails(Dataset([ch]).write(tmp_path))
    dataset = Dataset([stored(0, "double_sequence", "nope")], block("i", 0, 1, "eFloat64Usi"))
    assert "does not exist" in _fails(dataset.write(tmp_path))


def test_many_channels_read_in_linear_time(tmp_path: Path) -> None:
    def seconds(count: int) -> float:
        header = Dataset([inline(i, "double_sequence", "1 2 3") for i in range(count)])
        path = header.write(tmp_path, f"n{count}")
        started = time.perf_counter()
        assert len(read_tdm(path).group("G")) == count
        return time.perf_counter() - started

    small, large = seconds(500), seconds(4000)
    assert large < 8 * small * 3 + 0.5


@pytest.mark.parametrize("seed", range(4))
def test_seeded_byte_mutations_of_real_files_raise_only_tdm_errors(seed: int) -> None:
    rng = random.Random(seed)
    sources = sorted((FIXTURES / "labview2026").glob("*.tdm"))
    sources += sorted((FIXTURES / "ni_probes").glob("p0*.tdm"))
    for _ in range(60):
        source = rng.choice(sources)
        header = bytearray(source.read_bytes())
        for _ in range(rng.randint(1, 8)):
            header[rng.randrange(len(header))] = rng.choice(b'<>"/ 0123456789-.ex\x00\xff')
        _read_mutant(source, bytes(header))


def _read_mutant(source: Path, header: bytes) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / source.name
        target.write_bytes(header)
        tdx = source.with_suffix(".tdx")
        if tdx.exists():
            (Path(folder) / tdx.name).write_bytes(tdx.read_bytes())
        started = time.perf_counter()
        try:
            read_tdm(target)
        except TdmError as exc:
            assert len(str(exc)) < 2000
        assert time.perf_counter() - started < 5.0

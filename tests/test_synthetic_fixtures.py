"""End-to-end contract tests against the hand-made TDM/TDX fixtures.

``tests/fixtures/synthetic`` is written by ``scripts/make_synthetic_tdm.py`` from
formulas, so the expected numbers are known exactly: ``A = k`` is ``k * sin(0.05 * i)``,
``F = k`` is ``sin(k * 0.05 * i)``, each 100 samples long, and the implicit file
generates ``0.25 + 0.5 * i``. Those identities are the oracle checked here.
"""

from __future__ import annotations

import math
from pathlib import Path

from tdmread import TdmFile, read_tdm

FIXTURES = Path(__file__).parent / "fixtures" / "synthetic"
LENGTH = 100
STEP = 0.05


def _sine(step: float, scale: float = 1.0) -> list[float]:
    return [scale * math.sin(step * index) for index in range(LENGTH)]


def test_synthetic_tdm_full_promise_end_to_end() -> None:
    dataset = read_tdm(FIXTURES / "Synthetic.tdm")

    assert dataset.metadata.name == "Synthetic.TDM"
    assert dataset.metadata.author == "tdmread test suite"
    assert dataset.group_names == ("Amplitudes", "Frequencies")

    amplitudes = dataset.group("Amplitudes")
    assert amplitudes.channel_names == ("A = 1", "A = 2", "A = 4", "A = 8", "A = 16")

    first = amplitudes.channel("A = 1")
    assert first.value_type == "eFloat64Usi"
    assert first.representation == "explicit"
    assert first.datatype == "DT_DOUBLE"
    assert len(first) == LENGTH
    assert first.minimum == min(first.data)
    assert first.maximum == max(first.data)


def test_channel_values_match_the_sine_oracle() -> None:
    dataset = read_tdm(FIXTURES / "Synthetic.tdm")
    amps = dataset.group("Amplitudes")
    for scale in (1, 2, 4, 8, 16):
        channel = amps.channel(f"A = {scale}")
        assert isinstance(channel.data, tuple)
        assert list(channel.data) == _sine(STEP, scale)
    freqs = dataset.group("Frequencies")
    assert list(freqs.channel("F = 2").data) == _sine(2 * STEP)


def test_big_endian_fixture_decodes_identically_to_little_endian() -> None:
    little = read_tdm(FIXTURES / "Synthetic.tdm")
    big = read_tdm(FIXTURES / "Synthetic-be.tdm")
    for (_, le_channel), (_, be_channel) in zip(little.channels(), big.channels(), strict=True):
        assert le_channel.name == be_channel.name
        assert le_channel.data == be_channel.data


def test_total_channel_count_and_sample_sizes() -> None:
    dataset = read_tdm(FIXTURES / "Synthetic.tdm")
    pairs = list(dataset.channels())
    assert len(pairs) == 10
    assert all(len(channel) == LENGTH for _, channel in pairs)
    assert isinstance(dataset, TdmFile)


def test_implicit_linear_fixture_generates_its_axis() -> None:
    dataset = read_tdm(FIXTURES / "Synthetic_implicit.tdm")
    expected = [0.25 + 0.5 * index for index in range(LENGTH)]
    # A = 1 takes its length from NI_ChannelLength, A = 2 from the submatrix row count.
    for name in ("A = 1", "A = 2"):
        channel = dataset.group("Amplitudes").channel(name)
        assert channel.representation == "implicit_linear"
        assert list(channel.data) == expected


def test_implicit_fixture_still_reads_its_explicit_channels() -> None:
    dataset = read_tdm(FIXTURES / "Synthetic_implicit.tdm")
    explicit = dataset.group("Frequencies").channel("F = 8")
    assert explicit.representation == "explicit"
    assert list(explicit.data) == _sine(8 * STEP)

"""End-to-end contract tests against genuine NI sample files, when they are present.

The ``SineData`` samples are not part of the repository: ``scripts/fetch_upstream.py``
downloads them from the TDMtermite repository into ``tests/upstream`` (URL, revision,
size and sha256 in ``tests/upstream/MANIFEST.json``), and these tests skip until it has
run. ``SineData`` is a known dataset: channel ``A = 1`` is ``sin(0.01 * index)`` sampled
1000 times, amplitude channels scale that sine, and the frequency channels raise the
angular step. Those identities are the independent oracle checked here.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from tdmread import TdmFile, read_tdm

FIXTURES = Path(__file__).parent / "upstream"
pytestmark = pytest.mark.skipif(
    not (FIXTURES / "SineData.tdx").is_file(), reason="run scripts/fetch_upstream.py"
)


def _sine(step: float) -> list[float]:
    return [math.sin(step * index) for index in range(1000)]


def test_real_tdm_full_promise_end_to_end() -> None:
    dataset = read_tdm(FIXTURES / "SineData.tdm")

    assert dataset.metadata.name == "SineData.TDM"
    assert dataset.metadata.author == "National Instruments"
    assert dataset.group_names == ("Amplitudes", "Frequencies")

    amplitudes = dataset.group("Amplitudes")
    assert amplitudes.channel_names == ("A = 1", "A = 2", "A = 4", "A = 8", "A = 16")

    first = amplitudes.channel("A = 1")
    assert first.value_type == "eFloat64Usi"
    assert first.representation == "explicit"
    assert first.datatype == "DT_DOUBLE"
    assert len(first) == 1000
    assert first.minimum is not None and first.maximum is not None
    assert min(first.data) >= first.minimum - 1e-9
    assert max(first.data) <= first.maximum + 1e-9


def test_real_channel_values_match_the_sine_oracle() -> None:
    dataset = read_tdm(FIXTURES / "SineData.tdm")
    amps = dataset.group("Amplitudes")

    base = _sine(0.01)
    for name, scale in (("A = 1", 1.0), ("A = 2", 2.0), ("A = 4", 4.0), ("A = 16", 16.0)):
        channel = amps.channel(name)
        assert isinstance(channel.data, tuple) and len(channel.data) == 1000
        error = max(abs(channel.data[i] - scale * base[i]) for i in range(1000))
        assert error < 1e-9, f"{name} deviates from {scale} * sin(0.01 * i) by {error}"

    freqs = dataset.group("Frequencies")
    error = max(abs(freqs.channel("F = 2").data[i] - math.sin(0.02 * i)) for i in range(1000))
    assert error < 1e-9


def test_big_endian_fixture_decodes_identically_to_little_endian() -> None:
    little = read_tdm(FIXTURES / "SineData.tdm")
    big = read_tdm(FIXTURES / "SineData-be.tdm")
    for (_, le_channel), (_, be_channel) in zip(little.channels(), big.channels(), strict=True):
        assert le_channel.name == be_channel.name
        assert le_channel.data == be_channel.data


def test_total_channel_count_and_sample_sizes() -> None:
    dataset = read_tdm(FIXTURES / "SineData.tdm")
    pairs = list(dataset.channels())
    assert len(pairs) == 10
    assert all(len(channel) == 1000 for _, channel in pairs)
    assert isinstance(dataset, TdmFile)


def test_implicit_linear_fixture_generates_its_axis() -> None:
    dataset = read_tdm(FIXTURES / "SineData_implicit.tdm")
    channel = dataset.group("Amplitudes").channel("A = 1")
    assert channel.representation == "implicit_linear"
    assert len(channel) == 1000
    # generation_parameters "-0.5 1.2" means value[i] = -0.5 + 1.2 * i.
    expected = [-0.5 + 1.2 * index for index in range(1000)]
    assert max(abs(channel.data[i] - expected[i]) for i in range(1000)) < 1e-9


def test_implicit_fixture_still_reads_its_one_explicit_channel() -> None:
    dataset = read_tdm(FIXTURES / "SineData_implicit.tdm")
    explicit = dataset.group("Frequencies").channel("F = 8")
    assert explicit.representation == "explicit"
    assert len(explicit) == 1000

"""tdmread against NI's reading of the hand-made probes in ``tests/fixtures/ni_probes``.

Where NI returns values, tdmread returns the same values, except the documented cases in
``DIVERGES``. Where NI fails or returns nothing, tdmread raises (``RAISES``) or reads the
stored values by their declared type (listed in ``DIVERGES`` with the reason).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import pytest
from ni_oracle import FIXTURES, canon, expected_for, load_view, same_values

from tdmread import TdmError, UnsupportedTdmError, read_tdm

FOLDER = FIXTURES / "ni_probes"
VIEWS = load_view("ni_probes")

RAISES: dict[str, type[Exception]] = {
    "p03_inline_11.tdm": TdmError,  # "1,5" is not a number; NI reads 1
    "p03_inline_13.tdm": TdmError,  # "1.5" is not an integer; NI reads 1
    "p07_g_saw.tdm": UnsupportedTdmError,  # NI fails too
    "p07_h_raw_poly.tdm": UnsupportedTdmError,  # NI fails too
    "p07_i_implicit_alias.tdm": UnsupportedTdmError,  # NI returns nothing
    "p07_k_lin_no_param.tdm": TdmError,  # NI fails too
    "p08_bm_b_8_12.tdm": TdmError,  # past the end of the .tdx; NI returns nothing
    "p08_mr_a.tdm": UnsupportedTdmError,  # NI's two readers disagree on block_mr
    "p09_strext_0.tdm": UnsupportedTdmError,  # NI fails too
    "p09_strext_1.tdm": UnsupportedTdmError,
    "p09_strext_2.tdm": UnsupportedTdmError,
    "p11_past_end.tdm": TdmError,  # NI returns nothing
}
DIVERGES: dict[tuple[str, str], tuple[object, ...]] = {
    # NI refuses a block type that does not fit the sequence type; tdmread decodes the
    # stored values by the block's valueType.
    ("p01_bytes.tdm", "byte_sequence:eSInt8Usi"): (0, 127, -128, -1),
    ("p02_ints.tdm", "short_sequence:eUInt16Usi"): (0, 1, 32768, 65535),
    ("p02_ints.tdm", "long_sequence:eUInt32Usi"): (0, 1, 2**31, 2**32 - 1),
    # tdmread keeps 64-bit integers and 64-bit floats exact where NI converts them.
    ("p02_ints.tdm", "double_sequence:eUInt64Usi"): (0, 1, 2**63, 2**64 - 1),
    ("p02_ints.tdm", "float_sequence:eFloat64Usi"): (0.5, -1.25, 1e300, 0.1),
    # A column without sequence_representation is read as explicit; NI returns nothing.
    ("p07_n_no_repr.tdm", "n_no_repr"): (9.0,) * 5,
    # One inline time: NI's channel reading has it (in UTC), its DataStore pads to 3 rows.
    ("p03_inline_08.tdm", "time_sequence#8"): (datetime(2026, 10, 14, 12, 0),),
    # Without a row count the channel's NI_ChannelLength gives the length; NI returns nothing.
    ("p10_implen_2.tdm", "x"): (0.0, 1.0, 2.0, 3.0, 4.0),
}


def test_the_manifest_matches_every_probe() -> None:
    manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))
    names = {p.name for p in FOLDER.iterdir()} - {"manifest.json"}
    assert set(manifest["files"]) == names
    for name, entry in manifest["files"].items():
        body = (FOLDER / name).read_bytes()
        assert (len(body), hashlib.sha256(body).hexdigest()) == (entry["size"], entry["sha256"])


@pytest.mark.parametrize("name", sorted(RAISES))
def test_probes_nothing_sound_can_be_read_from_raise(name: str) -> None:
    with pytest.raises(RAISES[name]):
        read_tdm(FOLDER / name)


@pytest.mark.parametrize("name", sorted(set(VIEWS) - set(RAISES)))
def test_probes_read_as_nis_reader_reads_them(name: str) -> None:
    dataset = read_tdm(FOLDER / name)
    expected = expected_for(dataset, VIEWS[name])
    for group, channel in dataset.channels():
        diverges = DIVERGES.get((name, channel.name))
        if diverges is not None:
            assert channel.data == diverges
            continue
        assert same_values(channel, expected[(group.name, channel.name)]), channel.name


def test_every_listed_divergence_is_a_real_difference_from_ni() -> None:
    for (name, channel_name), ours in DIVERGES.items():
        recorded = expected_for(read_tdm(FOLDER / name), VIEWS[name])
        assert [canon(v) for v in ours] != recorded[("G", channel_name)]


def test_eint8_is_an_unsigned_byte_and_esint8_a_signed_one() -> None:
    group = read_tdm(FOLDER / "p01_bytes.tdm").group("G")
    assert group.channel("byte_sequence:eInt8Usi").data == (0, 127, 128, 255)
    assert group.channel("short_sequence:eSInt8Usi").data == (0, 127, -128, -1)


def test_times_in_either_byte_order_are_seconds_and_fractions_from_1904() -> None:
    little = read_tdm(FOLDER / "p05_time.tdm").group("G").channel("t").data
    big = read_tdm(FOLDER / "p05_time_be.tdm").group("G").channel("t").data
    first = datetime(2026, 10, 14, 17, 34, 39, 500000)
    assert little == (first, datetime(1904, 1, 1), datetime(1903, 12, 31), datetime(1904, 1, 1))
    assert big == (first, datetime(1904, 1, 1), datetime(1903, 12, 31, 0, 0, 0, 250000))


def test_generated_and_scaled_channels_follow_nis_rules() -> None:
    def data(stem: str) -> tuple[object, ...]:
        return read_tdm(FOLDER / f"p07_{stem}.tdm").group("G").channel(stem).data

    assert data("a_lin_with_values") == (-0.5, 0.7, 1.9, 3.0999999999999996, 4.3)
    assert data("j_lin_one_param") == (5.0, 5.0, 5.0)
    assert data("c_constant") == (7.5, 7.5, 7.5)
    assert data("e_raw_linear_3_2") == (3.0, 7.0, 11.0)
    assert data("f_raw_linear_external") == (3.0, 7.0, 11.0)


def test_block_bm_interleaves_by_block_offset_and_size() -> None:
    group = read_tdm(FOLDER / "p08_bm_c_0_12.tdm").group("G")
    assert group.channel("A").data == (1.5, 2.5, 3.5)
    assert group.channel("B").data == (10, 20, 30)


def test_inline_values_count_is_the_number_written_not_the_row_count() -> None:
    assert read_tdm(FOLDER / "p03_inline_09.tdm").group("G").channel("double_sequence#9").data == (
        1.0,
        2.0,
    )

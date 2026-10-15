"""tdmread against files LabVIEW 2026 wrote on this machine and against NI's own reading.

``tests/fixtures/labview2026`` holds the output of two shipped LabVIEW examples and of
LabVIEW's TDMS-to-TDM converter (``manifest.json`` says how each was made). For every
channel the values tdmread returns must equal the ones NI's reader returned.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pytest
from ni_oracle import FIXTURES, expected_for, load_view, same_values

from tdmread import read_tdm

FOLDER = FIXTURES / "labview2026"
VIEWS = load_view("labview2026")


def test_the_manifest_matches_every_capture() -> None:
    manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))
    names = {p.name for p in FOLDER.iterdir()} - {"manifest.json"}
    assert set(manifest["files"]) == names
    for name, entry in manifest["files"].items():
        body = (FOLDER / name).read_bytes()
        assert (len(body), hashlib.sha256(body).hexdigest()) == (entry["size"], entry["sha256"])


@pytest.mark.parametrize("name", sorted(VIEWS))
def test_every_channel_holds_what_nis_reader_returns(name: str) -> None:
    dataset = read_tdm(FOLDER / name)
    expected = expected_for(dataset, VIEWS[name])
    assert len(expected) == sum(1 for _ in dataset.channels())
    for group, channel in dataset.channels():
        recorded = expected[(group.name, channel.name)]
        assert recorded is not None, (group.name, channel.name)
        assert same_values(channel, recorded), (group.name, channel.name)


def test_the_channel_group_example_reads_whole() -> None:
    dataset = read_tdm(FOLDER / "Example Channel Group File.tdm")
    assert dataset.metadata.name == "Example Channel Groups"
    assert dataset.metadata.title == "Example Description"
    assert dataset.group_names == ("No Noise", "With Noise")
    sine = dataset.group("No Noise").channel("Sine")
    assert (len(sine), sine.value_type, sine.datatype) == (100, "eFloat64Usi", "DT_DOUBLE")
    assert sine.minimum == -0.999866565916045
    assert min(sine.data) == pytest.approx(sine.minimum, abs=1e-12)
    assert sine.properties["wf_increment"] == 0.001
    assert sine.properties["wf_samples"] == 100
    assert sine.properties["wf_xunit_string"] == "s"
    assert sine.properties["wf_start_time"] == datetime(2026, 10, 14, 15, 34, 39, 781104)
    assert dataset.properties == {"wf_create_time": datetime(2026, 10, 14, 15, 34, 39, 781104)}


def test_the_event_example_reads_numbers_integers_and_strings() -> None:
    group = read_tdm(FOLDER / "Example Event File.tdm").group("Untitled")
    assert group.channel_names == ("Data", "Histogram", "Event Time", "Event Type")
    times = group.channel("Event Time")
    assert times.value_type == "eInt32Usi"
    assert times.data == (8, 15, 27, 44, 52, 60, 88, 91)
    assert all(type(value) is int for value in times.data)
    kinds = group.channel("Event Type")
    assert (kinds.datatype, kinds.value_type, len(kinds)) == ("DT_STRING", "", 8)
    assert kinds.data[:2] == ("Random Event 4", "Random Event 3")
    assert group.channel("Histogram").properties["wf_start_offset"] == -2.7


def test_converted_types_hold_the_values_written_into_the_source() -> None:
    # gt_types_0 was converted by LabVIEW from a TDMS file whose values are chosen in
    # scripts/make_tdms_source.py; NI stores some types wider, never with other values.
    dataset = read_tdm(FOLDER / "gt_types_0.tdm")
    ints = dataset.group("Ints")
    assert ints.channel("i8").data == (0, 1, -1, 127, -128, 42)
    assert ints.channel("u8").value_type == "eInt8Usi"
    assert ints.channel("u8").data == (0, 1, 255, 128, 42)
    assert ints.channel("i32").data == (0, -1, 2147483647, -2147483648, 123456)
    assert ints.channel("u32").data == (0.0, 4294967295.0, 2147483648.0, 7.0)
    floats = dataset.group("Floats")
    f64 = floats.channel("f64").numbers()
    assert f64[:6] == (0.0, -0.0, 0.1, -1e308, 5e-324, 1.7976931348623157e308)
    assert math.copysign(1.0, f64[1]) == -1.0
    assert f64[6:9] == (math.inf, -math.inf, f64[8]) and math.isnan(f64[8])
    assert floats.channel("f32").data[9] == 0.10000000149011612
    assert floats.channel("empty").data == ()
    text = dataset.group("Text").channel("strings").data
    assert text[:5] == ("plain", "", "with space ", " lead", 'x<y & z>"q"\'')
    assert text[6:] == ("tab\there", "line\nbreak", "ééé")
    wave = dataset.group("Wave")
    sine = wave.channel("sine").numbers()
    assert all(abs(sine[i] - math.sin(i * 0.01)) < 1e-15 for i in range(1000))
    assert wave.channel("ramp").data == tuple(range(1000))
    assert wave.channel("sine").properties["flag"] == 1
    assert dataset.properties["prop_i32"] == -7
    assert dataset.properties["prop_str"] == "root text"


def test_converted_times_are_the_local_wall_clock_nis_reader_shows() -> None:
    stamps = read_tdm(FOLDER / "gt_types_0.tdm").group("Time").channel("stamps")
    assert stamps.value_type == "eTimeUsi"
    assert stamps.data[0] == datetime(2026, 10, 14, 17, 34, 39, 500000)
    assert stamps.data[3] == datetime(1970, 1, 1, 1, 0)


def test_files_are_read_from_any_working_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).parent)
    relative = Path("fixtures") / "labview2026" / "Example Event File.tdm"
    assert len(read_tdm(relative).group("Untitled").channel("Data")) == 10000

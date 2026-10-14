"""The promise of the result types: Channel, Group, FileMetadata, TdmFile and properties."""

from __future__ import annotations

import builtins
import copy
import pickle
from datetime import datetime
from pathlib import Path

import pytest
from tdm_builder import Dataset, inline

from tdmread import Channel, FileMetadata, Group, TdmError, TdmFile, read_tdm

PROPS = (
    "<instance_attributes>"
    '<string_attribute name="s"><s>text</s></string_attribute>'
    '<string_attribute name="two"><s>a</s><s>b</s></string_attribute>'
    '<long_attribute name="n">-7</long_attribute>'
    '<short_attribute name="bad">x</short_attribute>'
    '<double_attribute name="d">2.5</double_attribute>'
    '<float_attribute name="inf">INF</float_attribute>'
    '<double_attribute name="weird">1_0</double_attribute>'
    '<time_attribute name="t">2026-10-14T15:34:39.781104564666748046875</time_attribute>'
    '<time_attribute name="badtime">yesterday</time_attribute>'
    '<byte_attribute name="flag">1</byte_attribute>'
    '<long_attribute name="n">99</long_attribute>'
    '<odd_attribute name="o"> raw </odd_attribute>'
    "</instance_attributes>"
)
EXPECTED = {
    "s": "text",
    "two": "a",
    "bad": "x",
    "d": 2.5,
    "inf": float("inf"),
    "weird": "1_0",
    "t": datetime(2026, 10, 14, 15, 34, 39, 781104),
    "badtime": "yesterday",
    "flag": 1,
    "n": 99,
    "o": "raw",
}


def _dataset(tmp_path: Path) -> TdmFile:
    channel = inline(0, "double_sequence", "1 2")
    channel.extra = PROPS
    data = Dataset([channel], root_extra=PROPS, group_extra=PROPS)
    return read_tdm(data.write(tmp_path))


def test_properties_are_typed_at_every_level_and_the_last_name_wins(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    group = dataset.group("G")
    for props in (dataset.properties, group.properties, group.channel("ch0").properties):
        assert dict(props) == EXPECTED
        assert list(props) == list(EXPECTED)


def test_properties_are_read_only_hashable_and_picklable(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    props = dataset.properties
    with pytest.raises(TypeError):
        props["s"] = "changed"  # type: ignore[index]
    assert hash(props) == hash(copy.deepcopy(props))
    assert pickle.loads(pickle.dumps(dataset)) == dataset
    assert hash(dataset) == hash(pickle.loads(pickle.dumps(dataset)))
    assert "s" in repr(props) and len(props) == len(EXPECTED)


def test_a_channel_promises_its_fields_length_and_lists() -> None:
    channel = Channel("U", "V", "d", "eFloat64Usi", (1.0, 2.0), "explicit", 1.0, 2.0, "DT_DOUBLE")
    assert (channel.name, channel.unit, channel.description) == ("U", "V", "d")
    assert (channel.minimum, channel.maximum, channel.datatype) == (1.0, 2.0, "DT_DOUBLE")
    assert len(channel) == 2 and channel.to_list() == [1.0, 2.0]
    assert channel.to_list() is not channel.to_list()
    assert dict(channel.properties) == {}
    with pytest.raises(AttributeError):
        channel.name = "other"  # type: ignore[misc]


def test_typed_accessors_return_the_data_or_refuse_another_kind() -> None:
    numbers = Channel("n", "", "", "", (1, 2.5))
    texts = Channel("s", "", "", "", ("a",))
    times = Channel("t", "", "", "", (datetime(2000, 1, 1),))
    empty = Channel("e", "", "", "", ())
    assert numbers.numbers() == (1, 2.5) and texts.strings() == ("a",)
    assert times.times() == (datetime(2000, 1, 1),)
    assert empty.numbers() == () and empty.strings() == () and empty.times() == ()
    for wrong in (numbers.strings, numbers.times, texts.numbers, times.numbers):
        with pytest.raises(TdmError, match="values, not"):
            wrong()
    with pytest.raises(TdmError):
        Channel("b", "", "", "", (True,)).numbers()


@pytest.mark.parametrize("error", [ModuleNotFoundError, ImportError])
def test_to_numpy_without_a_working_numpy_explains_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, error: type[ImportError]
) -> None:
    real_import = builtins.__import__

    def no_numpy(name: str, *args: object, **kwargs: object) -> object:
        if name == "numpy":
            raise error("numpy cannot be loaded here")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_numpy)
    with pytest.raises(TdmError, match="pip install numpy"):
        Channel("n", "", "", "", (1.0,)).to_numpy()


def test_to_numpy_returns_an_array_when_numpy_is_installed() -> None:
    np = pytest.importorskip("numpy")
    array = Channel("n", "", "", "", (1.0, 2.0)).to_numpy()
    assert isinstance(array, np.ndarray) and array.tolist() == [1.0, 2.0]


def test_group_and_dataset_lookups_iteration_and_errors() -> None:
    first, second = Channel("a", "", "", "", (1,)), Channel("a", "", "", "", (2,))
    group = Group("G", (first, second), "desc")
    dataset = TdmFile((group, Group("G", ())), FileMetadata(name="n"))
    assert group.channel("a") is first and dataset.group("G") is group
    assert list(group) == [first, second] and len(group) == 2
    assert list(dataset) == list(dataset.groups) and len(dataset) == 2
    assert group.channel_names == ("a", "a") and dataset.group_names == ("G", "G")
    assert [c.data for _, c in dataset.channels()] == [(1,), (2,)]
    with pytest.raises(TdmError, match="no channel named 'b' in group 'G'"):
        group.channel("b")
    with pytest.raises(TdmError, match="no group named 'H'"):
        dataset.group("H")
    assert TdmFile(()).metadata == FileMetadata()
    assert FileMetadata().datetime == "" and group.description == "desc"


def test_lookup_messages_cut_long_names() -> None:
    with pytest.raises(TdmError) as caught:
        TdmFile(()).group("x" * 10_000)
    assert len(str(caught.value)) < 80

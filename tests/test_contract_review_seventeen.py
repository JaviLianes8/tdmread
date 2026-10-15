"""Contracts from the seventeenth independent review: output shape, bounded messages, types."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from tdm_builder import Dataset, inline

from tdmread import Channel, Group, TdmError, TdmFile, read_tdm, supported_value_types
from tdmread._cli import main


def _header(tmp_path: Path) -> Path:
    return Dataset([inline(0, "double_sequence", "1.5 2.5")]).write(tmp_path)


def test_dump_json_is_indented_by_two_spaces_and_ends_in_a_newline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header = _header(tmp_path)
    assert main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "json"]) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["data"] == [1.5, 2.5]
    assert out == json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    assert out.splitlines()[1] == '  "name": "ch0",'


def test_dump_refuses_an_unknown_format_as_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    header = _header(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["dump", str(header), "-g", "G", "-c", "ch0", "-f", "txt"])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid choice: 'txt'" in captured.err


def test_lookup_and_accessor_messages_bound_the_quoted_names() -> None:
    long_name = "N" * 1000
    group = Group(long_name, (Channel(long_name, "", "", "", ("a",)),))
    failures: list[Callable[[], object]] = [
        lambda: group.channel("missing"),
        lambda: TdmFile((group,)).group(long_name + "x"),
        lambda: group.channel(long_name).numbers(),
        lambda: group.channel(long_name).times(),
    ]
    for fail in failures:
        with pytest.raises(TdmError) as exc:
            fail()
        message = str(exc.value)
        assert "N" * 40 not in message
        assert len(message) < 120


def test_typed_accessor_messages_name_the_wanted_kind() -> None:
    text = Channel("s", "", "", "", ("a",))
    with pytest.raises(TdmError) as exc:
        text.numbers()
    assert str(exc.value) == "channel 's' holds str values, not numbers"
    number = Channel("n", "", "", "eInt32Usi", (1,))
    with pytest.raises(TdmError) as exc:
        number.times()
    assert str(exc.value) == "channel 'n' holds int values, not times"


def test_a_missing_header_message_shows_the_callers_path_in_full(tmp_path: Path) -> None:
    missing = tmp_path / "sub" / "missing.tdm"
    with pytest.raises(TdmError) as exc:
        read_tdm(missing)
    assert str(exc.value) == f"TDM header not found: {missing}"


def test_supported_value_types_is_an_immutable_frozenset() -> None:
    types = supported_value_types()
    assert type(types) is frozenset
    assert "eStringUsi" not in types
    assert len(types) == 12

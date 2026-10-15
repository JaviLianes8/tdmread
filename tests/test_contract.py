import importlib.resources

import tdmread

# The public API. Add every exported name here as the library grows; this list is the
# contract and the test below fails if the module and this list disagree.
PUBLIC_API: list[str] = [
    "Channel",
    "FileMetadata",
    "Group",
    "TdmError",
    "TdmFile",
    "TdmFileNotFoundError",
    "UnsupportedTdmError",
    "read_tdm",
    "supported_value_types",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(tdmread.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in tdmread.__all__:
        assert hasattr(tdmread, name)


def test_version_is_a_three_part_string() -> None:
    parts = tdmread.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("tdmread").joinpath("py.typed").is_file()


def test_the_package_has_no_runtime_dependencies_and_is_stable() -> None:
    from pathlib import Path

    import pytest

    tomllib = pytest.importorskip("tomllib")  # Python 3.11 and later
    project = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text("utf-8"))
    meta = project["project"]
    assert meta["dependencies"] == []
    assert meta["version"] == tdmread.__version__ == "1.0.0"
    assert "Development Status :: 5 - Production/Stable" in meta["classifiers"]
    assert set(meta["urls"]) >= {"Homepage", "Source", "Issues", "Changelog"}

"""Contracts from the tenth independent review: the documented defaults of the public types."""

from __future__ import annotations

from tdmread import Channel, FileMetadata, Group, TdmFile


def test_a_channel_built_with_only_its_required_fields_has_empty_defaults() -> None:
    channel = Channel("U", "V", "", "eFloat64Usi", (1.0,))
    assert channel.representation == ""
    assert channel.minimum is None
    assert channel.maximum is None
    assert channel.datatype == ""
    assert dict(channel.properties) == {}


def test_file_metadata_defaults_to_empty_text_in_every_field() -> None:
    meta = FileMetadata()
    assert (meta.name, meta.title, meta.description, meta.author, meta.datetime) == (
        "",
        "",
        "",
        "",
        "",
    )
    assert FileMetadata(name="run").title == ""


def test_group_and_dataset_defaults_are_empty() -> None:
    group = Group("G", ())
    assert group.description == ""
    assert dict(group.properties) == {}
    dataset = TdmFile((group,))
    assert dataset.metadata == FileMetadata()
    assert dict(dataset.properties) == {}

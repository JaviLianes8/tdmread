"""Build small hand-written TDM datasets for the tests (our own text, not NI output)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chan:
    """One channel: its localcolumn body, an optional value sequence and extras."""

    name: str
    column: str = ""
    sequence: str = ""
    rows: int | None = None
    extra: str = ""


@dataclass
class Dataset:
    """A dataset with one group ``G``; `blocks` is the body of the ``file`` element."""

    channels: list[Chan] = field(default_factory=list)
    blocks: str = ""
    tdx: bytes | None = None
    byte_order: str = "littleEndian"
    url: str = "data.tdx"
    root_extra: str = ""
    group_extra: str = ""

    def write(self, folder: Path, stem: str = "data") -> Path:
        parts = []
        for i, ch in enumerate(self.channels):
            rows = f"<number_of_rows>{ch.rows}</number_of_rows>" if ch.rows is not None else ""
            parts.append(
                f'<tdm_channel id="c{i}"><name>{ch.name}</name>{ch.extra}'
                f'<local_columns>#xpointer(id("l{i}"))</local_columns></tdm_channel>'
                f'<submatrix id="m{i}">{rows}</submatrix>'
                f'<localcolumn id="l{i}"><submatrix>#xpointer(id("m{i}"))</submatrix>'
                f"{ch.column}</localcolumn>{ch.sequence}"
            )
        refs = " ".join(f'id("c{i}")' for i in range(len(self.channels)))
        include = (
            f'<usi:include><file byteOrder="{self.byte_order}" url="{self.url}">'
            f"{self.blocks}</file></usi:include>"
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<usi:tdm xmlns:usi="http://www.ni.com/Schemas/USI/1_0" version="1.0">'
            f"{include}<usi:data>"
            f'<tdm_root id="r"><name>{stem}</name>{self.root_extra}'
            '<channelgroups>#xpointer(id("g"))</channelgroups></tdm_root>'
            f'<tdm_channelgroup id="g"><name>G</name>{self.group_extra}'
            f"<channels>#xpointer({refs})</channels></tdm_channelgroup>"
            + "".join(parts)
            + "</usi:data></usi:tdm>"
        )
        header = folder / f"{stem}.tdm"
        header.write_text(xml, encoding="utf-8")
        if self.tdx is not None:
            (folder / self.url).parent.mkdir(parents=True, exist_ok=True)
            (folder / self.url).write_bytes(self.tdx)
        return header


def stored(index: int, sequence: str, external: str) -> Chan:
    """A channel whose values sit in .tdx block `external`, through a `sequence` element."""
    return Chan(
        f"ch{index}",
        column=f'<values>#xpointer(id("s{index}"))</values>',
        sequence=f'<{sequence} id="s{index}"><values external="{external}"/></{sequence}>',
    )


def inline(index: int, sequence: str, text: str) -> Chan:
    """A channel whose values are written inline in the header."""
    return Chan(
        f"ch{index}",
        column=f'<values>#xpointer(id("s{index}"))</values>',
        sequence=f'<{sequence} id="s{index}"><values>{text}</values></{sequence}>',
    )


def block(ident: str, offset: int, length: int, value_type: str, extra: str = "") -> str:
    """A ``block`` element."""
    return (
        f'<block id="{ident}" byteOffset="{offset}" length="{length}" '
        f'valueType="{value_type}"{extra}/>'
    )

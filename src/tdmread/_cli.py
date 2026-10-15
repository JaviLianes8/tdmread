"""Command-line interface for reading NI TDM/TDX files."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from contextlib import suppress
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

from . import __version__
from ._cli_output import (
    as_csv,
    as_json,
    emit,
    emit_data,
    emit_error,
    flush_stdout,
    short,
    visible,
)
from ._errors import TdmError
from ._model import TdmFile
from ._reader import read_tdm

_EXAMPLES = """\
examples:
  tdmread info measurement.tdm
  tdmread channels measurement.tdm
  tdmread dump measurement.tdm --group Amplitudes --channel "A = 1" --format csv
  tdmread dump measurement.tdm -g Amplitudes -c "A = 1" -f json -o values.json

exit status: 0 on success, 1 when a file cannot be read, 2 for a usage error,
130 when interrupted.
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``tdmread`` console script. Returns a process exit code.

    As with any argparse program, ``--help``, ``--version`` and usage errors raise
    ``SystemExit`` (codes 0 and 2) instead of returning.

    >>> from tdmread._cli import main
    >>> main(["info", "no-such-file.tdm"])
    1
    """
    try:
        return _run(argv)
    finally:
        _settle(sys.stdout)
        _settle(sys.stderr)


def _run(argv: Sequence[str] | None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        exit_code: int = args.handler(args)
        flush_stdout()
        return exit_code
    except BrokenPipeError:
        # The reader of our output went away (for example `| head`): stop quietly.
        _silence(sys.stdout)
        return 1
    except KeyboardInterrupt:
        return 130
    except (TdmError, OSError) as exc:
        emit_error(f"tdmread: error: {short(str(exc))}\n")
        return 1


def _settle(stream: TextIO | None) -> None:
    # Flush now; if the reader is gone, point the descriptor at the null device so the
    # interpreter's own flush at exit cannot fail and change the exit status.
    if stream is None:
        return
    try:
        stream.flush()
    except (OSError, ValueError):
        _silence(stream)


def _silence(stream: TextIO | None) -> None:
    # Only the process's own standard streams are redirected, never a caller's stream.
    if stream is None or stream not in (sys.__stdout__, sys.__stderr__):
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, stream.fileno())  # type: ignore[union-attr]
        os.close(devnull)
    except (OSError, ValueError, AttributeError):
        pass


class _Parser(argparse.ArgumentParser):
    # Python 3.11+ ignores a failed write of help or usage text; 3.10 does not.
    def _print_message(self, message: str, file: SupportsWrite[str] | None = None) -> None:
        with suppress(OSError, AttributeError):
            super()._print_message(message, file)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="tdmread",
        description="Read NI TDM/TDX measurement files (XML .tdm header plus binary .tdx).",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"tdmread {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")

    info = sub.add_parser("info", help="print dataset metadata and a group summary")
    _add_files(info)
    info.set_defaults(handler=_cmd_info)

    channels = sub.add_parser("channels", help="list every channel with its type and length")
    _add_files(channels)
    channels.set_defaults(handler=_cmd_channels)

    dump = sub.add_parser("dump", help="dump one channel's values to CSV or JSON")
    _add_files(dump)
    dump.add_argument("-g", "--group", required=True, help="group name")
    dump.add_argument("-c", "--channel", required=True, help="channel name")
    dump.add_argument(
        "-f", "--format", choices=("csv", "json"), default="csv", help="output format"
    )
    dump.add_argument("-o", "--output", help="write to this file instead of standard output")
    dump.set_defaults(handler=_cmd_dump)
    return parser


def _add_files(command: argparse.ArgumentParser) -> None:
    command.add_argument("tdm", help="path to the .tdm header file")
    command.add_argument("--tdx", help="path to the .tdx data file (default: from the header)")


def _load(args: argparse.Namespace) -> TdmFile:
    return read_tdm(args.tdm, args.tdx)


def _cmd_info(args: argparse.Namespace) -> int:
    dataset = _load(args)
    meta = dataset.metadata
    lines = [
        f"{label}: {visible(value)}"
        for label, value in (
            ("name", meta.name),
            ("title", meta.title),
            ("author", meta.author),
            ("datetime", meta.datetime),
            ("description", meta.description),
        )
        if value
    ]
    lines.append(f"groups: {len(dataset.groups)}")
    lines.extend(f"  {visible(g.name)} ({len(g.channels)} channels)" for g in dataset)
    emit("\n".join(lines) + "\n")
    return 0


def _cmd_channels(args: argparse.Namespace) -> int:
    dataset = _load(args)
    lines = []
    for group, channel in dataset.channels():
        kind = channel.value_type or channel.datatype or channel.representation or "?"
        unit = f" [{visible(channel.unit)}]" if channel.unit else ""
        name = f"{visible(group.name)}\t{visible(channel.name)}{unit}"
        lines.append(f"{name}\t{visible(kind)}\t{len(channel)}")
    emit("".join(line + "\n" for line in lines))
    return 0


def _cmd_dump(args: argparse.Namespace) -> int:
    dataset = _load(args)
    channel = dataset.group(args.group).channel(args.channel)
    text = as_csv(channel) if args.format == "csv" else as_json(channel)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    else:
        emit_data(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

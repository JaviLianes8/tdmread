"""Command-line interface for reading NI TDM/TDX files."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from . import __version__
from ._cli_output import as_csv, as_json, emit, emit_data, short
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

    >>> from tdmread._cli import main
    >>> main(["info", "no-such-file.tdm"])
    1
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        exit_code: int = args.handler(args)
        sys.stdout.flush()
        return exit_code
    except BrokenPipeError:
        # The reader of our output went away (for example `| head`): stop quietly, and
        # point stdout at the null device so the final flush at exit cannot fail again.
        _silence_stdout()
        return 1
    except KeyboardInterrupt:
        return 130
    except (TdmError, OSError) as exc:
        emit(f"tdmread: error: {short(str(exc))}\n", sys.stderr)
        return 1


def _silence_stdout() -> None:
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)
    except (OSError, ValueError, AttributeError):
        pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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
        f"{label}: {value}"
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
    lines.extend(f"  {group.name} ({len(group.channels)} channels)" for group in dataset)
    emit("\n".join(lines) + "\n")
    return 0


def _cmd_channels(args: argparse.Namespace) -> int:
    dataset = _load(args)
    lines = []
    for group, channel in dataset.channels():
        kind = channel.value_type or channel.datatype or channel.representation or "?"
        unit = f" [{channel.unit}]" if channel.unit else ""
        lines.append(f"{group.name}\t{channel.name}{unit}\t{kind}\t{len(channel)}")
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

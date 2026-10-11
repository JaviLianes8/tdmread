"""Command-line interface for reading NI TDM/TDX files."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Sequence

from . import __version__
from ._errors import TdmError
from ._model import Channel, TdmFile
from ._reader import read_tdm

_EXAMPLES = """\
examples:
  tdmread info measurement.tdm
  tdmread channels measurement.tdm
  tdmread dump measurement.tdm --group Amplitudes --channel "A = 1" --format csv
  tdmread dump measurement.tdm -g Amplitudes -c "A = 1" -f json -o values.json
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the `tdmread` console script. Returns a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        exit_code: int = args.handler(args)
        return exit_code
    except TdmError as exc:
        print(f"tdmread: error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"tdmread: error: {exc}", file=sys.stderr)
        return 1


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
    info.add_argument("tdm", help="path to the .tdm header file")
    info.add_argument("--tdx", help="path to the .tdx data file (default: from the header)")
    info.set_defaults(handler=_cmd_info)

    channels = sub.add_parser("channels", help="list every channel with its type and length")
    channels.add_argument("tdm", help="path to the .tdm header file")
    channels.add_argument("--tdx", help="path to the .tdx data file (default: from the header)")
    channels.set_defaults(handler=_cmd_channels)

    dump = sub.add_parser("dump", help="dump one channel's values to CSV or JSON")
    dump.add_argument("tdm", help="path to the .tdm header file")
    dump.add_argument("-g", "--group", required=True, help="group name")
    dump.add_argument("-c", "--channel", required=True, help="channel name")
    dump.add_argument(
        "-f", "--format", choices=("csv", "json"), default="csv", help="output format"
    )
    dump.add_argument("-o", "--output", help="write to this file instead of standard output")
    dump.add_argument("--tdx", help="path to the .tdx data file (default: from the header)")
    dump.set_defaults(handler=_cmd_dump)
    return parser


def _load(args: argparse.Namespace) -> TdmFile:
    return read_tdm(args.tdm, args.tdx)


def _cmd_info(args: argparse.Namespace) -> int:
    dataset = _load(args)
    meta = dataset.metadata
    for label, value in (
        ("name", meta.name),
        ("title", meta.title),
        ("author", meta.author),
        ("datetime", meta.datetime),
        ("description", meta.description),
    ):
        if value:
            print(f"{label}: {value}")
    print(f"groups: {len(dataset.groups)}")
    for group in dataset.groups:
        print(f"  {group.name} ({len(group.channels)} channels)")
    return 0


def _cmd_channels(args: argparse.Namespace) -> int:
    dataset = _load(args)
    for group, channel in dataset.channels():
        kind = channel.value_type or channel.representation or "?"
        unit = f" [{channel.unit}]" if channel.unit else ""
        print(f"{group.name}\t{channel.name}{unit}\t{kind}\t{len(channel)}")
    return 0


def _cmd_dump(args: argparse.Namespace) -> int:
    dataset = _load(args)
    channel = dataset.group(args.group).channel(args.channel)
    text = _as_csv(channel) if args.format == "csv" else _as_json(channel)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    return 0


def _as_csv(channel: Channel) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["index", channel.name or "value"])
    for index, value in enumerate(channel.data):
        writer.writerow([index, repr(value)])
    return buffer.getvalue()


def _as_json(channel: Channel) -> str:
    payload = {
        "name": channel.name,
        "unit": channel.unit,
        "value_type": channel.value_type,
        "representation": channel.representation,
        "length": len(channel),
        "data": list(channel.data),
    }
    return json.dumps(payload, indent=2) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())

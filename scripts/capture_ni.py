"""Record how NI's own software reads TDM files, as the oracle for tdmread's tests.

Windows only, with LabVIEW 2026 (and the NI USI components it installs), pywin32 and
npTDMS. For every .tdm given it records two views in a JSON file:

* ``datastore``: the values NI's USI DataStore COM API returns for each channel's
  local column (``UsiCore.DataStoreEnvironment``), with times as local wall-clock text.
* ``channel``: the values NI's channel-level reader produces. LabVIEW's shipped
  ``Convert to TDM or TDMS.vi`` is run through LabVIEW's ActiveX server to turn the
  .tdm into a .tdms, which npTDMS then reads back. This view applies the sequence
  representations (implicit and scaled channels) the way LabVIEW and DIAdem do.

Non-finite floats are written as "nan", "inf" and "-inf"; a failure is recorded as
the error text instead of values.

    python scripts/capture_ni.py OUT.json FILE.tdm [FILE.tdm ...]
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Value lists longer than this are recorded as a count and a SHA-256 of their JSON form.
LONG = 1000
CONVERT_VI = (
    r"C:\Program Files\National Instruments\LabVIEW 2026\vi.lib\Platform\storage"
    r"\utility\Convert to TDM or TDMS.vi"
)


def _plain(value: Any) -> Any:
    if hasattr(value, "item") and not hasattr(value, "_oleobj_"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if hasattr(value, "_oleobj_"):
        parts = [getattr(value, n) for n in ("Year", "Month", "Day", "Hour", "Minute")]
        second = value.Second
        micro = value.Millisecond * 1000 + value.MicroSecond
        y, mo, d, h, mi = parts
        return f"{y:04d}-{mo:02d}-{d:02d}T{h:02d}:{mi:02d}:{second:02d}.{micro:06d}"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def values_entry(values: list[Any]) -> Any:
    """Keep short value lists whole; summarise long ones by count and SHA-256."""
    if len(values) <= LONG:
        return values
    text = json.dumps(values, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {"count": len(values), "first": values[:5], "sha256": digest}


def datastore_view(path: Path) -> dict[str, Any]:
    import win32com.client.dynamic as dyn

    env = dyn.Dispatch("UsiCore.DataStoreEnvironment")
    store = env.ConnectDataStoreByParameter("TDM", f"<filename readonly='yes'>{path}</filename>")
    if store is None:
        return {"error": "NI could not open the file"}
    groups = []
    try:
        for root in store.RootElements:
            for group in root.Children:
                channels = []
                for channel in group.Children:
                    entry: dict[str, Any] = {"name": channel.Name}
                    for ref in channel.References:
                        if ref.Name != "local_columns":
                            continue
                        for column in ref.Elements:
                            try:
                                size = column.Size
                                entry["values"] = values_entry(
                                    [_plain(column.Values(i)) for i in range(1, size + 1)]
                                )
                            except Exception as exc:
                                # A value NI cannot read is part of the record, not a stop.
                                entry["error"] = str(exc)
                    channels.append(entry)
                groups.append({"name": group.Name, "channels": channels})
    finally:
        store.Close()
    return {"groups": groups}


def channel_views(paths: list[Path]) -> dict[str, dict[str, Any]]:
    import win32com.client.dynamic as dyn
    from nptdms import TdmsFile

    lv = dyn.Dispatch("LabVIEW.Application")
    for _ in range(180):
        if lv.Version:
            break
        time.sleep(1)
    vi = lv.GetVIReference(CONVERT_VI, "", False, 0)
    vi._FlagAsMethod("Run", "SetControlValue", "GetControlValue")
    views: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as folder:
        for index, path in enumerate(paths):
            target = Path(folder) / f"out{index}.tdms"
            vi.SetControlValue("source file path", str(path))
            vi.SetControlValue("target file path", str(target))
            vi.SetControlValue("target file format (TDMS)", 1)
            vi.SetControlValue("target file operation (3:create)", 3)
            vi.SetControlValue("data chunk size (1E+7)", 1e7)
            vi.SetControlValue("DataPlugin name", "")
            vi.Run(False)
            failed, code, _ = vi.GetControlValue("error out")
            if failed:
                views[path.name] = {"error": f"LabVIEW error {code}"}
                continue
            tdms = TdmsFile.read(target)
            views[path.name] = {
                "groups": [
                    {
                        "name": group.name,
                        "channels": [
                            {"name": ch.name, "values": values_entry([_plain(v) for v in ch[:]])}
                            for ch in group.channels()
                        ],
                    }
                    for group in tdms.groups()
                ]
            }
    return views


def isolated_datastore_view(path: Path) -> dict[str, Any]:
    # NI's DataStore reader crashes the whole process on some malformed files, so each
    # file is read in a child process and a crash is recorded as an error.
    done = subprocess.run(
        [sys.executable, __file__, "--datastore", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    if done.returncode != 0:
        return {"error": f"NI's DataStore reader stopped with exit code {done.returncode}"}
    view: dict[str, Any] = json.loads(done.stdout)
    return view


def main(argv: list[str]) -> int:
    if argv[0] == "--datastore":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        print(json.dumps(datastore_view(Path(argv[1])), ensure_ascii=False))
        return 0
    out, paths = Path(argv[0]), [Path(p).resolve() for p in argv[1:]]
    channel = channel_views(paths)
    result = {
        path.name: {"datastore": isolated_datastore_view(path), "channel": channel[path.name]}
        for path in paths
    }
    for path in paths:
        # NI writes its warnings next to the file read; they are not part of the capture.
        path.with_name(path.name + ".log").unlink(missing_ok=True)
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

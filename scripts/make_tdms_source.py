"""Write gt_types.tdms, the TDMS file LabVIEW converted into tests/fixtures/labview2026/gt_types_0.

Every value in it is chosen here, so the converted TDM has a known answer. Needs npTDMS and
NumPy. LabVIEW's shipped ``Convert to TDM or TDMS.vi`` (target format TDM, operation
create) turned the result into ``gt_types_0.tdm`` and ``gt_types_0.tdx``.

    python scripts/make_tdms_source.py gt_types.tdms
"""

from __future__ import annotations

import sys

import numpy as np
from nptdms import ChannelObject, GroupObject, RootObject, TdmsWriter

INF = float("inf")
INTS = {
    "i8": (np.int8, [0, 1, -1, 127, -128, 42]),
    "u8": (np.uint8, [0, 1, 255, 128, 42]),
    "i16": (np.int16, [0, -1, 32767, -32768, 1234]),
    "u16": (np.uint16, [0, 65535, 32768, 1]),
    "i32": (np.int32, [0, -1, 2147483647, -2147483648, 123456]),
    "u32": (np.uint32, [0, 4294967295, 2147483648, 7]),
    "i64": (np.int64, [0, -1, 2**63 - 1, -(2**63), 2**53 + 1]),
    "u64": (np.uint64, [0, 2**64 - 1, 2**63, 2**53 + 1]),
}
FLOATS = {
    "f32": (np.float32, [0.0, -0.0, 1.5, -2.25, 3.4028234663852886e38, 1.401298464324817e-45]),
    "f64": (np.float64, [0.0, -0.0, 0.1, -1e308, 5e-324, 1.7976931348623157e308]),
}
TAILS = {"f32": [INF, -INF, float("nan"), 0.1], "f64": [INF, -INF, float("nan"), 2.0 / 3.0]}
TEXT = ["plain", "", "with space ", " lead", 'x<y & z>"q"\'', "café 日本 Ω"]
TEXT += ["tab\there", "line\nbreak", "é" * 3]
TIMES = ["2026-10-14T15:34:39.500000", "1904-01-01T00:00:00", "2000-02-29T23:59:59.250000"]
TIMES += ["1970-01-01T00:00:00"]


def objects() -> list[object]:
    root = RootObject(
        properties={
            "title": "tdmread ground truth",
            "author": "tdmread",
            "prop_str": "root text",
            "prop_i32": np.int32(-7),
            "prop_f64": 2.5,
            "prop_time": np.datetime64("2026-10-14T12:00:00.125"),
        }
    )
    objs: list[object] = [root]
    objs.append(
        GroupObject("Ints", properties={"description": "integer types", "g_i32": np.int32(12)})
    )
    for name, (dtype, values) in INTS.items():
        data = np.array(values, dtype=dtype)
        objs.append(ChannelObject("Ints", name, data, properties={"unit_string": "count"}))
    objs.append(GroupObject("Floats", properties={"g_text": "floats"}))
    for name, (dtype, values) in FLOATS.items():
        props = {"unit_string": "V", "description": f"{name} values"}
        data = np.array(values + TAILS[name], dtype=dtype)
        objs.append(ChannelObject("Floats", name, data, properties=props))
    objs.append(ChannelObject("Floats", "empty", np.array([], dtype=np.float64)))
    objs += [GroupObject("Text"), ChannelObject("Text", "strings", TEXT)]
    stamps = np.array([np.datetime64(t) for t in TIMES])
    objs += [GroupObject("Time"), ChannelObject("Time", "stamps", stamps), GroupObject("Wave")]
    wave_props = {"wf_increment": 0.001, "wf_start_offset": 0.0, "wf_samples": np.int32(1000)}
    wave_props |= {"wf_xname": "Time", "wf_xunit_string": "s", "flag": True}
    sine = np.sin(np.arange(1000) * 0.01)
    objs.append(ChannelObject("Wave", "sine", sine, properties=wave_props))
    objs.append(ChannelObject("Wave", "ramp", np.arange(1000, dtype=np.int32)))
    return objs


def main(path: str) -> None:
    with TdmsWriter(path) as writer:
        writer.write_segment(objects())


if __name__ == "__main__":
    main(sys.argv[1])

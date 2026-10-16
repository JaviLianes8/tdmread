# tdmread

[![Lianes8 Certified](https://lianes8studio.com/certified/lianes8-certified-badge.svg)](https://lianes8studio.com/certified)

Read NI TDM/TDX measurement files (an XML `.tdm` header plus a binary `.tdx` data file,
as written by LabVIEW, DIAdem and other NI software) in plain Python: no dependencies,
nothing to compile, fully typed.

## Install

```
pip install tdmread
```

Python 3.10 or newer. NumPy is optional (`pip install tdmread[numpy]` for
`Channel.to_numpy()`).

## Quick start

```python
from tdmread import read_tdm

dataset = read_tdm("measurement.tdm")  # the .tdx is found through the header

for group in dataset:
    print(group.name)
    for channel in group:
        print(f"  {channel.name} [{channel.unit}] {channel.datatype}: {len(channel)} values")

voltage = dataset.group("Measurements").channel("voltage")
print(voltage.data[:5])  # a tuple of numbers, strings or datetimes
print(voltage.properties.get("wf_increment"))  # custom properties, typed
print(sum(voltage.numbers()))  # typed view for type checkers
```

Every channel carries its `name`, `unit`, `description`, `datatype` (`DT_DOUBLE`, ...),
the .tdx `value_type`, the sequence `representation`, the header `minimum` and `maximum`,
its custom `properties`, and `data`: numbers (`int` for integer types), strings, or naive
`datetime` values for time channels. The dataset and each group have `properties` too, and
`dataset.metadata` holds the root name, title, description, author and datetime.

What is read, all checked against NI's own reader (see [GUIDE.md](https://github.com/JaviLianes8/tdmread/blob/main/GUIDE.md)):

- Every numeric .tdx value type (8 to 64-bit integers, signed and unsigned, 32 and 64-bit
  floats) in both byte orders, and 16-byte time values.
- Values written inline in the header: numbers, strings and times.
- `implicit_linear` and `implicit_constant` channels (generated, no .tdx needed) and
  `raw_linear` / `raw_linear_external` scaled channels.
- Interleaved `block_bm` layouts.

Anything else (for example strings stored in the .tdx, `block_mr` layouts or
`implicit_saw`) raises `UnsupportedTdmError` instead of returning wrong numbers.

## Command line

```
tdmread info measurement.tdm
tdmread channels measurement.tdm
tdmread dump measurement.tdm --group Amplitudes --channel "A = 1" --format csv
tdmread dump measurement.tdm -g Amplitudes -c "A = 1" -f json -o values.json
```

`info` prints the dataset metadata and a group summary, `channels` lists every channel with
its type and length, and `dump` writes one channel as CSV or JSON (UTF-8). Errors go to standard
error with exit code 1; usage errors exit with 2. `python -m tdmread` works too.

## Why

[npTDMS](https://pypi.org/project/npTDMS/) reads the newer `.tdms` format but not the
`.tdm`/`.tdx` pair. Two packages do read `.tdm`/`.tdx`, each with weight:
[tdm-loader](https://pypi.org/project/tdm-loader/) depends on NumPy, and
[TDMtermite](https://pypi.org/project/TDMtermite/) ships a compiled C++ extension.
`tdmread` is a small, fully typed reader with no runtime dependencies and nothing to build,
whose behaviour is pinned by tests against files LabVIEW 2026 wrote and against NI's own
reading of them.

## More

- [GUIDE.md](https://github.com/JaviLianes8/tdmread/blob/main/GUIDE.md): the format rules,
  errors, limits, and upgrading from 0.2.
- [CHANGELOG.md](https://github.com/JaviLianes8/tdmread/blob/main/CHANGELOG.md)

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/tdmread/blob/main/LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/

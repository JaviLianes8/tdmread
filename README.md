# tdmread

Zero-dependency, typed reader for NI TDM/TDX files (an XML `.tdm` header paired with a
binary `.tdx` data file), using only the Python standard library.

## Install

```
pip install tdmread
```

## Usage

```python
from tdmread import read_tdm

dataset = read_tdm("measurement.tdm")  # the .tdx is found via the header reference

for group in dataset.groups:
    print(group.name)
    for channel in group.channels:
        print(f"  {channel.name} [{channel.unit}]: {channel.data[:5]}")

# Direct lookup by name.
voltage = dataset.group("Measurements").channel("voltage")
print(voltage.value_type, len(voltage.data))
```

Each `Channel` carries its `name`, `unit`, `description`, the TDM `value_type`, and the
decoded `data` as a plain tuple of numbers. Pass a second argument to point at a `.tdx`
in a non-default location: `read_tdm("m.tdm", "elsewhere/m.tdx")`.

## Why

[npTDMS](https://pypi.org/project/npTDMS/) reads the newer `.tdms` format but not the
older `.tdm`/`.tdx` pair, so it is no help to anyone holding `.tdm` data. Two packages do
read `.tdm`/`.tdx`, but each pulls in weight: [tdm-loader](https://pypi.org/project/tdm-loader/)
depends on NumPy, and [TDMtermite](https://pypi.org/project/TDMtermite/) ships a compiled
C++ extension. `tdmread` fills the remaining gap: a small, fully typed reader with no
runtime dependencies and nothing to build, for scripts and environments where adding
NumPy or a native extension is unwelcome.

## Supported subset

`tdmread` targets the common documented TDM layout and is honest about its limits:

- Numeric channels with the `explicit` sequence representation.
- Value types `eInt8`/`16`/`32`/`64`, their unsigned variants, `eFloat32`, and `eFloat64`,
  in both `littleEndian` and `bigEndian` byte order.

It does not yet decode string, timestamp, or extended-precision channels, implicit or
raw-linear sequences, or per-sample flags; those raise `UnsupportedTdmError` rather than
returning wrong numbers. Issues and sample files that broaden the coverage are welcome.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/

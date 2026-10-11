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

Each `Channel` carries its `name`, `unit`, `description`, the TDM `value_type`, the
`representation` (`explicit` or `implicit_linear`), the header `minimum`/`maximum` and
`datatype`, and the decoded `data` as a plain tuple of numbers. `read_tdm` also returns
dataset metadata on `dataset.metadata` (name, title, description, author, datetime).
Pass a second argument to point at a `.tdx` in a non-default location:
`read_tdm("m.tdm", "elsewhere/m.tdx")`.

```python
# Convenience helpers.
for group, channel in dataset.channels():
    print(group.name, channel.name, len(channel))

values = dataset.group("Amplitudes").channel("A = 1").to_list()
array = dataset.group("Amplitudes").channel("A = 1").to_numpy()  # needs numpy installed
```

## Command line

Installing the package also installs a `tdmread` console script:

```
tdmread info measurement.tdm
tdmread channels measurement.tdm
tdmread dump measurement.tdm --group Amplitudes --channel "A = 1" --format csv
tdmread dump measurement.tdm -g Amplitudes -c "A = 1" -f json -o values.json
```

`info` prints the dataset metadata and a group summary, `channels` lists every channel
with its type and length, and `dump` writes one channel to CSV or JSON (to standard
output, or to a file with `-o`). Errors go to standard error with exit code 1.

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
- Numeric channels with the `implicit_linear` representation, generated as
  `offset + index * increment` from the header (no `.tdx` needed for those).
- Value types `eInt8`/`16`/`32`/`64`, their unsigned variants, `eFloat32`, and `eFloat64`,
  in both `littleEndian` and `bigEndian` byte order.

It does not yet decode string, timestamp, or extended-precision channels, `raw_linear`
scaled sequences, or per-sample flags; those raise `UnsupportedTdmError` rather than
returning wrong numbers. Issues and sample files that broaden the coverage are welcome.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/

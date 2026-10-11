# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

- Added decoding of `implicit_linear` channels: a generated `offset + index * increment`
  axis sized from `NI_ChannelLength` (or the submatrix row count), with a `0, 1, 2, ...`
  default when generation parameters are absent. These channels need no `.tdx`.
- Added a `tdmread` command-line interface (`info`, `channels`, `dump` to CSV or JSON),
  with `--version`, example-rich help, and errors on stderr with exit code 1.
  `python -m tdmread` works as an alias.
- `read_tdm` now returns dataset metadata (`TdmFile.metadata`: name, title, description,
  author, datetime) and each `Channel` carries its `representation`, `minimum`,
  `maximum`, and `datatype`; groups carry their `description`.
- Added convenience helpers: `Channel.__len__`, `Channel.to_list`, optional
  `Channel.to_numpy`, `Group` iteration and `channel_names`, and `TdmFile` iteration,
  `group_names`, and `channels()`.
- Exported `FileMetadata` and `supported_value_types`.
- Committed the real `SineData` sample files as golden fixtures and added end-to-end
  tests, including one that installs the package and drives the installed console script.

## [0.1.0]

- First release.
- `read_tdm` parses a `.tdm` XML header, locates the `.tdx` by its reference, and returns
  groups and channels with decoded numeric data.
- Supports numeric channels with the `explicit` sequence representation, signed and
  unsigned 8/16/32/64-bit integers, 32/64-bit floats, and both byte orders.
- Unsupported value types, sequence representations, and byte orders raise
  `UnsupportedTdmError`; missing files raise `TdmFileNotFoundError`.

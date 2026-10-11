# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- First release.
- `read_tdm` parses a `.tdm` XML header, locates the `.tdx` by its reference, and returns
  groups and channels with decoded numeric data.
- Supports numeric channels with the `explicit` sequence representation, signed and
  unsigned 8/16/32/64-bit integers, 32/64-bit floats, and both byte orders.
- Unsupported value types, sequence representations, and byte orders raise
  `UnsupportedTdmError`; missing files raise `TdmFileNotFoundError`.

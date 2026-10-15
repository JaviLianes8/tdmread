# tdmread guide

This guide describes exactly what `tdmread` reads, how it maps the TDM format onto Python
values, what it refuses, and how it differs from NI's own reader. Every rule here is pinned
by a test; the rules about NI's behaviour were checked on LabVIEW 2026 (see "Ground truth").

## Reading a dataset

`read_tdm(tdm_path, tdx_path=None)` parses the XML header and returns a `TdmFile`.

- The `.tdx` is the file the header names (`<file url="...">`), in the header's folder or
  below it. A header that names an absolute path, a drive, a URL scheme, a step out with
  `..`, a name made only of dots or spaces, or a character no Windows file name can hold
  (control characters and any of `:<>"|?*`) is refused with `TdmError`, so a header cannot
  make the reader open an unrelated file. Only the text is checked: a symbolic link placed
  in the header's folder is followed. Pass `tdx_path` to read a `.tdx` from anywhere.
- The `.tdx` is opened only when a channel stores values in it, and only the bytes of the
  blocks' values are read (for a `block_bm` whose values sit close together, the range
  covering them), so a header whose values are all inline or generated needs no `.tdx`,
  and a large `.tdx` is never loaded whole.
- Every group, channel, stored column, value sequence and block is decoded once per
  dataset, however many times the header refers to it; channels that share them share the
  same tuple. A generated column shared by several channels is generated for each, since
  its length comes from the channel.
- Paths may be `str` or any `os.PathLike[str]` such as `pathlib.Path`.

## The result

| Type | Fields and helpers |
| --- | --- |
| `TdmFile` | `groups`, `metadata`, `properties`; `len()`, iteration, `group_names`, `group(name)`, `channels()` |
| `Group` | `name`, `channels`, `description`, `properties`; `len()`, iteration, `channel_names`, `channel(name)` |
| `Channel` | `name`, `unit`, `description`, `value_type`, `data`, `representation`, `minimum`, `maximum`, `datatype`, `properties`; `len()`, `numbers()`, `strings()`, `times()`, `to_list()`, `to_numpy()` |
| `FileMetadata` | `name`, `title`, `description`, `author`, `datetime` (the header text) |

All four are frozen dataclasses: they compare by value, hash, copy and pickle. `group()`
and `channel()` return the first match by name and raise `TdmError` when there is none.

```pycon
>>> from datetime import datetime
>>> from tdmread import Channel, Group, TdmFile
>>> stamps = Channel("t", "", "", "eTimeUsi", (datetime(2026, 10, 14, 15, 34, 39, 500000),))
>>> dataset = TdmFile((Group("Run", (stamps,)),))
>>> dataset.group("Run").channel("t").times()[0].isoformat()
'2026-10-14T15:34:39.500000'
>>> [(g.name, c.name) for g, c in dataset.channels()]
[('Run', 't')]

```

### Values

`Channel.data` is a tuple holding one kind of value:

- Numbers: `int` for every integer type, `float` for 32 and 64-bit floats. Values stored
  in the `.tdx` are exactly what is stored; 64-bit integers stay exact and 32-bit floats
  are widened to Python floats without rounding. As NI's reader does, inline integers are
  first clamped to the signed 32-bit range, then values in a `byte_sequence` are read
  unsigned (modulo 256) and values in a `short_sequence` wrap to 16 bits; inline values in
  a `float_sequence` are rounded to 32-bit precision. Non-finite floats come back as `inf`, `-inf`, `nan`.
- Strings: `str`, for string channels written in the header.
- Times: naive `datetime.datetime`. TDM stores local wall-clock time without a zone; in the
  `.tdx` a time is an unsigned 64-bit fraction of a second (units of 2**-64 s) followed by
  signed 64-bit seconds since 1904-01-01 00:00 (seconds first in a big-endian file). In the
  header it is ISO text with any number of fractional digits, which NI reads as a double
  and turns into a 2**-64 fraction (cut; a double of exactly 1.0 carries into the next
  second). As NI's reader does, the fraction is rounded to the nearest nanosecond, but
  never past the end of its second (LabVIEW stores fractions just below the exact value),
  and then cut to microseconds, the finest unit `datetime` holds. A time outside the
  years 1 to 9999 raises `TdmError`.

Because `data` can hold any of the three kinds, a type checker sees
`tuple[float, ...] | tuple[str, ...] | tuple[datetime, ...]`. `numbers()`, `strings()` and
`times()` return the same tuple typed as one kind, or raise `TdmError` when the channel
holds another kind (an empty channel gives `()` for all three).

```pycon
>>> from tdmread import Channel, TdmError
>>> channel = Channel("n", "", "", "eInt32Usi", (1, 2, 3))
>>> sum(channel.numbers())
6
>>> try:
...     channel.strings()
... except TdmError as exc:
...     print(exc)
channel 'n' holds int values, not strings

```

`value_type` is the `.tdx` valueType the values were stored as, and is empty for values
written in the header or generated. `datatype` is the header's `DT_*` name as written.

### Value types

| valueType | Read as |
| --- | --- |
| `eInt8Usi`, `eUInt8Usi` | unsigned byte, 0 to 255 (NI writes `eInt8Usi` for `DT_BYTE`, and NI's reader returns 255 for the byte 0xFF) |
| `eSInt8Usi` | signed byte |
| `eInt16Usi`, `eInt32Usi`, `eInt64Usi` | signed integers |
| `eUInt16Usi`, `eUInt32Usi`, `eUInt64Usi` | unsigned integers |
| `eFloat32Usi`, `eFloat64Usi` | IEEE 754 floats |
| `eTimeUsi` | 16-byte time, described above |

`supported_value_types()` returns exactly this set. Any other valueType raises
`UnsupportedTdmError`; `eStringUsi` (strings stored in the `.tdx`) is refused because NI's
own reader fails on it too.

### Sequence representations

| `sequence_representation` | Values |
| --- | --- |
| `explicit` (or missing) | the stored values, from the `.tdx` or inline |
| `implicit_linear` | `start + index * increment` from `generation_parameters`; a single parameter gives a constant; extra parameters are ignored |
| `implicit_constant` | the first parameter, repeated |
| `raw_linear`, `raw_linear_external` | `offset + factor * raw` for each stored value, with `offset factor` from `generation_parameters` |

A generated column without `generation_parameters` takes the start and increment from the
first values of the sequence it refers to, as NI's reader does. Anything else (for
example `implicit_saw`, `raw_polynomial`, or `implicit`) raises `UnsupportedTdmError`.

### Lengths

- A `.tdx` block gives as many values as its `length`, whatever the submatrix row count
  says; this is what NI's channel reader does.
- Inline values give as many values as are written.
- A generated channel takes its length from its submatrix `number_of_rows`, or else from a
  `NI_ChannelLength` channel property; with neither it raises `TdmError`.
- A column with no values reference is an empty channel (NI writes empty channels so).

### Layouts

A plain `block` is contiguous from `byteOffset`; NI's reader ignores `blockSize` and
`blockOffset` on it, and so does tdmread. A `block_bm` interleaves channels: value `i` sits
at `byteOffset + blockOffset + i * blockSize`. A `block_mr` is refused: when probed, NI's
DataStore API and NI's channel reader returned different values for it.

### Properties

`properties` is a read-only mapping (hashable and picklable) of each `*_attribute` in the
element's `instance_attributes`. `byte`, `short`, `long` and `longlong` attributes become
`int` (`byte`, `short` and `long` narrowed as inline integers are), `float` (rounded to
32-bit precision) and `double` become `float`, `time` becomes a naive `datetime` (rounded
as above), and `string` becomes `str` (the first `<s>` part, or empty without one, as NI
reads it). A value that does not parse as its declared kind is kept as the raw text. When
a name repeats with the same kind, the last one wins, as in NI's reader. Attributes named
`name` or `description` are ordinary properties here (NI's reader shows the element's own
name and description under those names instead).

## Errors

| Exception | Raised when |
| --- | --- |
| `TdmFileNotFoundError` (a `TdmError` and a `FileNotFoundError`) | the header path is not a readable file (missing, a folder, or a name the system rejects), or a `.tdx` a channel needs is missing |
| `UnsupportedTdmError` (a `TdmError`) | the dataset uses something tdmread does not read (see above) |
| `TdmError` | anything else malformed: not XML, not a TDM header, a DTD, an unknown text encoding, a bad number or time, a reference to a missing sequence or block, a block past the end of the `.tdx`, a negative or non-integer count, a `.tdx` location outside the header folder or not a valid file name, a `.tdx` that is a folder, a generated size over the limit |

Other `OSError`s (for example a permission error, or too many open files) propagate
unchanged. Messages quote at most 40 characters of any text taken from a file (for the
`.tdx` name, its last 40); a path the caller passed is shown in full, as a path. The command line prints errors as
`tdmread: error: ...` (cut to 300 characters) and exits with 1; usage errors exit with 2,
an interrupt with 130. When the reader of its output or errors goes away, the command
ends quietly: with 1 if it noticed the lost output, otherwise with its usual code.

## Limits

- A dataset may decode at most ten million values plus one per byte of the `.tdx` from
  `.tdx` blocks, as many again by scaling (`raw_linear`), and as many again by generation
  (implicit channels); a block or column shared by several channels counts once. A real
  file stays below each limit, since a stored value takes at least one byte and its scaled
  copy and time axis are no longer than it; a header asking for more (for example many
  overlapping blocks, or a huge generated axis) raises `TdmError` at once instead of
  filling memory.
- Headers that declare a DTD are refused: TDM headers never use one, and refusing them
  rules out entity expansion whatever XML library runs underneath. The check looks for
  `<!DOCTYPE` and `<!ENTITY` anywhere in the file, so a comment that mentions them is
  refused too (NI escapes such text in values).

## Where tdmread differs from NI's reader

Each case below was observed on NI's reader. The layout and value cases are pinned by
`tests/test_ni_probes.py` against recorded NI readings; the text-spelling cases (numbers
and times written oddly) were checked by hand-made probes that are not part of the suite.

- NI returns no values when a block's valueType does not fit the sequence element (for
  example `eUInt16Usi` in a `short_sequence`); tdmread decodes the stored values by the
  block's valueType.
- NI converts 64-bit integers in a `double_sequence` to floats, and narrows 64-bit floats
  in a `float_sequence` to 32 bits; tdmread returns the stored values exactly.
- NI's readers return nothing for the sequence kinds `ubyte_sequence`,
  `ushort_sequence`, `ulong_sequence`, `longlong_sequence` and `ulonglong_sequence`, even
  with a matching valueType; tdmread reads them (inline as integers, from the `.tdx` by the
  block's valueType).
- NI does not read `longlong_attribute` properties; tdmread reads them as `int`.
- When a property name repeats with different kinds, NI keeps the first kind and converts
  later values into it: if any later value cannot be converted, NI keeps the first value
  of every repeated name of that element, otherwise the last converted value wins;
  tdmread takes the last value as written. Real files never repeat a name.
- Numbers and times written as text in unusual ways: NI's reader is lenient and its
  results depend on the exact spelling. Examples observed: it reads only the first 60
  characters of a number (60 zeros then a digit read as 0); it recognises only the exact
  non-finite spellings `INF`, `-INF` and `NaN` and reads others such as `inf`, `+INF`,
  `Infinity` or `nan` as 0 (its DataStore API returns non-finite values as empty); for a
  header time it reads a leading `YYYY-MM-DDTHH:MM:SS[.fraction]` and ignores the rest (a
  `Z` or `+02:00` zone is ignored, not applied; `,5` drops the fraction), drops or empties
  most other spellings, turns some years with more or fewer than four digits into
  unrelated or negative years, keeps year 0000, and normalises impossible dates (any month
  outside 1 to 12 becomes January, day 0 becomes day 1, other overflows roll over).
  tdmread accepts only these forms: integers as optionally signed decimal digits; floats
  in decimal or exponent notation (exponents of at most 6 digits), or any case of `inf`,
  `infinity` and `nan`; numbers up to 400 characters, sign included; times in exactly that form (an optional bare trailing dot allowed)
  whose rounded value falls in years 1 to 9999. Surrounding whitespace is ignored.
  Anything else raises `TdmError`, or stays raw text in a property.
- NI matches property names regardless of case (`Aa` and `aa` are one property); tdmread
  keeps them apart.
- NI reads a property value that does not parse by its leading number (`abc` as 0, `1.5`
  as 1 in a `long_attribute`) and drops a time property that does not parse; tdmread keeps
  the raw text.
- NI returns `.tdx` times outside the years 1 to 9999 (as 0000 or 10000); tdmread raises
  `TdmError`, since `datetime` cannot hold them.
- NI reads the text `1,5` as 1.0 in an inline `double_sequence` and `1.5` as 1 in an
  inline `long_sequence`; tdmread raises `TdmError`.
- NI's channel reader returns nothing for a column without `sequence_representation`
  (NI's DataStore API returns its values, as tdmread does), for a generated channel
  without a row count, and for `implicit`; tdmread reads the first two (the second by
  `NI_ChannelLength`) and raises for `implicit`.
- For a block that runs past the end of the `.tdx`, NI's channel reader returns nothing
  and its DataStore API returns the values it can, padded with an empty one; tdmread raises
  `TdmError`.

## Ground truth

- `tests/fixtures/labview2026`: files LabVIEW 2026 Community (26.3.1f1) wrote on
  2026-10-14: the output of the shipped examples `Write TDM Channel Groups.vi` and
  `Write TDM Event Data.vi`, and LabVIEW's `Convert to TDM or TDMS.vi` output for a TDMS
  file whose every value is chosen in `scripts/make_tdms_source.py` (all integer and float
  types, extremes, non-finite values, strings, times, properties). `manifest.json` records
  how each was made, its size and SHA-256.
- `tests/fixtures/ni_probes`: small hand-made datasets (`scripts/make_ni_probes.py`), one
  question each.
- `ni_view.json` in both folders: how NI's software read each file, recorded by
  `scripts/capture_ni.py` through NI's DataStore COM API and through LabVIEW's converter to
  TDMS. The tests compare every channel of every file with it.

## Upgrading from 0.2

Changes that can alter what a 0.2.1 call returned or raised:

- `eInt8Usi` is read as an unsigned byte (0.2.1 read it as signed, so 255 came back as -1).
- String channels and time channels are read (0.2.1 returned an empty tuple for string
  channels and refused times); `Channel.data` is typed as numbers, strings or datetimes.
- Inline values are read, and a malformed one raises `TdmError` (0.2.1 returned an empty
  tuple for both).
- `implicit_linear` takes its length from the row count first (0.2.1 preferred
  `NI_ChannelLength`); a single generation parameter gives a constant (0.2.1 used an
  increment of 1); missing parameters come from the stored values or raise (0.2.1 produced
  `0, 1, 2, ...`); `implicit` is refused (0.2.1 treated it as `implicit_linear`).
- A reference to a missing sequence or block raises `TdmError` (0.2.1 returned an empty
  channel); a header whose root is not `<tdm>`, or with a DTD, raises `TdmError`; malformed
  XML raises `TdmError` instead of `xml.etree.ElementTree.ParseError`, and an unknown
  text encoding raises `TdmError` instead of `LookupError`.
- A `.tdx` location outside the header's folder, or that is not a valid file name, is
  refused; a `.tdx` name the system cannot open raises `TdmError` (0.2.1 raised a plain
  `OSError`), and so does a `.tdx` that is a folder (0.2.1 raised `PermissionError`).
- A `block_bm` layout is read, and raises `TdmError` when it runs past the end of the
  `.tdx`; a `block_mr` layout raises `UnsupportedTdmError` (0.2.1 returned empty channels
  for both).
- Generated channels over the size limit (see "Limits") raise `TdmError` (0.2.1 built
  them, however large).
- A missing `.tdx` that no channel needs is no longer an error (0.2.1 raised
  `TdmFileNotFoundError` whenever the header listed blocks).
- A block attribute that is not an integer, or a negative `length`, raises `TdmError`
  (0.2.1 raised `ValueError` or `struct.error`).
- When two elements share an id, the first one is used (0.2.1 used the last).
- `Channel.to_list()` is typed `list[float] | list[str] | list[datetime]`.
- `tdmread dump`: JSON writes non-finite floats as the strings `"inf"`, `"-inf"` and
  `"nan"` (0.2.1 wrote `Infinity` and `NaN`, which are not JSON), times as ISO text, and
  adds `datatype`; it stays ASCII-only. CSV writes times as ISO text, strings as they are,
  and rows end with LF (0.2.1 ended them with CRLF, which showed as blank lines between rows
  on Windows standard output). Both are written as UTF-8 whatever the
  console encoding. `tdmread channels` shows the `DT_*` type of values written in the
  header (0.2.1 had no such channels), and `info` and `channels` escape unprintable characters
  in names (a tab shows as `\t`) and characters the console cannot show (0.2.1 stopped with
  `UnicodeEncodeError` there); `dump` always writes UTF-8.
- New: `properties` on `TdmFile`, `Group` and `Channel`; `Channel.numbers()`, `strings()`
  and `times()`; `eSInt8Usi`, `raw_linear`, `raw_linear_external`, `implicit_constant`
  and `block_bm`.

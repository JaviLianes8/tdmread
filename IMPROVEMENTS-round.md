# tdmread improvement round

Ranked, substantial improvements identified by reading the library, cross-checked
against genuine NI sample files from the RecordEvolution/TDMtermite repository and the
public NI TDM data model. Items marked "done" ship in this branch; the rest are honest
follow-ups.

## Shipped in this round (0.1.0 to 0.2.0)

1. **Implicit-linear axes (done).** The reader now decodes `implicit_linear` columns,
   generating `offset + index * increment` from `generation_parameters`, with the length
   taken from the channel's `NI_ChannelLength` (falling back to the submatrix
   `number_of_rows`). Missing parameters default to the natural `0, 1, 2, ...` index
   axis. This is the second representation the format uses and the one that needs no
   `.tdx` at all. Verified against the real `SineData_implicit.tdm` sample.

2. **A real command-line interface (done).** New `tdmread` console script
   (`[project.scripts]`, entry `tdmread._cli:main`) with `argparse` subcommands:
   `info` (dataset metadata and group summary), `channels` (one row per channel with
   type and length), and `dump` (one channel to CSV or JSON, to stdout or a file).
   `--version`, a help epilog with runnable examples, and errors routed to stderr with
   exit code 1. `python -m tdmread` works as an alias.

3. **Dataset and channel metadata (done).** `read_tdm` now returns a `FileMetadata`
   (name, title, description, author, datetime) on `TdmFile.metadata`, and each
   `Channel` carries its `representation`, `minimum`, `maximum`, and `datatype` from the
   header. Groups expose their `description`.

4. **Richer, friendlier typed objects (done).** `Channel` gains `__len__`, `to_list`,
   and an optional `to_numpy()`; `Group` gains `__len__`, `__iter__`, and
   `channel_names`; `TdmFile` gains `__len__`, `__iter__`, `group_names`, and a
   `channels()` iterator over every `(group, channel)` pair. All additive.

5. **NumPy stays optional (done).** The core never imports NumPy. `Channel.to_numpy()`
   imports it lazily and raises a clear `TdmError` with an install hint when it is
   absent. A `numpy` optional-dependency extra is declared for users who want it.

6. **Genuine golden fixtures and a real cross-check (done).** The real `SineData`,
   `SineData-be`, and `SineData_implicit` samples are committed under `tests/fixtures`.
   New tests parse them end to end and assert the decoded numbers against the known sine
   identity (`A = 1` is `sin(0.01 * index)`, amplitudes scale it, frequencies raise the
   step), and that the big-endian file decodes identically to the little-endian one.

7. **A true end-to-end test (done).** `tests/test_e2e.py` builds a throwaway virtual
   environment, installs the project editable into it, and drives the real installed
   `tdmread` console script as a subprocess against the committed samples, including a
   sine cross-check through the JSON dump path. No mocks.

8. **Code kept small and typed (done).** The reader is split into focused modules
   (`_reader`, `_sequence`, `_xml`, `_binary`, `_model`, `_cli`), each well under 200
   lines, still `mypy --strict` clean with no runtime dependencies.

## Honest follow-ups (not in this round)

9. **String and timestamp channels.** `eStringUsi` and `eTimeStamp`-style value types
   are not decoded yet; they still raise rather than returning wrong numbers.

10. **`raw_linear` scaled sequences.** Columns that store raw integers plus a scale and
    offset are not applied yet and remain unsupported on purpose.

11. **Per-sample flags / validity vectors.** The `global_flag` and generation flag
    vectors are not surfaced.

12. **Streaming for very large `.tdx`.** The reader loads the whole `.tdx` into memory;
    a memory-mapped or chunked path would help multi-gigabyte files.

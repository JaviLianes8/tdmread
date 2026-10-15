# tdmread 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.1, a646185)
- [x] Baseline gates run on 0.2.1
- [x] Real LabVIEW 2026 output and NI reader captures (item 7)
- [x] API review and 1.0.0 API changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e and upgrade from PyPI 0.2.1 (items 8, 10, 13, 14)
- [x] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer (item 16)
- [x] Gates (item 15)
- [x] PR #4 open and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Scorecard

| # | Item | Verdict | Evidence |
| --- | --- | --- | --- |
| 1 | API reviewed for stability | PASS | the nine 0.2.1 names kept with their signatures and defaults; additions only (`properties`, `numbers()`, `strings()`, `times()`); every behaviour change in CHANGELOG 1.0.0 and GUIDE "Upgrading from 0.2", checked side by side against PyPI 0.2.1 by lenses a and d |
| 2 | `__all__` exact | PASS | `test_contract::test_all_lists_exactly_the_public_api`; no other public attribute |
| 3 | Docstrings with runnable examples, doctests pass | PASS | every public name and method has `>>>` (`test_docs`); module doctests, GUIDE `pycon` blocks and README code run by the suite |
| 4 | Typed end to end | PASS | `mypy --strict src tests` clean; `py.typed` shipped; outside strict consumers clean (lenses a and d); only `to_numpy()` returns `Any`, documented |
| 5 | Typed, documented, safe errors | PASS | GUIDE error table; file text quoted to 40 characters (the end of a .tdx name), caller paths in full, CLI messages cut at 300; system failures propagate unchanged |
| 6 | Contract asserts the full promise | PASS | 411 tests: promises per public name, every LabVIEW capture and NI probe against NI's recorded reading, hostile input, CLI in process and by subprocess, and the contracts from the review rounds |
| 7 | Real ground truth | PASS | files LabVIEW 2026 wrote (two shipped examples and its TDMS-to-TDM converter), 56 probes, NI's own reading of all of them recorded (`ni_view.json`); lens b compared about 850,000 values against NI's DataStore reading over ten rounds |
| 8 | Real e2e incl. PyPI upgrade | PASS | wheel built and installed in clean venvs, console script and `python -m` by subprocess, suite from the sdist with `src` removed against the wheel; PyPI 0.2.1 upgraded in place with every difference documented (lens d) |
| 9 | Seeded fuzz, no crash, hang or blow-up | PASS | seeded mutation tests in the suite; lens c rounds with more than 60,000 fuzz cases, scaling of every input dimension linear, value allowance bounding generated, scaled and stored values |
| 10 | Every interpreter | PASS | 3.10.22, 3.11.17, 3.12.15, 3.13.16, 3.14.2/3.14.6 and 3.14.8t from the installed wheel (lens d round 3: 366 or 367 passed); this PC's 3.13.2 runs the gates |
| 11 | README | PASS | `twine check --strict` passed; absolute links; problem, verified why (tdm-loader and TDMtermite checked on PyPI), install, quick start, GUIDE and CHANGELOG links |
| 12 | CHANGELOG dated 1.0.0 | PASS | `## [1.0.0] - 2026-10-15` with the stable surface and every behaviour change |
| 13 | pyproject | PASS | 1.0.0, Production/Stable, 3.10 to 3.14, MIT, Homepage/Source/Issues/Changelog, keywords, `dependencies = []` (contract-tested) |
| 14 | sdist and wheel contents | PASS | wheel: package, `py.typed`, LICENSE; sdist: source, tests with fixtures and manifests, the two fixture scripts, docs; NI SineData samples never shipped (manifest and fetch script only) |
| 15 | Gates exit 0 alone | PASS | `ruff format --check .`, `ruff check .`, `mypy --strict src`, `pytest` each exit 0 alone |
| 16 | Independent reviewer | see below | |
| 17 | PR, trace guard | ready | PR #4 from `release/1.0.0`, trace guard CLEAN; merge and PyPI publish left to the maintainer |
| 18 | Mutation round | PASS | independent reviewer: round 1, 48 mutations, 43 killed, 4 closed by `tests/test_contract_review.py`, 1 equivalent; round 2, the 48 re-applied plus 36 new, 12 closed by `tests/test_contract_review_two.py`; round 3, all 84 re-applied plus 36 new, 8 closed by `tests/test_contract_review_three.py`, 1 equivalent; author: 55 mutations, 55 killed after 5 contracts; blind lens e round 1: 96 mutations, 23 survivors closed by `tests/test_contract_strength.py`, 2 equivalent; blind lens e round 2 on the final source: 131 mutations, 108 killed, 16 closed by `tests/test_contract_strength_two.py`, 7 equivalent |
| 19 | Five QA lenses | PASS | a (round 5), b (round 10), c (round 6), d (round 3), e (round 2) all PASS after every finding was fixed and re-verified |

## Baseline on 0.2.1 (before any change)

| Command | Result |
| --- | --- |
| `ruff format --check .`, `ruff check .`, `mypy --strict src tests` | exit 0 |
| `pytest` | 43 passed (the fetched upstream samples present) |
| `pytest --doctest-modules src` | no doctests at all |

## Ground truth (item 7)

`tests/fixtures/labview2026/` holds what LabVIEW 2026 Community 26.3.1f1 wrote on this PC
on 2026-10-14, run headless through LabVIEW's ActiveX server: the output of the shipped
examples `Write TDM Channel Groups.vi` and `Write TDM Event Data.vi` (doubles, a 32-bit
integer channel, an inline string channel, waveform properties), and the output of
LabVIEW's `Convert to TDM or TDMS.vi` for a TDMS file whose every value is chosen in
`scripts/make_tdms_source.py` (every integer and float type with extremes, signed zero,
non-finite values, strings with XML-special characters, times, typed properties).
`manifest.json` records how each file was made, its size and SHA-256.

`tests/fixtures/ni_probes/` holds 56 hand-made probes (`scripts/make_ni_probes.py`,
regenerated byte-identical), one layout question each. For every file in both folders
`ni_view.json` records how NI's software read it, through NI's USI DataStore COM API and
through LabVIEW's converter to TDMS read back with npTDMS (`scripts/capture_ni.py`). The
tests compare every channel of every file with NI's reading; the deliberate differences are
listed in GUIDE.md and pinned by `tests/test_ni_probes.py`. The NI schema installed with
LabVIEW (`UsiCore/DataModels/USI/1_0/usi_1_0.xsd`) was read for element and value type
names; no NI text is in the repository.

Defects of 0.2.1 found against NI's reading:

- `eInt8Usi` was decoded as a signed byte; NI writes it for `DT_BYTE` and reads 0xFF as 255
  (LabVIEW's own converter output `gt_types_0` has such a channel).
- String channels (LabVIEW's Event Data example writes one) came back as an empty tuple;
  so did every inline value and any reference to a missing block.
- Time channels (`eTimeUsi`) were refused.
- `implicit_linear` with one parameter used an increment of 1 (NI: a constant), without
  parameters produced `0, 1, 2, ...` (NI: start and increment from the first stored
  values, as in the TDMtermite `SineData_implicit` sample), and preferred
  `NI_ChannelLength` over the row count (NI uses the row count). `implicit` was accepted
  (NI reads nothing).
- Malformed XML leaked `ParseError`; any XML file read as an empty dataset; a header could
  point the reader at any file on disk through its `url`; the whole `.tdx` was loaded.
- `tdmread dump -f json` wrote `NaN` and `Infinity`, which are not JSON.

## API review (item 1)

The nine public names of 0.2.1 are kept with their signatures and defaults. Additions:
`properties` on `TdmFile`, `Group` and `Channel` (read-only, hashable, picklable mapping),
and `Channel.numbers()`, `strings()` and `times()` (typed views of `data`). `Channel.data`
is typed `tuple[float, ...] | tuple[str, ...] | tuple[datetime, ...]`. Every behaviour
change is in CHANGELOG 1.0.0 and in GUIDE.md "Upgrading from 0.2".

## Author mutation round (item 18)

Each mutation was applied alone to a fresh clone on the laptop, `__pycache__` purged, no
bytecode written, the suite run with `-x` (all but `tests/test_e2e.py`; the command line is
covered in process), and the file restored; the suite was green before and after. The
first run (55 mutations at dcbf3a3) left five survivors: the `eStringUsi` refusal (it fell
through to the generic refusal), the stored-value fallback (only the fetched upstream
sample covered it), the `..` check (a test matched "outside" in its own temporary path),
the drive check (equivalent: the `:` and absolute-path checks already refuse drives, so it
was removed), and the command's 300-character cut (library messages are already bounded).
Contracts were added in 6eeda2b and M34 now mutates the `:` check. The table is the final
run at 6eeda2b: 55 mutations, 55 killed. The code changed after it in response to the lenses; the
blind lens e round 2 and the independent reviewer's round cover the final source.

| Id | Mutation | File | Result | Caught by |
| --- | --- | --- | --- | --- |
| M01 | eInt8Usi read signed | `_binary.py` | killed | `tests/test_labview_captures.py::test_every_channel_holds_what_nis_reader_returns[gt_types_0.tdm]` |
| M02 | eSInt8Usi read unsigned | `_binary.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p01_bytes.tdm]` |
| M03 | eUInt16Usi read signed | `_binary.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p02_ints.tdm]` |
| M04 | eInt64Usi read unsigned | `_binary.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p02_ints.tdm]` |
| M05 | big endian read little | `_binary.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p04_bigendian.tdm]` |
| M06 | time fields swapped (little) | `_times.py` | killed | `tests/test_cli.py::test_channels_shows_units` |
| M07 | big-endian time fraction first | `_times.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p05_time_be.tdm]` |
| M08 | fraction scaled wrong | `_times.py` | killed | `tests/test_cli.py::test_dump_csv_writes_text_and_times` |
| M09 | epoch 1970 | `_times.py` | killed | `tests/test_cli.py::test_dump_csv_writes_text_and_times` |
| M10 | time range check dropped | `_times.py` | killed | `tests/test_hostile.py::test_times_outside_the_datetime_range_raise[4611686018427387904]` |
| M11 | ISO fraction cut to 5 digits | `_times.py` | killed | `tests/test_docs.py::test_module_doctests_pass[tdmread._times]` |
| M12 | span one byte short | `_binary.py` | killed | `tests/test_cli.py::test_info_reports_metadata_and_groups` |
| M13 | interleave stride ignored | `_binary.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p08_bm_c_0_12.tdm]` |
| M14 | blockOffset ignored | `_explicit.py` | killed | `tests/test_ni_probes.py::test_probes_nothing_sound_can_be_read_from_raise[p08_bm_b_8_12.tdm]` |
| M15 | small blockSize accepted | `_explicit.py` | killed | `tests/test_hostile.py::test_bad_blocks_raise_quickly_with_short_messages[<block_bm` |
| M16 | plain block honours blockSize | `_explicit.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p08_blk_blocksize.tdm]` |
| M17 | empty-block shortcut off by one | `_explicit.py` | killed | `tests/test_hostile.py::test_bad_blocks_raise_quickly_with_short_messages[<block` |
| M18 | missing sequence read as empty | `_explicit.py` | killed | `tests/test_hostile.py::test_a_missing_value_sequence_or_block_reference_raises` |
| M19 | missing block read as empty | `_explicit.py` | killed | `tests/test_hostile.py::test_bad_blocks_raise_quickly_with_short_messages[]` |
| M20 | eStringUsi not refused | `_explicit.py` | killed after a new contract | `tests/test_hostile.py::test_unsupported_layouts_say_so` |
| M21 | inline split on spaces only | `_inline.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p03_inline_06.tdm]` |
| M22 | inline strings stripped | `_inline.py` | killed | `tests/test_cli.py::test_dump_csv_writes_text_and_times` |
| M23 | integer tokens accept decimals | `_numbers.py` | killed | `tests/test_ni_probes.py::test_probes_nothing_sound_can_be_read_from_raise[p03_inline_13.tdm]` |
| M24 | float tokens via float() | `_numbers.py` | killed | `tests/test_hostile.py::test_bad_inline_values_raise[double_sequence-1_000]` |
| M25 | one parameter adds 1 | `_sequence.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p07_c_constant.tdm]` |
| M26 | linear starts one step late | `_sequence.py` | killed | `tests/test_implicit.py::test_generates_offset_and_increment` |
| M27 | no stored-value fallback | `_sequence.py` | killed after a new contract | `tests/test_promises.py::test_missing_generation_parameters_come_from_the_first_stored_values` |
| M28 | NI_ChannelLength before rows | `_sequence.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p10_implen_0.tdm]` |
| M29 | allowance not consumed | `_sequence.py` | killed | `tests/test_hostile.py::test_generated_channels_share_one_allowance` |
| M30 | raw scaling swapped | `_sequence.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p07_d_raw_linear_1_05.tdm]` |
| M31 | missing representation unsupported | `_sequence.py` | killed | `tests/test_cli.py::test_unicode_survives_a_file_and_a_narrow_console` |
| M32 | implicit_constant dropped | `_sequence.py` | killed | `tests/test_ni_probes.py::test_probes_read_as_nis_reader_reads_them[p07_c_constant.tdm]` |
| M33 | parent steps allowed | `_tdx.py` | killed after a new contract | `tests/test_promises.py::test_a_tdx_outside_the_header_folder_is_refused[../x.tdx]` |
| M34 | URL schemes allowed | `_tdx.py` | killed after a new contract | `tests/test_promises.py::test_a_tdx_outside_the_header_folder_is_refused[file:x.tdx]` |
| M35 | DTD accepted | `_reader.py` | killed | `tests/test_hostile.py::test_text_that_is_not_a_tdm_header_raises_tdm_error[<?xml` |
| M36 | any XML root accepted | `_reader.py` | killed | `tests/test_hostile.py::test_text_that_is_not_a_tdm_header_raises_tdm_error[<svg/>]` |
| M37 | unknown encoding leaks | `_reader.py` | killed | `tests/test_hostile.py::test_seeded_byte_mutations_of_real_files_raise_only_tdm_errors[0]` |
| M38 | last property name wins (the rule at the time; the shipped rule is now last wins) | `_props.py` | killed | `tests/test_model.py::test_properties_are_typed_at_every_level_and_the_first_name_wins` (since renamed) |
| M39 | string parts joined without newline | `_props.py` | killed | `tests/test_model.py::test_properties_are_typed_at_every_level_and_the_first_name_wins` |
| M40 | byte properties stay text | `_props.py` | killed | `tests/test_labview_captures.py::test_converted_types_hold_the_values_written_into_the_source` |
| M41 | bool counted as number | `_channel.py` | killed | `tests/test_model.py::test_typed_accessors_return_the_data_or_refuse_another_kind` |
| M42 | quotes unbounded | `_errors.py` | killed | `tests/test_hostile.py::test_bad_blocks_raise_quickly_with_short_messages[<block` |
| M43 | CLI messages unbounded | `_cli_output.py` | killed after a new contract | `tests/test_cli.py::test_a_huge_name_is_cut_in_the_message` |
| M44 | CLI data error exits 2 | `_cli.py` | killed | `tests/test_cli.py::test_errors_go_to_stderr_with_exit_one[args0]` |
| M45 | interrupt exits 1 | `_cli.py` | killed | `tests/test_cli.py::test_an_interrupt_exits_130` |
| M46 | JSON non-finite kept | `_cli_output.py` | killed | `tests/test_cli.py::test_dump_json_writes_every_kind_as_valid_json` |
| M47 | short tdx accepted | `_tdx.py` | killed | `tests/test_hostile.py::test_bad_blocks_raise_quickly_with_short_messages[<block` |
| M48 | group lookup returns last | `_model.py` | killed | `tests/test_model.py::test_group_and_dataset_lookups_iteration_and_errors` |
| M49 | tdx opened without blocks | `_reader.py` | killed | `tests/test_docs.py::test_module_doctests_pass[tdmread._reader]` |
| M50 | CSV times as str() | `_cli_output.py` | killed | `tests/test_cli.py::test_dump_csv_writes_text_and_times` |
| M51 | eTimeUsi item size 8 | `_binary.py` | killed | `tests/test_hostile.py::test_times_outside_the_datetime_range_raise[4611686018427387904]` |
| M52 | float32 read as float64 | `_binary.py` | killed | `tests/test_labview_captures.py::test_every_channel_holds_what_nis_reader_returns[gt_types_0.tdm]` |
| M53 | property raw-text fallback raises | `_props.py` | killed | `tests/test_model.py::test_properties_are_typed_at_every_level_and_the_first_name_wins` |
| M54 | header overrides tdx_path | `_tdx.py` | killed | `tests/test_promises.py::test_tdx_path_overrides_the_header` |
| M55 | inline time not parsed | `_inline.py` | killed | `tests/test_hostile.py::test_bad_inline_values_raise[time_sequence-2026-02-30T00:00:00]` |

## QA lenses (item 19)

Each lens was a fresh reviewer that read the certification rules first, worked in its own
clone, ran things rather than reading, and reported back privately. From 2026-10-15 only one
reviewer ran at a time. Heavy runs went to the laptop or the second build machine.

| Lens | Round | Head | Verdict | Findings and outcome |
| --- | --- | --- | --- | --- |
| a | 1 | afe7b45 | FAIL | .tdx url text leaked into long untyped errors; `dump` output corrupt on a non-UTF-8 console; upgrade notes incomplete; `channels` showed `explicit` as a type. Fixed in a410a2d |
| a | 2 | 020a62e | FAIL | two missing upgrade notes (`LookupError`, `struct.error`), missing-.tdx message hid the name, invalid names reported as outside the folder, path wording. Fixed in 4937b98 and 55f77de |
| a | 3 | 55f77de | FAIL | a url starting with a backslash escaped the header folder on Windows; a .tdx folder raised `PermissionError`; .tdx labels cut. Fixed in e5a4df0 |
| a | 4 | e5a4df0 | FAIL | a long caller path was cut in messages; every OSError opening the .tdx became `TdmError`; folder case missing from the upgrade notes. Fixed in d994cb1 |
| a | 5 | d994cb1 | PASS | three low notes on wording, addressed in b7828e2 |
| b | 1 | afe7b45 | FAIL | .tdx and header times cut instead of rounded as NI does (3936 of 5000 LabVIEW times 1 us low); inline bytes, floats and multi-part string properties read differently from NI. Fixed in 0e4822f |
| b | 2 to 9 | 2182cac to ad35584 | FAIL | NI's exact rules at the edges: no carry past the second, header times read through a double, integers clamped to 32 bits before narrowing, last property wins, any digit count; then documentation of NI's lenient text reading. Fixed in 6df10da, 90d7c95, 885363c, f938d64, 1e023d3, 8b57baa, cbceb0e, ad35584, 020a62e |
| b | 10 | 020a62e | PASS | every statement about NI behaviour and every accepted form checked against NI's reading |
| c | 1 | afe7b45 | FAIL | quadratic work on shared references, `ValueError` from odd encodings, raw `OSError` from hostile .tdx names, closed streams. Fixed in 3ee5c01 |
| c | 2 | 0e4822f | FAIL | overlapping blocks multiplied header and .tdx size; repeated groups; shared generated column lengths; names with control characters. Fixed in 52c0d84 |
| c | 3 | 52c0d84 | FAIL | the allowance rejected real raw_linear files; sparse block_bm read whole spans; padded shared columns rescanned. Fixed in 39d9d52 |
| c | 4 and 5 | 39d9d52, 6d4e461 | FAIL | Windows reports a vanished pipe reader as EINVAL; argparse paths and stderr kept exit 120. Fixed in 6d4e461 and 251c99a |
| c | 6 | 251c99a | PASS | 416 subprocess runs over closed streams, 4,000 fuzz cases, spot checks of all earlier fixes |
| d | 1 | afe7b45 | FAIL | three behaviour changes missing from the upgrade notes. Fixed in 93df864 |
| d | 2 | b7828e2 | FAIL | Python 3.10 argparse did not ignore failed usage writes (exit 1 instead of 2); fixture scripts missing from the sdist. Fixed in 55fd275 |
| d | 3 | 55fd275 | PASS | 3.10 to 3.14t from the installed wheel; two low notes (descriptor closed inside the process, `channels` type of generated channels) fixed in c0f03f6 |
| e | 1 | afe7b45 | PASS with contracts | 96 blind mutations, 23 survivors closed by `tests/test_contract_strength.py`, 2 equivalent |
| e | 2 | c0f03f6 | PASS with contracts | 131 blind mutations on the final source, 16 survivors closed by `tests/test_contract_strength_two.py` (1d08d5d), 7 equivalent with proofs |

## Decisions for the maintainer

- Behaviour changes against PyPI 0.2.1 are all listed in CHANGELOG 1.0.0 and GUIDE "Upgrading
  from 0.2". The ones most likely to matter: `eInt8Usi` is unsigned (255, not -1); string,
  time and inline values are now read; `implicit_linear` follows NI's rules; a .tdx outside
  the header's folder is refused; malformed input raises `TdmError` instead of other types;
  `dump -f json` writes valid ASCII JSON.
- Where NI's two readers or NI's lenient text parsing disagree with a sound reading, tdmread
  is stricter or exact, and GUIDE "Where tdmread differs" lists every case found.
- `block_mr` layouts are refused: NI's own readers disagreed on them when probed.
- The value allowance (ten million plus one per .tdx byte, per account) protects against
  tiny headers asking for gigabytes; a huge implicit-only file would hit it.
- The fixtures in `tests/fixtures/labview2026` are LabVIEW 2026 output made on this PC and
  NI's recorded reading of it; they ship in the sdist with their manifests. No NI text is in
  the repository; the NI SineData samples stay out (manifest and fetch script only).
- The README links to GUIDE.md and CHANGELOG.md on `main`: publish only after merging.
- The sdist carries `.gitignore` (hatchling always adds it).
- GUIDE.md and this report are longer than 200 lines; the limit applies to source files.

## Independent reviewer (item 16)

| Review | Head | Verdict | Findings and outcome |
| --- | --- | --- | --- |
| 1 | ebceaf2 | FAIL (items 6 and 18) | items 1 to 5, 7 to 15 and 19 PASS; 48 mutations of its own, 43 killed, 1 equivalent (the UTF-16 big-endian DTD mark), 4 survived (missing byteOffset, a sequence without values, a one-byte past-end check, the 40-character quote); its 4 contracts added in `tests/test_contract_review.py`; CHANGELOG line for `to_list()`, stale process note removed, author table note. Fixed in the next commit |
| 2 | db6783f | FAIL (items 6 and 18) | the four round-1 survivors killed; 36 new mutations, 24 killed, 12 survived (ENAMETOOLONG mapping, exact 40-character quote, 7-digit exponents, first child match, 40-digit counts, unnamed and non-`<s>` properties, bare ENTITY, first `tdm_root`, missing group, value type of empty blocks, allowance off by one); its 11 contracts added in `tests/test_contract_review_two.py`. Suite on 3.11.5, 3.13.2 and 3.14.2t, wheel e2e, gates and hygiene PASS |
| 3 | c6b3e62 | FAIL (items 6 and 18) | all 84 earlier mutations killed or equivalent; 36 new, 27 killed, 1 equivalent, 8 survived (floats like `.5`, stripped header text, padded attributes, a shrinking `.tdx`, missing block length, group description, dataset datetime, unit escaping); its 8 contracts added in `tests/test_contract_review_three.py`. Gates, hygiene and counts PASS |

# tdmread 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.1, a646185)
- [x] Baseline gates run on 0.2.1
- [x] Real LabVIEW 2026 output and NI reader captures (item 7)
- [x] API review and 1.0.0 API changes (item 1)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e and upgrade from PyPI 0.2.1 (items 8, 10, 13, 14)
- [ ] Independent reviewer and five QA lenses report PASS (items 16, 19)
- [ ] Gates (item 15)
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Baseline on 0.2.1 (before any change)

| Command | Result |
| --- | --- |
| `ruff format --check .`, `ruff check .`, `mypy --strict src tests` | exit 0 |
| `pytest` | 43 passed (the fetched upstream samples present) |
| `pytest --doctest-modules src` | no doctests at all |

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
| M38 | last property name wins | `_props.py` | killed | `tests/test_model.py::test_properties_are_typed_at_every_level_and_the_first_name_wins` |
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

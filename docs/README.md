# Documentation Index

This directory contains design notes and operating guides for
`C:\price_system_listing`.

## Start Here

- `rakuten_listing_developer_guide.md`
  - Canonical guide for the Rakuten listing flow.
  - Includes file locations, API specification sources, command flow, payload
    rules, DB sync, and troubleshooting.

- `rakuten_listing_standard_operation.md`
  - Short standard-operation note.
  - Use when you only need the normal pilot sequence and image-count policy.

- `rakuten_listing_pilot_checklist.md`
  - Short checklist before a real one-item pilot.
  - The top section is current. The lower original section is historical.

## Reference Notes

- `legacy_rakuten_listing_spec.md`
  - Early legacy workbook and master-file reverse-engineering notes.
  - Historical context only; current behavior is in the developer guide.

- `allowed_phrase_migration_candidates.md`
  - Investigation notes for migrating legacy prohibited-word spacing rules to
    allowed phrase masking.

- `legacy_comparison_input_spec.md`
  - Input format for legacy baseline comparison and offline sample work.

- `rakuten_price_system_design.md`
  - Price and inventory update design notes.
  - The top section is current; old mojibake text is retained only as history.

## Non-Markdown Notes

- `旧システム実行結果.txt`
  - Raw notes from legacy-system execution results.

## Source Of Truth

For RMS WEB SERVICE API behavior, use:

- `reference/rakuten_api/spec_pages/`

For legacy listing masters, use:

- `reference/legacy_listing/`


# CLI Workflow

`trackloom` is designed around a safe merge workflow:

1. Run `compare` to inspect exact matches, fuzzy matches, and recommended actions.
2. Run `plan` to generate copy/add operations.
3. Run `review` if any items require manual decisions.
4. Run `apply --dry-run` to inspect the final operations.
5. Run `apply --yes` when ready.

## Common commands

```bash
trackloom parse /path/to/library_a
trackloom parse /path/to/library_a /path/to/library_b
trackloom compare /path/to/library_a /path/to/library_b
trackloom plan /path/to/library_a /path/to/library_b
trackloom review /path/to/library_a /path/to/library_b
trackloom apply /path/to/library_a /path/to/library_b
trackloom doctor
trackloom help
trackloom help-advanced compare
```

## Happy path

```bash
trackloom compare /path/to/A /path/to/B --json > /tmp/compare.json
trackloom plan /path/to/A /path/to/B --write-plan-json /tmp/plan.json
trackloom review /path/to/A /path/to/B --decisions-file /tmp/decisions.json \
  --write-plan-json /tmp/reviewed-plan.json
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --dry-run
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --yes
```

If `trackloom` is not on your `PATH` yet:

```bash
python3 -m trackloom.cli help
```

## Key options

- `--json`: emit machine-readable output
- `--progress`: show live scan progress on stderr
- `--extensions .mp3 .flac .m4a .ogg .wav`: restrict scanned formats
- `--mode {standard,plex}`: filter operations by compatibility mode

Advanced tuning flags are hidden from default help output. Use
`trackloom help-advanced <command>` for the full option set.

## Compare

`compare` reports:

- exact matches on canonical key `artist + album + song`
- tracks only in A and only in B
- fuzzy candidates and fuzzy rejections
- duplicate policy classification:
  - `likely_duplicate`
  - `version_conflict`
  - `duration_conflict`
- recommended actions:
  - `add_to_b`
  - `replace_in_b_with_a`
  - `keep_b`
  - `keep_both_versions`
  - `manual_review`

Tuning flags:

- `--fuzzy-threshold` default `0.75`
- `--close-duration-seconds` default `1.0`
- `--duration-conflict-seconds` default `5.0`
- `--min-song-sim` default `0.82`
- `--min-artist-sim` default `0.65`
- `--top-k` default `20`

## Plan

`plan` creates a copy/add operation list to bring tracks from A into B:

- includes operations for `add_to_b`, `replace_in_b_with_a`, and `keep_both_versions`
- never deletes files
- deconflicts destination filenames if needed with `"(from A)"` suffixes
- supports `--write-plan-json <file>` for later `review` or `apply`
- in `plex` mode, incompatible operations are filtered and reported

Example:

```bash
trackloom plan /path/to/A /path/to/B --write-plan-json /tmp/plan.json --json > /tmp/plan.out.json
```

## Review

`review` processes `manual_review` items interactively:

- `--page-size` controls paging
- `--max-manual-items` caps manual-review session size
- `--start-index` resumes from a specific item
- `--decisions-file` loads and autosaves decisions
- `--export-manual-review-json` writes manual-review details
- `--write-plan-json` saves the reviewed plan

Typical flow:

```bash
trackloom review /path/to/A /path/to/B \
  --page-size 20 \
  --max-manual-items 1000 \
  --decisions-file /tmp/review-decisions.json \
  --write-plan-json /tmp/reviewed-plan.json
```

## Apply

`apply` executes plan copy operations:

- `--dry-run` simulates operations with no writes
- `--from-plan-json <file>` applies a saved plan
- `--report-json <file>` writes a full run report
- `--report-csv <file>` writes per-operation results
- `--cleanup-mode none` disables quarantine cleanup
- `--quarantine-dir <dir>` overrides the default quarantine location

Safety behavior:

- default behavior asks for confirmation before writing files
- `--yes` enables non-interactive apply
- with `--yes` and real writes, an extra safeguard confirmation is required unless `--force` is set
- per-operation I/O failures are reported and the run continues

Examples:

```bash
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --dry-run
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --yes
trackloom apply /path/to/A /path/to/B --yes --cleanup-mode none
```

## Output notes

Path parsing assumes `artist/album/track.ext`. Two-level paths are treated as
`album/track.ext` with unknown artist.

Parsed fields include:

- `path_fields.*`
- `tag_fields.*`
- `normalized_path_fields.*`
- `normalized_tag_fields.*`
- `duration_seconds`
- fidelity-related metadata such as bitrate, sample rate, bit depth, channels, and codec
- `version_hints`

## Exit codes

- `0`: success
- `2`: blocked
- `3`: cancelled by user or safeguard confirmation

## Reports

`apply --report-json` includes:

- run metadata
- source linkage
- requested, executed, and skipped counts
- per-operation executed and skipped items

`apply --report-csv` includes:

- `status`
- `reason`
- `action`
- `source_path`
- `destination_path`
- quarantine-related fields

## Demo fixtures

```bash
python3 scripts/make_demo_data.py --force
trackloom parse demo_data/A --extensions .wav .mp3 .m4a .flac .m4p --json
```

Tagged `mp3`, `m4a`, and `flac` fixture generation requires `ffmpeg`.

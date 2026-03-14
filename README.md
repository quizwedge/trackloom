# trackloom

Step 1 CLI for comparing audio libraries by first extracting normalized
`artist`, `album`, and `song` from:

- file paths
- embedded metadata tags (ID3/Vorbis/MP4 tags via `mutagen`)
- audio duration in seconds (from metadata when available)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -e .
```

If editable install still fails on older `pip`, run:

```bash
python3 -m pip install -e . --no-use-pep517
```

## Usage

```bash
trackloom parse /path/to/library_a
trackloom parse /path/to/library_a /path/to/library_b
trackloom compare /path/to/library_a /path/to/library_b
trackloom plan /path/to/library_a /path/to/library_b
trackloom apply /path/to/library_a /path/to/library_b
trackloom review /path/to/library_a /path/to/library_b
trackloom help
trackloom help parse
trackloom help compare
trackloom help plan
trackloom help apply
trackloom help review
```

Demo fixtures:

```bash
python3 scripts/make_demo_data.py --force
trackloom parse demo_data/A --extensions .wav .mp3 .m4a .flac .m4p --json
```

`ffmpeg` is required to generate tagged `mp3`, `m4a`, and `flac` demo fixtures.
Without `ffmpeg`, the generator still creates `wav` and `.m4p` demo files.

See `demo/README.md` for full demo commands.

## First Real Run

```bash
# 1) Compare and inspect
trackloom compare /path/to/A /path/to/B --json > /tmp/compare.json

# 2) Build a baseline plan
trackloom plan /path/to/A /path/to/B --write-plan-json /tmp/plan.json --json > /tmp/plan.out.json

# 3) Review manual-review items (paged), save reviewed plan + decisions
trackloom review /path/to/A /path/to/B \
  --page-size 20 \
  --max-manual-items 1000 \
  --decisions-file /tmp/review-decisions.json \
  --write-plan-json /tmp/reviewed-plan.json

# 4) Dry-run apply with reports
trackloom apply /path/to/A /path/to/B \
  --from-plan-json /tmp/reviewed-plan.json \
  --dry-run \
  --report-json /tmp/apply-dryrun.json \
  --report-csv /tmp/apply-dryrun.csv

# 5) Real apply (optional quarantine cleanup)
trackloom apply /path/to/A /path/to/B \
  --from-plan-json /tmp/reviewed-plan.json \
  --yes \
  --cleanup-mode move-to-quarantine \
  --quarantine-dir /path/to/quarantine \
  --report-json /tmp/apply.json \
  --report-csv /tmp/apply.csv
```

If the `trackloom` command is not on your PATH yet, run:

```bash
python3 -m trackloom.cli parse /path/to/library_a
python3 -m trackloom.cli parse /path/to/library_a /path/to/library_b
```

Optional flags:

- `--extensions .mp3 .flac .m4a .ogg .wav`
- `--json` to emit machine-readable JSON
- `--progress` to show live scan progress on stderr

`compare` also supports:

- `--fuzzy-threshold` (default `0.75`)
- `--close-duration-seconds` (default `1.0`)
- `--duration-conflict-seconds` (default `5.0`)
- `--min-song-sim` (default `0.82`)
- `--min-artist-sim` (default `0.65`)
- `--top-k` (default `20`, caps reported fuzzy candidates; dropped fuzzy-eligible pairs are excluded from `only_in_*` and counted in `fuzzy_dropped_count`)

`plan` uses the same fuzzy/duration tuning flags as `compare`.
`apply` uses the same fuzzy/duration tuning flags as `compare`.
`review` uses the same fuzzy/duration tuning flags as `compare`.
`plan`/`apply`/`review` support `--mode {standard,plex}` (default `standard`).

Synthetic tuning helper:

```bash
python3 scripts/tune_synthetic_thresholds.py
```

## Output shape

For each audio file in both directories, step 1 extracts:

- `path_fields.artist`
- `path_fields.album`
- `path_fields.song` (normalized to remove common track-number prefixes)
- `duration_seconds`
- `bitrate_kbps`
- `sample_rate_hz`
- `bit_depth`
- `channels`
- `codec`
- `tag_fields.artist`
- `tag_fields.album`
- `tag_fields.song`
- `normalized_path_fields.*` (casefolded; `-` and `_` replaced with spaces; extra whitespace collapsed)
- `normalized_tag_fields.*` (casefolded; `-` and `_` replaced with spaces; extra whitespace collapsed)
- `version_hints` (e.g. `live`, `remaster`, `radio_edit`, `acoustic`)

Path parsing assumes `artist/album/track.ext`. Two-level paths are treated as
`album/track.ext` (artist unknown).

## Compare Output

`compare` reports:

- exact matches on canonical key (`artist + album + song`, preferring normalized tag fields; requires all fields)
- tracks only in A
- tracks only in B
- fuzzy candidates scored from song similarity, artist similarity, and duration similarity
- fuzzy candidates are capped by `--top-k`; additional fuzzy-eligible pairs are counted
  as `fuzzy_dropped_count` and excluded from `only_in_*` results
- fuzzy rejections with score breakdown and rejection reasons (for threshold tuning)
- duplicate policy classification for matched pairs:
  - `likely_duplicate`
  - `version_conflict`
  - `duration_conflict`
- preferred side (`a`/`b`/`tie`) based on fidelity score (format + bit depth + sample rate + bitrate)
- recommended actions:
  - `add_to_b` for tracks only in A
  - `replace_in_b_with_a` when exact duplicates favor A's fidelity
  - `keep_b` when B is equal/better
  - `keep_both_versions` for version conflicts (for example remaster year mismatch)
  - `manual_review` for fuzzy matches and duration conflicts

Lossless vs lossy is treated as a hard boundary in preference logic.

## Plan Output

`plan` creates a copy/add operation list to bring tracks from A into B:

- includes operations for `add_to_b`, `replace_in_b_with_a`, and `keep_both_versions`
- never deletes files
- deconflicts destination filenames if needed (adds `"(from A)"` suffixes)
- use `--write-plan-json <file>` to save the plan for later review/apply
- in `--mode plex`, incompatible operations are filtered out and reported with skip reasons

To inspect Plex-skipped files (for example `.m4p`), run with JSON and check `mode_skipped_operations`:

```bash
trackloom plan /path/to/A /path/to/B --mode plex --json > /tmp/plan-plex.json
```

## Apply Output

`apply` executes the plan copy operations:

- default behavior asks for confirmation before writing files
- use `--yes` to auto-apply without prompt
- with `--yes` and real writes, an extra safeguard confirmation is required unless `--force` is set
- use `--dry-run` to simulate copy operations with no writes
- use `--from-plan-json <file>` to apply a previously saved `plan --json` result
- use `--report-json <file>` to save a full run report
- use `--report-csv <file>` to save per-operation results
- optional cleanup mode:
  - `--cleanup-mode move-to-quarantine --quarantine-dir <dir>`
  - only applies to `replace_in_b_with_a` actions
  - moves replaced B files to quarantine instead of deleting
- in `--mode plex`, incompatible operations are skipped before execution and included in output/report payloads
- per-operation copy/move failures are recorded as skipped `io_error` items and processing continues for remaining operations

`apply` prints a concise "planned changes in B" summary before confirmation.
Apply reports include source linkage metadata (`source_plan_json`, `source_decisions_file`) when available.

Safety guarantees:

- no file overwrite: existing destination files are skipped
- no delete operations are performed
- plan destinations are deconflicted when possible using `"(from A)"` suffixes
- plan JSON is validated: actions must be supported and paths must stay under `dir_a`/`dir_b`

Example reviewed workflow:

```bash
trackloom plan /path/to/A /path/to/B --write-plan-json /tmp/plan.json --json
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/plan.json --dry-run
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/plan.json --yes
trackloom apply /path/to/A /path/to/B --yes --report-json /tmp/apply.json --report-csv /tmp/apply.csv
trackloom apply /path/to/A /path/to/B --yes --cleanup-mode move-to-quarantine --quarantine-dir /path/to/quarantine
```

## Review Workflow

`review` is for `manual_review` items from compare logic:

- prompts for each item:
  - `add_to_b`
  - `replace_in_b_with_a`
  - `keep_b`
  - `keep_both_versions`
  - `skip`
- supports pagination via `--page-size` (default `20`)
- safety cap via `--max-manual-items` (default `1000`, set `0` for no cap)
- resume support via `--start-index` (1-based)
- `--export-manual-review-json <file>` writes candidate details + summary stats
- `--decisions-file <file>` loads prior decisions and autosaves after each change, on quit, and on completion
- review commands:
  - `n` next page
  - `p` previous page
  - `<index> <choice>` set action for an item (example: `3 r`)
  - `done` finish and build plan
- builds a reviewed plan containing only copy/add actions
- save with `--write-plan-json` and then run `apply --from-plan-json`
- when a reviewed plan is saved, CLI prints suggested next `apply` commands
- prints summary stats before interactive prompts (exact/fuzzy counts + policy counts)

Example:

```bash
trackloom review /path/to/A /path/to/B --write-plan-json /tmp/reviewed-plan.json
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --dry-run
trackloom apply /path/to/A /path/to/B --from-plan-json /tmp/reviewed-plan.json --yes
```

Resume review example:

```bash
trackloom review /path/to/A /path/to/B --decisions-file /tmp/review-decisions.json
```

## Exit Codes

- `0`: success
- `2`: blocked (for example `review` exceeded `--max-manual-items`)
- `3`: cancelled by user or safeguard confirmation

## Decision Glossary

- `add_to_b`: copy track from A into B.
- `replace_in_b_with_a`: A is preferred duplicate; copy A into B, optionally quarantine old B file.
- `keep_b`: keep B’s current track; no copy from A.
- `keep_both_versions`: keep both variants (for example version/remaster conflict).
- `manual_review`: ambiguous item requiring explicit choice.
- `duration_conflict`: durations differ by at least conflict threshold.
- `version_conflict`: version hints differ (for example `live` vs studio, or remaster year mismatch).
- `mode_skipped_operations`: operations filtered out by mode policy (for example Plex incompatibility).

## Report Schema

Apply JSON (`--report-json`) includes:

- run metadata (`timestamp_utc`, thresholds, cleanup mode)
- source linkage (`source_plan_json`, `source_decisions_file` when available)
- result counts (`requested_count`, `executed_count`, `skipped_count`)
- per-operation entries in `executed` and `skipped`

Apply CSV (`--report-csv`) columns:

- `status`, `reason`, `action`
- `source_path`, `source_relative_path`
- `destination_path`, `effective_destination_path`
- `quarantine_from`, `quarantine_to`, `quarantine_status`

## Performance Notes

- For large libraries, scan performance is optimized by filtering extensions during directory walk.
- Start with dry-run flows (`plan`, `apply --dry-run`) before real writes.
- Restrict `--extensions` to formats you actually store for faster scans.
- Manual-review scale is controlled via:
  - `--max-manual-items` guardrail
  - `--page-size` and `--start-index` for manageable sessions

## Troubleshooting

See `docs/TROUBLESHOOTING.md`.

## Community

- Contribution guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`
- Release checklist: `RELEASE.md`
- Architecture overview: `docs/ARCHITECTURE.md`
- Docs index: `docs/README.md`

## License

This project is licensed under the GNU General Public License v3.0 or later
(`GPL-3.0-or-later`). See `LICENSE`.

Copyright (C) 2026 Dan Getz, Jr.

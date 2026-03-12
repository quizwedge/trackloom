# AGENTS.md

Guidance for future coding sessions in this repository.

## Project Purpose

This project is a Python CLI for comparing two music libraries and safely merging tracks from library A into library B.

Primary commands:

- `parse`: catalog extracted fields
- `compare`: detect exact/fuzzy matches and recommended actions
- `plan`: build copy/add operation plan
- `review`: process `manual_review` items interactively
- `apply`: execute plan operations safely

## Core Workflow

Recommended sequence:

1. `compare` (`--json`) to inspect match quality and fuzzy rejections
2. `plan` (`--write-plan-json`) to generate baseline operations
3. `review` (with pagination + decisions persistence) for manual items
4. `apply --dry-run` with reports
5. `apply --yes` (optionally with quarantine cleanup)

## Safety Invariants (Do Not Break)

- No overwrite of existing destination files.
- No delete operations.
- Copy/add model by default.
- Optional cleanup is quarantine-only and only for `replace_in_b_with_a`.
- `apply` requires confirmation by default.
- `apply --yes` real writes require safeguard confirmation unless `--force`.
- `apply` is best-effort per operation: I/O failures are reported as skipped `io_error` entries and the run continues.

If changing safety behavior, add/update ADR(s) first.

## Current Decision Model

Canonical key:

- `artist + album + song` using normalized (casefolded) tag-first fallback to normalized path fields.

Duplicate policy highlights:

- Hard boundary: lossless preferred over lossy.
- Version conflicts keep both versions.
- Default duration thresholds:
  - close: `1.0s`
  - conflict: `5.0s` (`>=5.0s` is conflict/manual review)

Action labels:

- `add_to_b`
- `replace_in_b_with_a`
- `keep_b`
- `keep_both_versions`
- `manual_review`

Mode policy:

- `standard`: no mode-based operation filtering
- `plex`: only keep operations with Plex-compatible source media; incompatible operations are surfaced as `mode_skipped_operations`

## Review UX

Use these flags for large sessions:

- `--page-size`
- `--max-manual-items`
- `--start-index`
- `--decisions-file` (autosave/load)
- `--export-manual-review-json`
- `--write-plan-json`

## Reports and Audit

`apply` supports:

- `--report-json`
- `--report-csv`

Reports should preserve contract stability (see ADR 0015).

## Compatibility

- Python target: `>=3.8`.
- Use `python3` and `python3 -m pip ...`.

## Tests

Run full test suite:

```bash
python3 -m pytest -q
```

## Developer Tools

- Demo fixture generator:
  - `python3 scripts/make_demo_data.py --force`
  - full tagged `mp3/m4a/flac` fixtures require `ffmpeg`
- Synthetic tuning helper:
  - `python3 scripts/tune_synthetic_thresholds.py`

## Key Files

- CLI entrypoint + arg parser: `trackloom/cli.py`
- Command handlers:
  - `trackloom/commands/parse.py`
  - `trackloom/commands/compare.py`
  - `trackloom/commands/plan.py`
  - `trackloom/commands/review.py`
  - `trackloom/commands/apply.py`
- Command shared helpers: `trackloom/commands/common.py`
- Parsing: `trackloom/parser.py`
- Compare logic: `trackloom/compare.py`
- Planning: `trackloom/planner.py`
- Apply execution: `trackloom/apply_ops.py`
- Review helpers: `trackloom/review.py`
- Shared compare tuning config: `trackloom/config.py`
- Typed operation/result models: `trackloom/models.py`
- I/O helpers:
  - `trackloom/plan_io.py`
  - `trackloom/decision_io.py`
  - `trackloom/report_io.py`
- Tests: `tests/`
- Architecture decisions: `adr/`
- Architecture overview: `docs/ARCHITECTURE.md`

## ADR Requirement

Before introducing major behavior changes (matching policy, safety rules, apply semantics, report contracts), add/update ADRs in `adr/` and index them in `adr/README.md`.

## Maintenance Checklist (Do/Don't)

Do:

- Keep report schemas and exit-code meanings backward-compatible.
- Add/adjust tests for every policy, safety, or workflow behavior change.
- Update README and ADRs when defaults or command semantics change.

Don't:

- Weaken no-overwrite/no-delete guarantees without a new ADR.
- Change threshold/safety defaults silently.
- Introduce destructive cleanup behavior as default.

## Release Checklist

Before a real apply run on production libraries:

1. Run tests:
   - `python3 -m pytest -q`
2. Generate/update plan:
   - `plan --write-plan-json ...`
3. Complete manual review (if needed):
   - `review --write-plan-json ... --decisions-file ...`
4. Execute dry-run apply with reports:
   - `apply --dry-run --report-json ... --report-csv ...`
5. Confirm safety settings for real run:
   - confirmation flow (`--yes`/`--force`) intentionally chosen
   - quarantine mode/dir set if cleanup is desired
6. Execute real apply with reports enabled.
7. Archive outputs:
   - saved plan JSON
   - decisions JSON (if used)
   - apply report JSON/CSV

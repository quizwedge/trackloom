# Architecture

Trackloom is a local-first CLI for safe music-library merge planning.

## End-to-end flow

1. `parse`
- scans supported audio files
- extracts path fields + tag fields + quality metadata
- computes normalized fields and version hints

2. `compare`
- builds canonical keys (`artist + album + song`, normalized tag-first)
- classifies exact matches, only-in-A/B, and fuzzy candidates
- applies duplicate policy (version/duration/fidelity/lossless boundary)

3. `plan`
- converts compare results into copy-only operations
- deconflicts destination names
- filters operations by mode (`standard` / `plex`)

4. `review`
- presents `manual_review` items and records decisions
- emits reviewed plan payload

5. `apply`
- executes planned copy operations safely
- optional quarantine handling for replace actions
- emits JSON/CSV reports

## Safety invariants

- No overwrite of existing destination files.
- No delete operations.
- Copy/add model by default.
- Cleanup (if enabled) is quarantine-only for replace actions.
- Per-operation I/O failures are reported and processing continues.

## Module layout

- CLI entrypoint and arg parser:
  - `trackloom/cli.py`
- Command handlers:
  - `trackloom/commands/parse.py`
  - `trackloom/commands/compare.py`
  - `trackloom/commands/plan.py`
  - `trackloom/commands/review.py`
  - `trackloom/commands/apply.py`
- Command shared utilities:
  - `trackloom/commands/common.py`
- Shared compare tuning config:
  - `trackloom/config.py`
- Core domain logic:
  - parsing: `trackloom/parser.py`
  - comparison: `trackloom/compare.py`
  - planning: `trackloom/planner.py`
  - review helpers: `trackloom/review.py`
  - apply execution: `trackloom/apply_ops.py`
  - mode filtering: `trackloom/mode.py`
- Typed operation/result models:
  - `trackloom/models.py`
- JSON/CSV I/O:
  - `trackloom/plan_io.py`
  - `trackloom/decision_io.py`
  - `trackloom/report_io.py`

## Design notes

- Compare-tuning validation is centralized in `CompareConfig`.
- Command modules should remain thin orchestration layers; core behavior belongs in
  parser/compare/planner/review/apply modules.
- Behavior changes affecting safety or policy should be captured in ADRs.

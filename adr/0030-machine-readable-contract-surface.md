# 0030: Stable Machine-Readable Contract Surface

- Status: Accepted

## Context

Trackloom already relies on machine-readable artifacts and outputs for normal workflows:

- `plan --write-plan-json`
- `review --decisions-file`
- `review --write-plan-json`
- `apply --report-json`
- `apply --report-csv`
- `--json` outputs used by scripts and CI

Without an explicit contract definition, these outputs can drift even when the
documentation and workflow imply stability.

## Decision

Treat the following as stable machine-readable contracts:

- exit codes
- plan JSON written by `plan` and `review`
- decisions JSON written by `review`
- apply report JSON written by `apply --report-json`
- apply report CSV written by `apply --report-csv`
- top-level machine-readable `--json` payloads for `compare`, `plan`, `review`,
  `apply`, and `doctor`

Compatibility rules:

- existing required fields and field meanings must remain backward-compatible
- additive changes are allowed
- breaking changes require:
  - an ADR
  - updated docs
  - compatibility tests updated intentionally
- plan JSON uses explicit `schema_version`
- other machine-readable outputs are additive-only within the current major CLI contract
- human-readable text output is not part of the stable contract surface

Required testing posture:

- fixture-backed compatibility tests for persisted artifacts
- scenario-driven workflow tests for multi-command contract handoff
- explicit tests for Plex-mode `mode_skipped_*` machine-readable fields

## Consequences

- Safer automation and archival workflows.
- Future refactors must preserve documented field contracts.
- Tests should prefer key presence, type/meaning, and interoperability over exact
  pretty-print formatting.

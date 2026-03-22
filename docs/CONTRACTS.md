# Machine-Readable Contracts

This document defines the machine-readable outputs Trackloom treats as stable.

Human-readable CLI text is not part of this contract.

## Stable surfaces

- Exit codes:
  - `0`: success
  - `2`: blocked / precondition failure
  - `3`: user or safeguard cancellation
- Plan JSON written by:
  - `plan --write-plan-json`
  - `review --write-plan-json`
- Decisions JSON written by:
  - `review --decisions-file`
- Apply report JSON written by:
  - `apply --report-json`
- Apply report CSV written by:
  - `apply --report-csv`
- Top-level `--json` payloads for:
  - `compare`
  - `plan`
  - `review`
  - `apply`
  - `doctor`

Currently excluded:

- `parse --json`
  - it is machine-readable, but it is not yet treated as a hard compatibility
    contract and may evolve as parsing detail improves

## Compatibility policy

- Existing required keys and meanings are backward-compatible.
- New keys may be added.
- Existing keys should not be removed or repurposed without:
  - a new ADR
  - docs updates
  - intentional compatibility-test updates
- Plan JSON uses explicit `schema_version`.
- Decisions JSON supports both:
  - wrapped form: `{"decisions": {...}}`
  - legacy plain-object form: `{...}`

## Persisted artifact requirements

### Plan JSON

Top-level requirements:

- `operations`
- `schema_version` is written on new plans and accepted when missing on old plans

Per-operation required fields:

- `action`
- `source_path`
- `source_relative_path`
- `destination_path`

Optional compatibility-sensitive fields:

- `preferred_destination_path`
- `replace_target_path`
- `source_extension`
- `source_codec`

### Decisions JSON

Canonical form written by Trackloom:

```json
{
  "decisions": {
    "exact:abc123": "replace_in_b_with_a"
  }
}
```

### Apply report JSON

Contract-sensitive top-level fields:

- `dir_a`
- `dir_b`
- `planned_operation_count`
- `applied`
- `dry_run`
- `mode`
- `mode_skipped_count`
- `mode_skipped_operations`
- `from_plan_json`
- `run_metadata`
- `result`

### Apply report CSV

Column order is stable:

1. `status`
2. `reason`
3. `action`
4. `source_path`
5. `source_relative_path`
6. `destination_path`
7. `effective_destination_path`
8. `quarantine_from`
9. `quarantine_to`
10. `quarantine_status`

## Plex-mode contract notes

When `mode=plex`, machine-readable outputs that include operations should surface:

- `mode`
- `mode_skipped_count`
- `mode_skipped_operations`

Skip reasons are compatibility-sensitive for automation and troubleshooting.

## Enforcement

The test suite enforces this contract using:

- fixture-backed compatibility tests for persisted artifacts
- end-to-end scenario tests for workflow handoff
- focused mode and I/O contract tests
- CI review checks that treat changes under `tests/fixtures/contracts/` as
  contract changes requiring matching docs, ADR, and contract-test updates

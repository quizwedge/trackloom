# 0015: Reporting and Exit-Code Contract Stability

- Status: Accepted

## Context
Automation and operational workflows depend on predictable command outcomes and report schemas.

## Decision
Treat report outputs and exit codes as stable contracts:

- Exit codes:
  - `0`: success
  - `2`: blocked/precondition failure
  - `3`: user/safeguard cancellation
- Report JSON/CSV schemas are versioned implicitly by backward-compatible evolution.
- New fields may be added, but existing fields/meanings should not be broken without explicit migration notes.

## Consequences
- Safer CI/scripting integration.
- Requires discipline when evolving CLI/report behavior.

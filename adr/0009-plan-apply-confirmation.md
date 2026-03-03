# 0009: Plan/Apply Workflow with Confirmation by Default

- Status: Accepted

## Context
Need safe execution model for filesystem writes.

## Decision
Use staged workflow:
- `plan` generates operations
- `apply` executes with confirmation by default
- `--yes` supports non-interactive mode
- extra safeguard confirmation for `--yes` real writes unless `--force`

## Consequences
- Safer operational flow.
- Slightly more steps for fully automated runs.

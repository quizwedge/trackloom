# 0013: Manual Review UX: Pagination, Caps, Resume, Persistence

- Status: Accepted

## Context
Manual-review sets can be large and sessions can be interrupted.

## Decision
Provide review UX features:
- pagination (`--page-size`)
- safety cap (`--max-manual-items`)
- resume index (`--start-index`)
- decisions persistence (`--decisions-file` autosave/load)
- candidate export (`--export-manual-review-json`)

## Consequences
- Practical large-session review workflow.
- Slightly more CLI complexity.

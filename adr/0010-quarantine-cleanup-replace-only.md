# 0010: Optional Quarantine Cleanup for Replace Actions

- Status: Accepted

## Context
Copy-only avoids data loss but can leave clutter.

## Decision
Support optional cleanup mode: `move-to-quarantine`.
Apply only to `replace_in_b_with_a` actions. Move old B file to quarantine before copy.

## Consequences
- Reversible cleanup without delete risk.
- Requires quarantine storage management.

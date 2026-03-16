# 0027: Default Cleanup Mode Moves Replaced Files to Quarantine

- Status: Accepted

## Context
The primary workflow is to bring higher-quality tracks from A into B while preserving the ability to restore the original B files. Relying on users to opt into quarantine makes the default path less aligned with this goal.

## Decision
- Default `apply --cleanup-mode` to `move-to-quarantine`.
- When `--quarantine-dir` is not provided, use `<dir_b>/.trackloom_quarantine` as the default quarantine location.
- This behavior applies only to `replace_in_b_with_a` actions and preserves the no-delete invariant.

## Consequences
- Replacements become a safe default: the original B file is moved aside for easy restoration.
- Users can still opt out with `--cleanup-mode=none`.
- A default quarantine directory is created when needed.

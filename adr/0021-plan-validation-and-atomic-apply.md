# 0021: Plan Validation and Atomic Apply Safety

- Status: Accepted

## Context
`apply` can ingest plan JSON from disk. Previously, plan operations were not constrained
to `dir_a`/`dir_b`, and action values were not validated. This allowed edited or malformed
plans to copy files from/to arbitrary paths. Additionally, a failed copy could leave a
partial destination file behind, which would then block future runs. Quarantine paths
could also be flattened when `dir_b` was a symlink, losing the original relative layout.

## Decision
Before apply execution, validate plan operations:
- allowlist actions to `add_to_b`, `replace_in_b_with_a`, `keep_both_versions`
- require `source_path` to reside under `dir_a` and destination/preferred/replace paths
  to reside under `dir_b` (using resolved paths)
- for `replace_in_b_with_a`, require `preferred_destination_path` and
  `replace_target_path`, and they must resolve to the same path

During apply execution:
- copy to a temporary file in the destination directory and `os.replace` atomically
- clean up temp files on failure
- resolve paths when deriving quarantine destinations so symlinked `dir_b` preserves
  relative structure
- when a replace target no longer exists, prefer writing to
  `preferred_destination_path` if it is free

## Consequences
- Malformed or malicious plan JSON is rejected before any file operations occur.
- Partial copies are avoided, improving idempotence and safety.
- Quarantine paths remain stable even when `dir_b` is a symlink.
- Custom external plans must adhere to the allowed action set and root constraints.

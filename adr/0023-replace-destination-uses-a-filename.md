# 0023: Replace Destination Uses B Directory with A Filename

- Status: Accepted

## Context
Exact matches that prefer `replace_in_b_with_a` can involve different file extensions (for example, replacing an MP3 with a FLAC). The previous behavior used B's full relative path as the preferred destination, which could copy A's bytes into a filename with B's extension. That creates mismatches between content and filename and can confuse players or taggers. Additionally, when the preferred destination differs from the original B path, we must avoid silently keeping both files in B unless the user explicitly enables quarantine cleanup.

## Decision
- For `replace_in_b_with_a`, construct the preferred destination path using B's directory structure and A's filename (including extension).
- Keep `replace_target_path` pointing to the existing B file so optional quarantine can move it out safely.
- If the preferred destination differs from the replace target and the replace target exists, require `--cleanup-mode=move-to-quarantine` to proceed; otherwise skip the operation.
- Plan validation allows preferred destination paths that differ from replace targets as long as both are within B.

## Consequences
- Replacements keep A's extension and avoid mismatched file types.
- A rename-style replacement requires quarantine mode to avoid accidentally leaving two versions in B.
- Plan JSONs can express replacements where destination and replace target differ without failing validation.

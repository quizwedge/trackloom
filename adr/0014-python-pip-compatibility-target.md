# 0014: Python/Pip Compatibility Target

- Status: Accepted

## Context
The tool should run on older macOS environments where default Python/pip toolchains may be outdated.

## Decision
Target Python `>=3.8` and maintain compatibility with older pip workflows by supporting setuptools-based editable install fallback.

## Consequences
- Broader environment compatibility (including older macOS setups).
- Limits use of newer Python-only syntax/features unless guarded.

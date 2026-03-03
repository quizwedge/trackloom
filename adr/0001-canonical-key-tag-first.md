# 0001: Canonical Match Key Uses Tag-First Normalized Fields

- Status: Accepted

## Context
Matching two music libraries needs a canonical key resilient to path differences.

## Decision
Use canonical key: `artist + album + song`, preferring normalized tag fields and falling back to normalized path fields.

## Consequences
- Better semantic matching when folder names are inconsistent.
- Depends on tag quality; poor tags still require fallback/manual review.

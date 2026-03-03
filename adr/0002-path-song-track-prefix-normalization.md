# 0002: Parse Path Song Normalization for Track Prefixes

- Status: Accepted

## Context
Filenames often include track prefixes (`01 -`, `Track 09`, `CD1-03`).

## Decision
Normalize path-derived song title by stripping common leading track-number prefixes.

## Consequences
- Improves matching quality from filesystem-only metadata.
- Pattern-based normalization may miss rare naming conventions.

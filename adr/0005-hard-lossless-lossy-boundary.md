# 0005: Duplicate Policy Uses Hard Lossless-vs-Lossy Boundary

- Status: Accepted

## Context
Quality ranking should strongly prefer lossless sources in archival merge goals.

## Decision
Enforce hard preference: when one candidate is lossless and the other is lossy, prefer lossless regardless of numeric score.

## Consequences
- Predictable archival preference.
- Still subject to version conflict safeguards.

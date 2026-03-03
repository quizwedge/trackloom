# 0003: Keep Raw and Normalized Fields Separately

- Status: Accepted

## Context
Comparison needs normalized text, but auditing needs original values.

## Decision
Store both raw parsed fields and normalized fields instead of overwriting originals.

## Consequences
- Clear traceability during review.
- Slightly larger payloads.

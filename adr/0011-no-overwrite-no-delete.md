# 0011: No Overwrite/No Delete Safety Model

- Status: Accepted

## Context
High-safety behavior is required during merges.

## Decision
Do not overwrite existing destination files and do not delete files.
Skip existing destinations and use deconflicted names in plans where possible.

## Consequences
- Strong safety guarantees.
- Potential duplicate accumulation unless quarantine cleanup is used.

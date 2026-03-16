# 0024: Exact-Match Pairing Prioritizes Version Hints

- Status: Accepted

## Context
A canonical key can map to multiple files in both libraries (for example, live and studio versions). The previous exact-match pairing strategy matched items by index after sorting paths, which could pair mismatched versions when naming conventions differ. That can trigger incorrect actions such as replacing the wrong file or flagging version conflicts unnecessarily.

## Decision
When multiple items share a canonical key:
- Group items by their `version_hints` signature and pair items within matching signatures first.
- For remaining unmatched items, pair by closest duration difference (stable, deterministic tie-breaker).

## Consequences
- Exact matches are more likely to align the correct versions and avoid false version conflicts.
- Pairing remains deterministic and bounded by the small per-key lists, without adding global complexity.

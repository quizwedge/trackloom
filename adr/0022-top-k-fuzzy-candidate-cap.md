# 0022: Top-K Fuzzy Candidate Cap Is Display-Only

- Status: Accepted

## Context
`--top-k` limits the number of fuzzy candidates returned. Previously, any fuzzy-eligible
pair that fell outside the top-k list would be dropped and the corresponding files
would be classified as only-in-A/B, producing automatic add/keep actions. This made
`--top-k` a policy lever rather than a display cap and could create silent duplicates.

## Decision
- Compute all fuzzy-eligible pairs as usual.
- Keep only the top-k pairs for `fuzzy_candidates` and manual review.
- Exclude all fuzzy-eligible items (including those dropped by top-k) from
  `only_in_a` / `only_in_b` results.
- Track the number of dropped fuzzy-eligible pairs as `fuzzy_dropped_count`.

## Consequences
- `--top-k` is now a display/review cap, not a decision policy.
- Fewer automatic add/keep operations when fuzzy-eligible pairs exist.
- Users should increase `--top-k` to review more fuzzy candidates.

# 0020: Case-Insensitive Normalized Fields for Matching

- Status: Accepted

## Context
Exact matching relies on normalized tag/path fields. Normalization previously only replaced
separators and collapsed whitespace, leaving case differences intact. This caused exact
matches to be missed when the same artist/album/song differed only by casing, pushing
items into `only_in_*` or fuzzy/manual review.

## Decision
Normalize match fields using `casefold()` before separator and whitespace normalization.
Canonical keys and fuzzy comparisons continue to use normalized fields, so matching becomes
case-insensitive while preserving raw field values for display/reporting.

## Consequences
- Exact matching is case-insensitive and reduces false negatives.
- Output counts may change versus prior versions for libraries with inconsistent casing.
- Raw fields remain unchanged, so reports still reflect original metadata.

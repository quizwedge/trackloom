# 0019: Exact Matching Requires Complete Canonical Key

- Status: Accepted

## Context
Exact matching currently groups files by the canonical key `(artist, album, song)` using normalized tag-first fields. When any of these fields are missing, the key can collapse to `(None, None, None)`, which causes unrelated files to match exactly. This creates incorrect replace/keep actions and undermines safety expectations.

## Decision
Exact matching will only include items whose canonical key is fully populated (all three fields present). Items missing any canonical key field are excluded from exact matching and treated as unmatched candidates for fuzzy/manual review. They may still appear in `only_in_a` / `only_in_b` results with the usual add/keep recommendations.

## Consequences
- Reduces false exact matches for partially tagged files.
- Some items that previously matched exactly will now require manual review or remain unmatched.
- The comparison output may include more `manual_review` candidates and `only_in_*` entries for files with incomplete metadata.

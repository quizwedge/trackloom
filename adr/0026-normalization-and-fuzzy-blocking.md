# 0026: Normalize Ampersands/Punctuation and Block Fuzzy Matching

- Status: Accepted

## Context
Large libraries (thousands of tracks) make naive fuzzy matching expensive. In addition, common artist/title variants like "Lost & Found" vs "Lost and Found" should match reliably. The existing normalization only handled casefolding, whitespace, underscores, and hyphens, and fuzzy matching compared every unmatched A with every unmatched B.

## Decision
- Expand normalization used for matching to:
  - Replace `&` with `and`.
  - Replace non-word punctuation with spaces.
  - Keep casefolding and whitespace normalization.
- Introduce blocking for fuzzy matching:
  - Bucket candidates by the first alphabetic (or numeric) character of normalized artist and song.
  - Compare only within the union of artist+song, artist-only, and song-only buckets.

## Consequences
- Common variants like `&` vs `and` match more reliably.
- Fuzzy matching cost drops significantly for large libraries, with minimal loss of recall.
- Matching behavior changes should be noted in release notes and test coverage.

# 0006: Version Conflicts Keep Both Versions

- Status: Accepted

## Context
Different editions (live/remaster/edit/year variants) are distinct versions.

## Decision
When version hints conflict (including remaster year mismatches), classify as version conflict and recommend `keep_both_versions`.

## Consequences
- Prevents accidental replacement across editions.
- May increase retained duplicates intentionally.

# 0029: Version Hints Favor High Recall

- Status: Accepted

## Context
Version hints (e.g., live, remaster, edit, mono/stereo) are derived from file and tag text.
These hints influence duplicate policy decisions, including when to keep both versions or require manual review.
Missing real version hints is riskier than detecting extra hints because it can merge distinct versions.

## Decision
Favor high recall for version hint detection, accepting occasional false positives.
Heuristics may use broad substring matching and are allowed to over-fire when text is ambiguous.

## Consequences
- Safer outcomes: distinct versions are less likely to be merged as duplicates.
- Increased manual review or “keep both” outcomes in edge cases.
- Future tuning should preserve the recall-first intent unless superseded by a new ADR.

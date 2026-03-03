# 0007: Fuzzy Duration Defaults and Threshold Model

- Status: Accepted

## Context
Single duration threshold was too coarse for real-world variance.

## Decision
Use two thresholds:
- close duration seconds: default `1.0`
- conflict duration seconds: default `5.0` (>= conflict is duration conflict)

Use middle range for scoring and manual review behavior.

## Consequences
- Better control over false positives/negatives.
- Requires tuning per library characteristics.

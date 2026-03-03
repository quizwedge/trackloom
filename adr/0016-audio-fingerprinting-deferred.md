# 0016: Audio Fingerprinting Deferred

- Status: Accepted

## Context
Audio fingerprinting can improve duplicate detection across inconsistent metadata, but increases complexity and runtime significantly.

## Decision
Defer audio fingerprinting for now. Revisit after real-library runs and threshold tuning, using observed mismatch pain as trigger.

Trigger criteria to revisit:

- persistent high manual-review volume caused by metadata inconsistency
- frequent false non-matches across format/transcode variants
- clear operational need that metadata/duration/fuzzy heuristics cannot satisfy

## Consequences
- Faster delivery with simpler dependency/runtime model.
- Some edge-case duplicates may still require manual review until fingerprinting is added.

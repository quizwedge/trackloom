# 0028: Use RapidFuzz for Text Similarity Scoring

- Status: Accepted

## Context
Fuzzy matching relies on string similarity scoring. `difflib.SequenceMatcher` is correct but slow for large collections. RapidFuzz provides faster similarity metrics under the MIT license, which is compatible with GPLv3+.

## Decision
- Use `rapidfuzz.fuzz.ratio` for text similarity scoring.
- Add RapidFuzz as a required dependency.

## Consequences
- Fuzzy matching performance improves substantially on large libraries.
- Similarity scores may shift slightly compared to `SequenceMatcher`; thresholds may need minor tuning.

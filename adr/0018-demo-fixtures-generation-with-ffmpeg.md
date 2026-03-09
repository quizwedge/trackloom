# 0018: Demo Fixtures Use ffmpeg for Encoded Formats and mutagen for Tagging

- Status: Accepted
- Date: 2026-03-08

## Context

We want reproducible demo fixtures that exercise:

- path parsing and normalization
- tag parsing precedence
- codec/format-aware behavior
- Plex compatibility filtering (including `.m4p` skip behavior)

WAV fixtures are easy to generate with Python stdlib, but realistic `mp3`, `m4a`,
and `flac` fixtures require actual audio encoding.

## Decision

Demo fixture generation uses:

- `ffmpeg` to encode `mp3`, `m4a`, and `flac` audio files from a generated WAV source.
- `mutagen` to write tags into generated encoded files.
- fallback behavior: if `ffmpeg` is unavailable, encoded tagged fixtures are skipped
  with explicit console messages; base WAV and `.m4p` fixtures are still generated.

## Consequences

- Pros:
  - demo data better matches real-world media/container behavior
  - validates tag parsing across multiple formats
  - keeps generation deterministic and scripted
- Cons:
  - developer dependency on `ffmpeg` for full demo coverage
  - demo generation capability may vary by local environment


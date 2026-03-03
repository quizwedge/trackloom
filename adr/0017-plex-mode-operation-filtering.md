# 0017: Plex Mode Operation Filtering

- Status: Accepted

## Context
Users may want merge output constrained to media compatible with Plex playback/transcoding, while keeping standard mode unchanged.

## Decision
Add optional mode filtering to `plan`, `review`, and `apply`:

- `--mode standard` (default): no mode filtering
- `--mode plex`: keep only Plex-compatible operations and emit skipped items with reasons

Plex mode is intentionally less restrictive (play or transcode acceptable), but excludes obvious protected/incompatible sources (for example DRM-protected extensions/codecs).

## Consequences
- Safer library output for Plex ingestion.
- Some operations are filtered out and must be reviewed via mode-skip reporting.
- Standard mode behavior remains backward-compatible.

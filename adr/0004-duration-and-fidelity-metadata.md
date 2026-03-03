# 0004: Parse Duration and Fidelity Metadata

- Status: Accepted

## Context
Duplicate policy needs quality and timing signals beyond text similarity.

## Decision
Parse and store duration and fidelity metadata: extension/codec, bitrate, sample rate, bit depth, channels.

## Consequences
- Enables quality-aware decisions.
- Metadata availability varies by format/source.

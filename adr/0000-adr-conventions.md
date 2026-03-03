# 0000: ADR Conventions

- Status: Accepted

## Context
This repository uses Architecture Decision Records (ADRs) to capture durable engineering and product decisions made during implementation.

## Decision
Adopt the following ADR conventions:

- Numbering:
  - Sequential, zero-padded IDs (`0000`, `0001`, ...)
  - IDs are immutable after merge
- Filename format:
  - `<id>-<short-kebab-title>.md`
- Required sections:
  - `Status`
  - `Context`
  - `Decision`
  - `Consequences`
- Status values:
  - `Proposed`
  - `Accepted`
  - `Superseded by <id>`
  - `Deprecated`
- Change policy:
  - ADRs are append-only in spirit; update only for clarifications
  - If a decision changes materially, create a new ADR and reference the superseded ADR
- Scope:
  - Record decisions with medium/long-term impact on behavior, safety, workflow, or interfaces
  - Do not record trivial implementation details

## Consequences
- Decisions remain discoverable and reviewable over time.
- Contributors have a consistent template for future ADRs.

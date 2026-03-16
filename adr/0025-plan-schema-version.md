# 0025: Plan JSON Includes schema_version

- Status: Accepted

## Context
Plan JSON is a user-facing artifact that can be stored and reused. As the plan payload evolves, consumers need a stable way to detect breaking changes. Without a version field, old plans can be misinterpreted silently.

## Decision
- Include a top-level `schema_version` field in plan JSON outputs.
- Current version starts at `1`.
- Plan loading accepts missing `schema_version` for backward compatibility.
- Plan loading rejects `schema_version` values greater than supported.

## Consequences
- Tools can detect or gate on incompatible plan versions.
- Future breaking changes can increment `schema_version` without ambiguity.

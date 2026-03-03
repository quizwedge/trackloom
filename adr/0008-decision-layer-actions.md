# 0008: Decision Layer Action Labels

- Status: Accepted

## Context
Comparison output must map to operational merge actions.

## Decision
Emit explicit recommended actions:
- `add_to_b`
- `replace_in_b_with_a`
- `keep_b`
- `keep_both_versions`
- `manual_review`

## Consequences
- Enables plan/apply automation.
- Ambiguous cases still flow to manual review.

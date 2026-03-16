# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import hashlib
from typing import Any

from .planner import build_copy_plan

REVIEW_ACTIONS = {
    "add_to_b",
    "replace_in_b_with_a",
    "keep_b",
    "keep_both_versions",
    "skip",
}


def validate_manual_item_limit(total: int, max_manual_items: int) -> None:
    if max_manual_items < 0:
        raise ValueError("max_manual_items must be >= 0")
    if max_manual_items == 0:
        return
    if total > max_manual_items:
        raise RuntimeError(
            "Manual review items "
            f"({total}) exceed --max-manual-items ({max_manual_items})."
        )


def extract_manual_review_candidates(
    compare_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def candidate_id(
        source: str,
        file_a: dict[str, Any] | None,
        file_b: dict[str, Any] | None,
    ) -> str:
        parts = [source]
        for record in (file_a or {}, file_b or {}):
            parts.append(str(record.get("absolute_path") or ""))
            parts.append(str(record.get("relative_path") or ""))
        digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
        return f"{source}:{digest[:12]}"

    for _idx, item in enumerate(compare_payload.get("exact_matches", [])):
        if item.get("recommended_action") != "manual_review":
            continue
        file_a = item.get("file_a")
        file_b = item.get("file_b")
        candidates.append(
            {
                "id": candidate_id("exact", file_a, file_b),
                "source": "exact",
                "file_a": file_a,
                "file_b": file_b,
                "duplicate_policy": item.get("duplicate_policy"),
                "recommended_action": item.get("recommended_action"),
            }
        )

    for _idx, item in enumerate(compare_payload.get("fuzzy_candidates", [])):
        if item.get("recommended_action") != "manual_review":
            continue
        file_a = item.get("file_a")
        file_b = item.get("file_b")
        candidates.append(
            {
                "id": candidate_id("fuzzy", file_a, file_b),
                "source": "fuzzy",
                "score": item.get("score"),
                "song_similarity": item.get("song_similarity"),
                "artist_similarity": item.get("artist_similarity"),
                "duration_score": item.get("duration_score"),
                "duration_diff_seconds": item.get("duration_diff_seconds"),
                "duplicate_policy": item.get("duplicate_policy"),
                "file_a": file_a,
                "file_b": file_b,
                "recommended_action": item.get("recommended_action"),
            }
        )

    return candidates


def summarize_manual_review_candidates(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    source_counts = {"exact": 0, "fuzzy": 0}
    policy_counts: dict[str, int] = {}

    for candidate in candidates:
        source = candidate.get("source", "unknown")
        if source in source_counts:
            source_counts[source] += 1
        else:
            source_counts[source] = source_counts.get(source, 0) + 1

        policy = (candidate.get("duplicate_policy") or {}).get("classification")
        if policy:
            policy_counts[policy] = policy_counts.get(policy, 0) + 1

    return {
        "total_manual_review_items": len(candidates),
        "source_counts": source_counts,
        "policy_counts": policy_counts,
    }


def build_plan_from_review_decisions(
    candidates: list[dict[str, Any]],
    decisions: dict[str, str],
    dir_b,
) -> dict[str, Any]:
    compare_subset: dict[str, Any] = {"only_in_a": [], "exact_matches": []}
    action_counts = {
        "add_to_b": 0,
        "replace_in_b_with_a": 0,
        "keep_b": 0,
        "keep_both_versions": 0,
        "skip": 0,
    }

    for candidate in candidates:
        candidate_id = candidate["id"]
        action = decisions.get(candidate_id, "skip")
        if action not in REVIEW_ACTIONS:
            action = "skip"
        action_counts[action] += 1

        file_a = candidate.get("file_a") or {}
        file_b = candidate.get("file_b") or {}
        if action == "add_to_b":
            compare_subset["only_in_a"].append(
                {
                    "recommended_action": "add_to_b",
                    "file": file_a,
                }
            )
        elif action in {"replace_in_b_with_a", "keep_both_versions"}:
            compare_subset["exact_matches"].append(
                {
                    "recommended_action": action,
                    "file_a": file_a,
                    "file_b": file_b,
                }
            )

    plan_payload = build_copy_plan(compare_subset, dir_b)
    plan_payload["review_action_counts"] = action_counts
    return plan_payload

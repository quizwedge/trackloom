# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
from __future__ import annotations

import json
from argparse import Namespace

from ..config import CompareConfig
from .common import (
    collect_audio_pair,
    compare_payload,
    normalize_extensions,
    print_ab_header,
    print_next_plan_hints,
    validate_directory,
)


def cmd_compare(args: Namespace) -> int:
    validate_directory(args.dir_a, "dir_a")
    validate_directory(args.dir_b, "dir_b")
    compare_config = CompareConfig.from_args(args)
    compare_config.validate()
    extensions = normalize_extensions(args.extensions)
    files_a, files_b = collect_audio_pair(
        args.dir_a, args.dir_b, extensions, args.progress
    )
    payload = compare_payload(files_a, files_b, compare_config)
    payload["dir_a"] = str(args.dir_a)
    payload["dir_b"] = str(args.dir_b)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print_ab_header("Compare", args.dir_a, args.dir_b)
    print(
        f"Exact matches: {payload['exact_match_count']} | "
        f"Only in A: {payload['only_in_a_count']} | "
        f"Only in B: {payload['only_in_b_count']} | "
        f"Fuzzy candidates: {payload['fuzzy_candidate_count']}"
    )
    policy_counts = payload.get("duplicate_policy_counts", {})
    if policy_counts:
        print(
            "Duplicate policy (exact matches): "
            f"likely_duplicate={policy_counts.get('likely_duplicate', 0)} | "
            f"version_conflict={policy_counts.get('version_conflict', 0)} | "
            f"duration_conflict={policy_counts.get('duration_conflict', 0)}"
        )
    action_counts = payload.get("action_counts", {})
    if action_counts:
        print(
            f"Actions: add_to_b={action_counts.get('add_to_b', 0)} | "
            f"replace_in_b_with_a={action_counts.get('replace_in_b_with_a', 0)} | "
            f"keep_b={action_counts.get('keep_b', 0)} | "
            f"keep_both_versions={action_counts.get('keep_both_versions', 0)} | "
            f"manual_review={action_counts.get('manual_review', 0)}"
        )
    if payload["fuzzy_candidates"]:
        print("Top fuzzy candidates:")
        for candidate in payload["fuzzy_candidates"]:
            print(
                f"- score={candidate['score']:.3f} "
                f"A={candidate['file_a']['relative_path']} "
                f"<-> B={candidate['file_b']['relative_path']}"
            )
    if payload.get("fuzzy_dropped_count"):
        print(
            f"Fuzzy candidates dropped due to --top-k: {payload['fuzzy_dropped_count']}"
        )
    if payload.get("fuzzy_rejection_count"):
        print(f"Fuzzy rejections logged: {payload['fuzzy_rejection_count']}")
    print_next_plan_hints(args.dir_a, args.dir_b)
    return 0

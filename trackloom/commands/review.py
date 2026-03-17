# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from argparse import Namespace

from ..config import CompareConfig
from ..decision_io import load_decisions, write_decisions
from ..plan_io import PLAN_SCHEMA_VERSION, write_plan_json
from ..review import (
    build_plan_from_review_decisions,
    extract_manual_review_candidates,
    summarize_manual_review_candidates,
    validate_manual_item_limit,
)
from .common import (
    apply_mode_to_plan_payload,
    collect_audio_pair,
    compare_payload,
    normalize_extensions,
    print_next_apply_hints,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_CANCELLED = 3


def cmd_review(args: Namespace) -> int:
    compare_config = CompareConfig.from_args(args)
    compare_config.validate()
    if args.page_size <= 0:
        raise ValueError("--page-size must be >= 1")
    if args.max_manual_items < 0:
        raise ValueError("--max-manual-items must be >= 0")
    if args.start_index < 1:
        raise ValueError("--start-index must be >= 1")

    extensions = normalize_extensions(args.extensions)
    files_a, files_b = collect_audio_pair(
        args.dir_a, args.dir_b, extensions, args.progress
    )
    compare_result = compare_payload(files_a, files_b, compare_config)
    candidates = extract_manual_review_candidates(compare_result)
    review_summary = summarize_manual_review_candidates(candidates)
    if compare_result.get("fuzzy_dropped_count"):
        print(
            "Note: "
            f"{compare_result['fuzzy_dropped_count']} fuzzy candidate(s) "
            "were dropped due to --top-k. "
            "Increase --top-k to review more matches."
        )
    if args.export_manual_review_json is not None:
        write_plan_json(
            args.export_manual_review_json,
            {
                "dir_a": str(args.dir_a),
                "dir_b": str(args.dir_b),
                "summary": review_summary,
                "manual_review_candidates": candidates,
            },
        )
    try:
        validate_manual_item_limit(len(candidates), args.max_manual_items)
    except RuntimeError as err:
        limit_payload = {
            "dir_a": str(args.dir_a),
            "dir_b": str(args.dir_b),
            "manual_review_count": len(candidates),
            "max_manual_items": args.max_manual_items,
            "message": str(err),
            "hint": (
                "Rerun with --max-manual-items 0 for no cap, or choose a larger value."
            ),
            "summary": review_summary,
        }
        if args.json:
            print(json.dumps(limit_payload, indent=2))
        else:
            print(limit_payload["message"])
            print(limit_payload["hint"])
        return EXIT_BLOCKED
    if not candidates:
        empty_payload = {
            "dir_a": str(args.dir_a),
            "dir_b": str(args.dir_b),
            "manual_review_count": 0,
            "message": "No manual review items found.",
            "summary": review_summary,
            "counts": {"operations": 0},
            "operations": [],
            "review_action_counts": {
                "add_to_b": 0,
                "replace_in_b_with_a": 0,
                "keep_b": 0,
                "keep_both_versions": 0,
                "skip": 0,
            },
            "schema_version": PLAN_SCHEMA_VERSION,
        }
        if args.write_plan_json is not None:
            write_plan_json(args.write_plan_json, empty_payload)
        if args.json:
            print(json.dumps(empty_payload, indent=2))
        else:
            print("No manual review items found.")
            if args.write_plan_json is not None:
                print(f"Reviewed plan saved to: {args.write_plan_json}")
                print_next_apply_hints(args.dir_a, args.dir_b, args.write_plan_json)
            if args.export_manual_review_json is not None:
                print(f"Manual review export: {args.export_manual_review_json}")
        return EXIT_SUCCESS

    print(f"Manual review items: {len(candidates)}")
    print(
        f"Summary: exact={review_summary['source_counts'].get('exact', 0)} "
        f"fuzzy={review_summary['source_counts'].get('fuzzy', 0)}"
    )
    if review_summary["policy_counts"]:
        policies = ", ".join(
            f"{k}={v}" for k, v in sorted(review_summary["policy_counts"].items())
        )
        print(f"Policy summary: {policies}")
    print(
        "Choices: [a] add_to_b, [r] replace_in_b_with_a, [k] keep_b, "
        "[b] keep_both_versions, [s] skip"
    )
    print(
        "Navigation: n=next page, p=previous page, done=finish, q=quit without saving"
    )
    print("Set action with: <index> <choice> (example: 3 r)")

    key_to_action = {
        "a": "add_to_b",
        "r": "replace_in_b_with_a",
        "k": "keep_b",
        "b": "keep_both_versions",
        "s": "skip",
    }
    decisions = {}
    if args.decisions_file is not None:
        decisions = load_decisions(args.decisions_file)
        if decisions:
            print(
                "Loaded "
                f"{len(decisions)} existing decision(s) from {args.decisions_file}"
            )
    page_size = args.page_size
    start_index = min(args.start_index, len(candidates))
    page = (start_index - 1) // page_size
    total_pages = (len(candidates) + page_size - 1) // page_size

    while True:
        start = page * page_size
        end = min(start + page_size, len(candidates))
        print(
            f"\nPage {page + 1}/{total_pages} "
            f"items {start + 1}-{end} of {len(candidates)}"
        )
        for index in range(start, end):
            candidate = candidates[index]
            file_a = candidate.get("file_a") or {}
            file_b = candidate.get("file_b") or {}
            a_rel = file_a.get("relative_path", "<unknown>")
            b_rel = file_b.get("relative_path", "<unknown>")
            chosen = decisions.get(candidate["id"], "skip")
            summary = (
                f"{index + 1}. [{chosen}] {candidate['source']} A={a_rel} <-> B={b_rel}"
            )
            if candidate["source"] == "fuzzy":
                summary += (
                    f" | score={candidate.get('score', 0):.3f}"
                    f" song={candidate.get('song_similarity', 0):.3f}"
                    f" artist={candidate.get('artist_similarity', 0):.3f}"
                )
            print(summary)

        try:
            raw = input("review> ").strip().lower()
        except EOFError:
            if args.decisions_file is not None:
                write_decisions(args.decisions_file, decisions)
                print(f"Decisions saved to: {args.decisions_file}")
            print(
                "Review cancelled due to EOF on stdin. "
                "No reviewed plan changes applied."
            )
            return EXIT_CANCELLED
        if raw in {"done", "d"}:
            break
        if raw == "n":
            if page < total_pages - 1:
                page += 1
            continue
        if raw == "p":
            if page > 0:
                page -= 1
            continue
        if raw == "q":
            if args.decisions_file is not None:
                write_decisions(args.decisions_file, decisions)
                print(f"Decisions saved to: {args.decisions_file}")
            print("Review cancelled by user. No reviewed plan changes applied.")
            return EXIT_CANCELLED

        parts = raw.split()
        if len(parts) == 2 and parts[0].isdigit():
            idx = int(parts[0])
            choice = parts[1]
            if idx < 1 or idx > len(candidates):
                print("Invalid index.")
                continue
            action = key_to_action.get(choice)
            if action is None:
                print("Invalid choice. Use one of: a r k b s")
                continue
            decisions[candidates[idx - 1]["id"]] = action
            if args.decisions_file is not None:
                write_decisions(args.decisions_file, decisions)
            continue

        print("Unknown command. Use n, p, done, q, or '<index> <choice>'")

    plan_payload = build_plan_from_review_decisions(candidates, decisions, args.dir_b)
    plan_payload = apply_mode_to_plan_payload(
        plan_payload, args.mode, args.dir_a, args.dir_b
    )
    plan_payload["compare_settings"] = compare_config.as_compare_kwargs()
    plan_payload["manual_review_count"] = len(candidates)
    plan_payload["summary"] = review_summary
    plan_payload["schema_version"] = PLAN_SCHEMA_VERSION
    if args.decisions_file is not None:
        plan_payload["source_decisions_file"] = str(args.decisions_file)

    if args.write_plan_json is not None:
        write_plan_json(args.write_plan_json, plan_payload)
    if args.decisions_file is not None:
        write_decisions(args.decisions_file, decisions)

    if args.json:
        print(json.dumps(plan_payload, indent=2))
        return 0

    counts = plan_payload.get("counts", {})
    review_counts = plan_payload.get("review_action_counts", {})
    print(
        f"Reviewed plan operations: {counts.get('operations', 0)} "
        f"(add_to_b={counts.get('add_to_b', 0)}, "
        f"replace_in_b_with_a={counts.get('replace_in_b_with_a', 0)}, "
        f"keep_both_versions={counts.get('keep_both_versions', 0)})"
    )
    print(
        f"Review choices: add_to_b={review_counts.get('add_to_b', 0)} "
        f"replace_in_b_with_a={review_counts.get('replace_in_b_with_a', 0)} "
        f"keep_b={review_counts.get('keep_b', 0)} "
        f"keep_both_versions={review_counts.get('keep_both_versions', 0)} "
        f"skip={review_counts.get('skip', 0)}"
    )
    if plan_payload.get("mode_skipped_count"):
        print(
            "Mode skipped operations "
            f"({args.mode}): {plan_payload['mode_skipped_count']}"
        )
    if args.write_plan_json is not None:
        print(f"Reviewed plan saved to: {args.write_plan_json}")
        print_next_apply_hints(args.dir_a, args.dir_b, args.write_plan_json)
    if args.export_manual_review_json is not None:
        print(f"Manual review export: {args.export_manual_review_json}")
    if args.decisions_file is not None:
        print(f"Decisions saved to: {args.decisions_file}")
    return EXIT_SUCCESS

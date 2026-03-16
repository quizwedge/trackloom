# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from argparse import Namespace

from ..config import CompareConfig
from ..plan_io import PLAN_SCHEMA_VERSION, write_plan_json
from ..planner import build_copy_plan
from .common import (
    apply_mode_to_plan_payload,
    collect_audio_pair,
    compare_payload,
    normalize_extensions,
)


def cmd_plan(args: Namespace) -> int:
    compare_config = CompareConfig.from_args(args)
    compare_config.validate()
    extensions = normalize_extensions(args.extensions)
    files_a, files_b = collect_audio_pair(args.dir_a, args.dir_b, extensions, args.progress)
    compare_result = compare_payload(files_a, files_b, compare_config)
    plan_payload = build_copy_plan(compare_result, args.dir_b)
    plan_payload = apply_mode_to_plan_payload(
        plan_payload, args.mode, args.dir_a, args.dir_b, compare_payload=compare_result
    )
    plan_payload["schema_version"] = PLAN_SCHEMA_VERSION

    if args.write_plan_json is not None:
        write_plan_json(args.write_plan_json, plan_payload)

    if args.json:
        print(json.dumps(plan_payload, indent=2))
        return 0

    counts = plan_payload["counts"]
    print(f"Plan for A={args.dir_a} -> B={args.dir_b}")
    print(
        f"Operations: {counts['operations']} "
        f"(add_to_b={counts['add_to_b']}, "
        f"replace_in_b_with_a={counts['replace_in_b_with_a']}, "
        f"keep_both_versions={counts['keep_both_versions']})"
    )
    if plan_payload.get("mode_skipped_count"):
        print(
            f"Mode skipped operations ({args.mode}): {plan_payload['mode_skipped_count']}"
        )
    if args.write_plan_json is not None:
        print(f"Plan saved to: {args.write_plan_json}")
    for op in plan_payload["operations"][:20]:
        print(f"- {op['action']}: {op['source_relative_path']} -> {op['destination_path']}")
    if len(plan_payload["operations"]) > 20:
        print(f"... {len(plan_payload['operations']) - 20} more operations")
    return 0

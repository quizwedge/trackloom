# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

from ..apply_ops import execute_operations
from ..config import CompareConfig
from ..plan_io import load_plan_json, validate_plan_operations
from ..planner import build_copy_plan
from ..report_io import write_report_csv, write_report_json
from .common import (
    collect_audio_pair,
    compare_payload,
    normalize_extensions,
    print_apply_change_summary,
)
from ..mode import filter_operations_for_mode

EXIT_SUCCESS = 0
EXIT_CANCELLED = 3


def cmd_apply(args: Namespace) -> int:
    source_decisions_file = None
    if args.from_plan_json is not None:
        plan_payload = load_plan_json(args.from_plan_json)
        operations = plan_payload["operations"]
        source_decisions_file = plan_payload.get("source_decisions_file")
        effective_dir_a = str(plan_payload.get("dir_a") or args.dir_a)
        effective_dir_b = str(plan_payload.get("dir_b") or args.dir_b)
        validate_plan_operations(
            operations,
            Path(effective_dir_a),
            Path(effective_dir_b),
        )
    else:
        compare_config = CompareConfig.from_args(args)
        compare_config.validate()
        extensions = normalize_extensions(args.extensions)
        files_a, files_b = collect_audio_pair(args.dir_a, args.dir_b, extensions, args.progress)
        compare_result = compare_payload(files_a, files_b, compare_config)
        plan_payload = build_copy_plan(compare_result, args.dir_b)
        operations = plan_payload["operations"]
        effective_dir_a = str(args.dir_a)
        effective_dir_b = str(args.dir_b)

    mode_filtered_ops, mode_skipped = filter_operations_for_mode(operations, args.mode)
    operations = mode_filtered_ops

    if not operations:
        result = {
            "dir_a": effective_dir_a,
            "dir_b": effective_dir_b,
            "planned_operation_count": 0,
            "applied": False,
            "mode": args.mode,
            "mode_skipped_count": len(mode_skipped),
            "mode_skipped_operations": mode_skipped,
            "message": "No operations to apply.",
            "result": {"executed": [], "skipped": []},
        }
        if args.report_json is not None:
            write_report_json(args.report_json, result)
        if args.report_csv is not None:
            write_report_csv(args.report_csv, result)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("No operations to apply.")
            if args.report_json is not None:
                print(f"Report JSON: {args.report_json}")
        return EXIT_SUCCESS

    effective_quarantine_dir = args.quarantine_dir
    if args.cleanup_mode == "move-to-quarantine" and effective_quarantine_dir is None:
        effective_quarantine_dir = Path(effective_dir_b) / ".trackloom_quarantine"

    if not args.json:
        print_apply_change_summary(operations, effective_dir_b)

    if args.yes and not args.dry_run and not args.force:
        confirmation = input(
            "You are applying real file changes with --yes. Type APPLY to continue: "
        ).strip()
        if confirmation != "APPLY":
            cancelled_payload = {
                "dir_a": effective_dir_a,
                "dir_b": effective_dir_b,
                "planned_operation_count": len(operations),
                "applied": False,
                "message": "Cancelled by safeguard confirmation.",
                "result": {"executed": [], "skipped": []},
            }
            if args.report_json is not None:
                write_report_json(args.report_json, cancelled_payload)
            if args.report_csv is not None:
                write_report_csv(args.report_csv, cancelled_payload)
            if args.json:
                print(json.dumps(cancelled_payload, indent=2))
            else:
                print("Cancelled by safeguard confirmation. No changes applied.")
            return EXIT_CANCELLED

    if not args.yes:
        response = input(
            f"Apply {len(operations)} operation(s) to {args.dir_b}? [y/N]: "
        ).strip().lower()
        if response not in {"y", "yes"}:
            cancelled_payload = {
                "dir_a": effective_dir_a,
                "dir_b": effective_dir_b,
                "planned_operation_count": len(operations),
                "applied": False,
                "message": "Cancelled by user.",
                "result": {"executed": [], "skipped": []},
            }
            if args.report_json is not None:
                write_report_json(args.report_json, cancelled_payload)
            if args.report_csv is not None:
                write_report_csv(args.report_csv, cancelled_payload)
            if args.json:
                print(json.dumps(cancelled_payload, indent=2))
            else:
                print("Cancelled by user. No changes applied.")
                if args.report_json is not None:
                    print(f"Report JSON: {args.report_json}")
            return EXIT_CANCELLED

    exec_result = execute_operations(
        operations,
        dry_run=args.dry_run,
        cleanup_mode=args.cleanup_mode,
        quarantine_dir=effective_quarantine_dir,
        dir_b=Path(effective_dir_b),
    )
    payload = {
        "dir_a": effective_dir_a,
        "dir_b": effective_dir_b,
        "planned_operation_count": len(operations),
        "applied": not args.dry_run,
        "dry_run": args.dry_run,
        "mode": args.mode,
        "mode_skipped_count": len(mode_skipped),
        "mode_skipped_operations": mode_skipped,
        "from_plan_json": str(args.from_plan_json) if args.from_plan_json else None,
        "run_metadata": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "fuzzy_threshold": args.fuzzy_threshold,
            "close_duration_seconds": args.close_duration_seconds,
            "duration_conflict_seconds": args.duration_conflict_seconds,
            "min_song_sim": args.min_song_sim,
            "min_artist_sim": args.min_artist_sim,
            "top_k": args.top_k,
            "yes": args.yes,
            "force": args.force,
            "mode": args.mode,
            "cleanup_mode": args.cleanup_mode,
            "quarantine_dir": str(effective_quarantine_dir) if effective_quarantine_dir else None,
            "source_plan_json": str(args.from_plan_json) if args.from_plan_json else None,
            "source_decisions_file": source_decisions_file,
        },
        "result": exec_result,
    }
    if args.report_json is not None:
        write_report_json(args.report_json, payload)
    if args.report_csv is not None:
        write_report_csv(args.report_csv, payload)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(
        f"Apply result: requested={exec_result['requested_count']} "
        f"executed={exec_result['executed_count']} skipped={exec_result['skipped_count']}"
    )
    if mode_skipped:
        print(f"Mode skipped operations ({args.mode}): {len(mode_skipped)}")
    if args.report_json is not None:
        print(f"Report JSON: {args.report_json}")
    if args.report_csv is not None:
        print(f"Report CSV: {args.report_csv}")
    return EXIT_SUCCESS

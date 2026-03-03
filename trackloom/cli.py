# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Optional

from .apply_ops import execute_operations
from .compare import compare_collections
from .decision_io import load_decisions, write_decisions
from .mode import MODE_PLEX, MODE_STANDARD, filter_operations_for_mode
from .parser import SUPPORTED_EXTENSIONS, collect_audio_metadata
from .plan_io import load_plan_json, write_plan_json
from .planner import build_copy_plan
from .report_io import write_report_csv, write_report_json
from .review import (
    build_plan_from_review_decisions,
    extract_manual_review_candidates,
    summarize_manual_review_candidates,
    validate_manual_item_limit,
)

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_CANCELLED = 3


def _find_subparser(
    parser: argparse.ArgumentParser, name: str
) -> Optional[argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparser = action.choices.get(name)
            if isinstance(subparser, argparse.ArgumentParser):
                return subparser
    return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trackloom",
        description="Compare audio files in two directories (step 1: parsing fields).",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    parse_cmd = subparsers.add_parser(
        "parse",
        help="Catalog one directory or compare two directories by parsed fields.",
    )
    parse_cmd.add_argument(
        "dir_a",
        type=Path,
        help="Audio library directory A",
    )
    parse_cmd.add_argument(
        "dir_b",
        nargs="?",
        type=Path,
        default=None,
        help="Optional audio library directory B",
    )
    parse_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help="Audio extensions to scan (ex: .mp3 .flac .m4a)",
    )
    parse_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print results as JSON",
    )
    parse_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    compare_cmd = subparsers.add_parser(
        "compare",
        help="Compare two directories using exact and fuzzy matching.",
    )
    compare_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    compare_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    compare_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help="Audio extensions to scan (ex: .mp3 .flac .m4a)",
    )
    compare_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help="Minimum fuzzy score to include a candidate (0.0-1.0)",
    )
    compare_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help="Duration considered close for fuzzy scoring",
    )
    compare_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help="Duration difference above this is a conflict",
    )
    compare_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help="Minimum song similarity to consider fuzzy candidate",
    )
    compare_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help="Minimum artist similarity to consider fuzzy candidate",
    )
    compare_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Maximum fuzzy candidates to include in output",
    )
    compare_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print results as JSON",
    )
    compare_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    plan_cmd = subparsers.add_parser(
        "plan",
        help="Create a copy/add plan to bring tracks from A into B.",
    )
    plan_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    plan_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    plan_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help="Audio extensions to scan (ex: .mp3 .flac .m4a)",
    )
    plan_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help="Minimum fuzzy score to include a candidate (0.0-1.0)",
    )
    plan_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help="Duration considered close for fuzzy scoring",
    )
    plan_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help="Duration difference above this is a conflict",
    )
    plan_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help="Minimum song similarity to consider fuzzy candidate",
    )
    plan_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help="Minimum artist similarity to consider fuzzy candidate",
    )
    plan_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Maximum fuzzy candidates to include in output",
    )
    plan_cmd.add_argument(
        "--mode",
        choices=[MODE_STANDARD, MODE_PLEX],
        default=MODE_STANDARD,
        help="Operation filtering mode",
    )
    plan_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print plan as JSON",
    )
    plan_cmd.add_argument(
        "--write-plan-json",
        type=Path,
        default=None,
        help="Write plan payload to a JSON file",
    )
    plan_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    apply_cmd = subparsers.add_parser(
        "apply",
        help="Apply copy/add operations to bring tracks from A into B.",
    )
    apply_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    apply_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    apply_cmd.add_argument(
        "--from-plan-json",
        type=Path,
        default=None,
        help="Apply operations from a saved plan JSON file",
    )
    apply_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help="Audio extensions to scan (ex: .mp3 .flac .m4a)",
    )
    apply_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help="Minimum fuzzy score to include a candidate (0.0-1.0)",
    )
    apply_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help="Duration considered close for fuzzy scoring",
    )
    apply_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help="Duration difference above this is a conflict",
    )
    apply_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help="Minimum song similarity to consider fuzzy candidate",
    )
    apply_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help="Minimum artist similarity to consider fuzzy candidate",
    )
    apply_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Maximum fuzzy candidates to include in output",
    )
    apply_cmd.add_argument(
        "--mode",
        choices=[MODE_STANDARD, MODE_PLEX],
        default=MODE_STANDARD,
        help="Operation filtering mode",
    )
    apply_cmd.add_argument(
        "--yes",
        action="store_true",
        help="Apply operations without confirmation prompt",
    )
    apply_cmd.add_argument(
        "--force",
        action="store_true",
        help="Bypass extra confirmation when using --yes without --dry-run",
    )
    apply_cmd.add_argument(
        "--cleanup-mode",
        choices=["none", "move-to-quarantine"],
        default="none",
        help="Optional cleanup behavior for replace actions",
    )
    apply_cmd.add_argument(
        "--quarantine-dir",
        type=Path,
        default=None,
        help="Required when cleanup-mode is move-to-quarantine",
    )
    apply_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing files",
    )
    apply_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print apply result as JSON",
    )
    apply_cmd.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Write apply report payload to a JSON file",
    )
    apply_cmd.add_argument(
        "--report-csv",
        type=Path,
        default=None,
        help="Write apply operation report to a CSV file",
    )
    apply_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    review_cmd = subparsers.add_parser(
        "review",
        help="Interactively review manual-review items and build a plan.",
    )
    review_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    review_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    review_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help="Audio extensions to scan (ex: .mp3 .flac .m4a)",
    )
    review_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help="Minimum fuzzy score to include a candidate (0.0-1.0)",
    )
    review_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help="Duration considered close for fuzzy scoring",
    )
    review_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help="Duration difference above this is a conflict",
    )
    review_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help="Minimum song similarity to consider fuzzy candidate",
    )
    review_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help="Minimum artist similarity to consider fuzzy candidate",
    )
    review_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Maximum fuzzy candidates to include in output",
    )
    review_cmd.add_argument(
        "--mode",
        choices=[MODE_STANDARD, MODE_PLEX],
        default=MODE_STANDARD,
        help="Operation filtering mode for reviewed plan output",
    )
    review_cmd.add_argument(
        "--page-size",
        type=int,
        default=20,
        help="Number of manual-review items shown per page",
    )
    review_cmd.add_argument(
        "--max-manual-items",
        type=int,
        default=1000,
        help="Safety cap for interactive manual-review items (0 disables cap)",
    )
    review_cmd.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="1-based item index to start review from",
    )
    review_cmd.add_argument(
        "--write-plan-json",
        type=Path,
        default=None,
        help="Write reviewed plan payload to a JSON file",
    )
    review_cmd.add_argument(
        "--export-manual-review-json",
        type=Path,
        default=None,
        help="Write manual-review candidate details and summary to JSON",
    )
    review_cmd.add_argument(
        "--decisions-file",
        type=Path,
        default=None,
        help="Load and autosave review decisions to a JSON file",
    )
    review_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print reviewed plan as JSON",
    )
    review_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    help_cmd = subparsers.add_parser("help", help="Show help for commands.")
    help_cmd.add_argument(
        "topic",
        nargs="?",
        choices=["parse", "compare", "plan", "apply", "review"],
        help="Optional command to show detailed help for",
    )
    return parser


def _normalize_extensions(extensions: list[str]) -> set[str]:
    return {ext if ext.startswith(".") else f".{ext}" for ext in extensions}


def _print_next_apply_hints(dir_a: Path, dir_b: Path, plan_path: Path) -> None:
    print("Next commands:")
    print(
        f"  trackloom apply {dir_a} {dir_b} "
        f"--from-plan-json {plan_path} --dry-run"
    )
    print(
        f"  trackloom apply {dir_a} {dir_b} "
        f"--from-plan-json {plan_path} --yes"
    )


def _print_apply_change_summary(operations: list[dict], dir_b: str) -> None:
    action_counts = {}
    destinations = []
    for op in operations:
        action = op.get("action", "unknown")
        action_counts[action] = action_counts.get(action, 0) + 1
        destinations.append(op.get("destination_path", ""))

    print(f"Planned changes in B ({dir_b}): {len(operations)} operation(s)")
    parts = []
    for action in ["add_to_b", "replace_in_b_with_a", "keep_both_versions"]:
        if action_counts.get(action):
            parts.append(f"{action}={action_counts[action]}")
    if not parts:
        for action, count in sorted(action_counts.items()):
            parts.append(f"{action}={count}")
    print("  by action: " + ", ".join(parts))
    preview = [d for d in destinations if d][:5]
    if preview:
        print("  destination preview:")
        for item in preview:
            print(f"    - {item}")


def cmd_parse(args: argparse.Namespace) -> int:
    extensions = _normalize_extensions(args.extensions)
    def make_progress_callback(label: str):
        def _callback(current: int, total: int, _: Path) -> None:
            print(
                f"\r[{label}] scanned {current}/{total} files",
                end="",
                file=sys.stderr,
                flush=True,
            )
            if current == total:
                print(file=sys.stderr, flush=True)

        return _callback

    left_progress = make_progress_callback("A") if args.progress else None
    left = collect_audio_metadata(
        args.dir_a,
        extensions=extensions,
        progress_callback=left_progress,
    )
    right = (
        collect_audio_metadata(
            args.dir_b,
            extensions=extensions,
            progress_callback=(make_progress_callback("B") if args.progress else None),
        )
        if args.dir_b is not None
        else []
    )

    payload = {
        "dir_a": str(args.dir_a),
        "dir_b": str(args.dir_b) if args.dir_b is not None else None,
        "count_a": len(left),
        "count_b": len(right) if args.dir_b is not None else None,
        "files_a": [item.to_dict() for item in left],
        "files_b": [item.to_dict() for item in right] if args.dir_b is not None else None,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"A ({args.dir_a}) files: {len(left)}")
    for item in left:
        print(f"- {item.relative_path}")
        print(
            f"  path: artist={item.path_fields.artist!r}, "
            f"album={item.path_fields.album!r}, song={item.path_fields.song!r}"
        )
        print(
            f"  tags: artist={item.tag_fields.artist!r}, "
            f"album={item.tag_fields.album!r}, song={item.tag_fields.song!r}"
        )
        print(
            f"  norm: artist={item.normalized_path_fields.artist!r}, "
            f"album={item.normalized_path_fields.album!r}, "
            f"song={item.normalized_path_fields.song!r}"
        )
        print(
            f"  quality: duration={item.duration_seconds!r}s, "
            f"bitrate_kbps={item.bitrate_kbps!r}, sample_rate_hz={item.sample_rate_hz!r}, "
            f"bit_depth={item.bit_depth!r}, channels={item.channels!r}, codec={item.codec!r}"
        )
        print(f"  version_hints: {item.version_hints!r}")

    if args.dir_b is not None:
        print(f"B ({args.dir_b}) files: {len(right)}")
        for item in right:
            print(f"- {item.relative_path}")
            print(
                f"  path: artist={item.path_fields.artist!r}, "
                f"album={item.path_fields.album!r}, song={item.path_fields.song!r}"
            )
            print(
                f"  tags: artist={item.tag_fields.artist!r}, "
                f"album={item.tag_fields.album!r}, song={item.tag_fields.song!r}"
            )
            print(
                f"  norm: artist={item.normalized_path_fields.artist!r}, "
                f"album={item.normalized_path_fields.album!r}, "
                f"song={item.normalized_path_fields.song!r}"
            )
            print(
                f"  quality: duration={item.duration_seconds!r}s, "
                f"bitrate_kbps={item.bitrate_kbps!r}, sample_rate_hz={item.sample_rate_hz!r}, "
                f"bit_depth={item.bit_depth!r}, channels={item.channels!r}, codec={item.codec!r}"
            )
            print(f"  version_hints: {item.version_hints!r}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    if args.fuzzy_threshold < 0 or args.fuzzy_threshold > 1:
        raise ValueError("--fuzzy-threshold must be between 0.0 and 1.0")
    if args.close_duration_seconds < 0:
        raise ValueError("--close-duration-seconds must be >= 0")
    if args.duration_conflict_seconds < 0:
        raise ValueError("--duration-conflict-seconds must be >= 0")
    if args.duration_conflict_seconds < args.close_duration_seconds:
        raise ValueError("--duration-conflict-seconds must be >= --close-duration-seconds")
    if args.min_song_sim < 0 or args.min_song_sim > 1:
        raise ValueError("--min-song-sim must be between 0.0 and 1.0")
    if args.min_artist_sim < 0 or args.min_artist_sim > 1:
        raise ValueError("--min-artist-sim must be between 0.0 and 1.0")
    if args.top_k < 0:
        raise ValueError("--top-k must be >= 0")

    extensions = _normalize_extensions(args.extensions)

    def make_progress_callback(label: str):
        def _callback(current: int, total: int, _: Path) -> None:
            print(
                f"\r[{label}] scanned {current}/{total} files",
                end="",
                file=sys.stderr,
                flush=True,
            )
            if current == total:
                print(file=sys.stderr, flush=True)

        return _callback

    files_a = collect_audio_metadata(
        args.dir_a,
        extensions=extensions,
        progress_callback=(make_progress_callback("A") if args.progress else None),
    )
    files_b = collect_audio_metadata(
        args.dir_b,
        extensions=extensions,
        progress_callback=(make_progress_callback("B") if args.progress else None),
    )
    payload = compare_collections(
        files_a=files_a,
        files_b=files_b,
        fuzzy_threshold=args.fuzzy_threshold,
        close_duration_seconds=args.close_duration_seconds,
        duration_conflict_seconds=args.duration_conflict_seconds,
        min_song_similarity=args.min_song_sim,
        min_artist_similarity=args.min_artist_sim,
        top_k=args.top_k,
    )
    payload["dir_a"] = str(args.dir_a)
    payload["dir_b"] = str(args.dir_b)

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Compared A={args.dir_a} vs B={args.dir_b}")
    print(
        f"Exact matches: {payload['exact_match_count']} | "
        f"Only in A: {payload['only_in_a_count']} | "
        f"Only in B: {payload['only_in_b_count']} | "
        f"Fuzzy candidates: {payload['fuzzy_candidate_count']}"
    )
    policy_counts = payload.get("duplicate_policy_counts", {})
    if policy_counts:
        print(
            f"Duplicate policy (exact matches): likely_duplicate={policy_counts.get('likely_duplicate', 0)} | "
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
    if payload.get("fuzzy_rejection_count"):
        print(f"Fuzzy rejections logged: {payload['fuzzy_rejection_count']}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    if args.fuzzy_threshold < 0 or args.fuzzy_threshold > 1:
        raise ValueError("--fuzzy-threshold must be between 0.0 and 1.0")
    if args.close_duration_seconds < 0:
        raise ValueError("--close-duration-seconds must be >= 0")
    if args.duration_conflict_seconds < 0:
        raise ValueError("--duration-conflict-seconds must be >= 0")
    if args.duration_conflict_seconds < args.close_duration_seconds:
        raise ValueError("--duration-conflict-seconds must be >= --close-duration-seconds")
    if args.min_song_sim < 0 or args.min_song_sim > 1:
        raise ValueError("--min-song-sim must be between 0.0 and 1.0")
    if args.min_artist_sim < 0 or args.min_artist_sim > 1:
        raise ValueError("--min-artist-sim must be between 0.0 and 1.0")
    if args.top_k < 0:
        raise ValueError("--top-k must be >= 0")

    extensions = _normalize_extensions(args.extensions)

    def make_progress_callback(label: str):
        def _callback(current: int, total: int, _: Path) -> None:
            print(
                f"\r[{label}] scanned {current}/{total} files",
                end="",
                file=sys.stderr,
                flush=True,
            )
            if current == total:
                print(file=sys.stderr, flush=True)

        return _callback

    files_a = collect_audio_metadata(
        args.dir_a,
        extensions=extensions,
        progress_callback=(make_progress_callback("A") if args.progress else None),
    )
    files_b = collect_audio_metadata(
        args.dir_b,
        extensions=extensions,
        progress_callback=(make_progress_callback("B") if args.progress else None),
    )
    compare_payload = compare_collections(
        files_a=files_a,
        files_b=files_b,
        fuzzy_threshold=args.fuzzy_threshold,
        close_duration_seconds=args.close_duration_seconds,
        duration_conflict_seconds=args.duration_conflict_seconds,
        min_song_similarity=args.min_song_sim,
        min_artist_similarity=args.min_artist_sim,
        top_k=args.top_k,
    )
    plan_payload = build_copy_plan(compare_payload, args.dir_b)
    filtered_ops, mode_skipped = filter_operations_for_mode(plan_payload["operations"], args.mode)
    plan_payload["operations"] = filtered_ops
    plan_payload["mode"] = args.mode
    plan_payload["mode_skipped_count"] = len(mode_skipped)
    plan_payload["mode_skipped_operations"] = mode_skipped
    plan_payload["counts"]["operations"] = len(filtered_ops)
    plan_payload["counts"]["add_to_b"] = len([op for op in filtered_ops if op.get("action") == "add_to_b"])
    plan_payload["counts"]["replace_in_b_with_a"] = len(
        [op for op in filtered_ops if op.get("action") == "replace_in_b_with_a"]
    )
    plan_payload["counts"]["keep_both_versions"] = len(
        [op for op in filtered_ops if op.get("action") == "keep_both_versions"]
    )
    plan_payload["dir_a"] = str(args.dir_a)
    plan_payload["dir_b"] = str(args.dir_b)
    plan_payload["compare_summary"] = {
        "exact_match_count": compare_payload["exact_match_count"],
        "only_in_a_count": compare_payload["only_in_a_count"],
        "only_in_b_count": compare_payload["only_in_b_count"],
        "fuzzy_candidate_count": compare_payload["fuzzy_candidate_count"],
        "fuzzy_rejection_count": compare_payload.get("fuzzy_rejection_count", 0),
        "action_counts": compare_payload["action_counts"],
    }

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


def cmd_apply(args: argparse.Namespace) -> int:
    source_decisions_file = None
    if args.from_plan_json is not None:
        plan_payload = load_plan_json(args.from_plan_json)
        operations = plan_payload["operations"]
        source_decisions_file = plan_payload.get("source_decisions_file")
        effective_dir_a = str(args.dir_a)
        effective_dir_b = str(args.dir_b)
    else:
        if args.fuzzy_threshold < 0 or args.fuzzy_threshold > 1:
            raise ValueError("--fuzzy-threshold must be between 0.0 and 1.0")
        if args.close_duration_seconds < 0:
            raise ValueError("--close-duration-seconds must be >= 0")
        if args.duration_conflict_seconds < 0:
            raise ValueError("--duration-conflict-seconds must be >= 0")
        if args.duration_conflict_seconds < args.close_duration_seconds:
            raise ValueError("--duration-conflict-seconds must be >= --close-duration-seconds")
        if args.min_song_sim < 0 or args.min_song_sim > 1:
            raise ValueError("--min-song-sim must be between 0.0 and 1.0")
        if args.min_artist_sim < 0 or args.min_artist_sim > 1:
            raise ValueError("--min-artist-sim must be between 0.0 and 1.0")
        if args.top_k < 0:
            raise ValueError("--top-k must be >= 0")

        extensions = _normalize_extensions(args.extensions)

        def make_progress_callback(label: str):
            def _callback(current: int, total: int, _: Path) -> None:
                print(
                    f"\r[{label}] scanned {current}/{total} files",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
                if current == total:
                    print(file=sys.stderr, flush=True)

            return _callback

        files_a = collect_audio_metadata(
            args.dir_a,
            extensions=extensions,
            progress_callback=(make_progress_callback("A") if args.progress else None),
        )
        files_b = collect_audio_metadata(
            args.dir_b,
            extensions=extensions,
            progress_callback=(make_progress_callback("B") if args.progress else None),
        )
        compare_payload = compare_collections(
            files_a=files_a,
            files_b=files_b,
            fuzzy_threshold=args.fuzzy_threshold,
            close_duration_seconds=args.close_duration_seconds,
            duration_conflict_seconds=args.duration_conflict_seconds,
            min_song_similarity=args.min_song_sim,
            min_artist_similarity=args.min_artist_sim,
            top_k=args.top_k,
        )
        plan_payload = build_copy_plan(compare_payload, args.dir_b)
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
        }
        if args.report_json is not None:
            write_report_json(args.report_json, result)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("No operations to apply.")
            if args.report_json is not None:
                print(f"Report JSON: {args.report_json}")
        return EXIT_SUCCESS

    if args.cleanup_mode == "move-to-quarantine" and args.quarantine_dir is None:
        raise ValueError("--quarantine-dir is required when --cleanup-mode=move-to-quarantine")

    if not args.json:
        _print_apply_change_summary(operations, effective_dir_b)

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
            }
            if args.report_json is not None:
                write_report_json(args.report_json, cancelled_payload)
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
            }
            if args.report_json is not None:
                write_report_json(args.report_json, cancelled_payload)
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
        quarantine_dir=args.quarantine_dir,
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
            "quarantine_dir": str(args.quarantine_dir) if args.quarantine_dir else None,
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


def cmd_review(args: argparse.Namespace) -> int:
    if args.fuzzy_threshold < 0 or args.fuzzy_threshold > 1:
        raise ValueError("--fuzzy-threshold must be between 0.0 and 1.0")
    if args.close_duration_seconds < 0:
        raise ValueError("--close-duration-seconds must be >= 0")
    if args.duration_conflict_seconds < 0:
        raise ValueError("--duration-conflict-seconds must be >= 0")
    if args.duration_conflict_seconds < args.close_duration_seconds:
        raise ValueError("--duration-conflict-seconds must be >= --close-duration-seconds")
    if args.min_song_sim < 0 or args.min_song_sim > 1:
        raise ValueError("--min-song-sim must be between 0.0 and 1.0")
    if args.min_artist_sim < 0 or args.min_artist_sim > 1:
        raise ValueError("--min-artist-sim must be between 0.0 and 1.0")
    if args.top_k < 0:
        raise ValueError("--top-k must be >= 0")
    if args.page_size <= 0:
        raise ValueError("--page-size must be >= 1")
    if args.max_manual_items < 0:
        raise ValueError("--max-manual-items must be >= 0")
    if args.start_index < 1:
        raise ValueError("--start-index must be >= 1")

    extensions = _normalize_extensions(args.extensions)

    def make_progress_callback(label: str):
        def _callback(current: int, total: int, _: Path) -> None:
            print(
                f"\r[{label}] scanned {current}/{total} files",
                end="",
                file=sys.stderr,
                flush=True,
            )
            if current == total:
                print(file=sys.stderr, flush=True)

        return _callback

    files_a = collect_audio_metadata(
        args.dir_a,
        extensions=extensions,
        progress_callback=(make_progress_callback("A") if args.progress else None),
    )
    files_b = collect_audio_metadata(
        args.dir_b,
        extensions=extensions,
        progress_callback=(make_progress_callback("B") if args.progress else None),
    )
    compare_payload = compare_collections(
        files_a=files_a,
        files_b=files_b,
        fuzzy_threshold=args.fuzzy_threshold,
        close_duration_seconds=args.close_duration_seconds,
        duration_conflict_seconds=args.duration_conflict_seconds,
        min_song_similarity=args.min_song_sim,
        min_artist_similarity=args.min_artist_sim,
        top_k=args.top_k,
    )
    candidates = extract_manual_review_candidates(compare_payload)
    review_summary = summarize_manual_review_candidates(candidates)
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
            "hint": "Rerun with --max-manual-items 0 for no cap, or choose a larger value.",
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
        }
        if args.write_plan_json is not None:
            write_plan_json(args.write_plan_json, empty_payload)
        if args.json:
            print(json.dumps(empty_payload, indent=2))
        else:
            print("No manual review items found.")
            if args.write_plan_json is not None:
                print(f"Reviewed plan saved to: {args.write_plan_json}")
                _print_next_apply_hints(args.dir_a, args.dir_b, args.write_plan_json)
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
    print("Choices: [a] add_to_b, [r] replace_in_b_with_a, [k] keep_b, [b] keep_both_versions, [s] skip")
    print("Navigation: n=next page, p=previous page, done=finish, q=quit without saving")
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
            print(f"Loaded {len(decisions)} existing decision(s) from {args.decisions_file}")
    page_size = args.page_size
    start_index = min(args.start_index, len(candidates))
    page = (start_index - 1) // page_size
    total_pages = (len(candidates) + page_size - 1) // page_size

    while True:
        start = page * page_size
        end = min(start + page_size, len(candidates))
        print(f"\nPage {page + 1}/{total_pages} items {start + 1}-{end} of {len(candidates)}")
        for index in range(start, end):
            candidate = candidates[index]
            file_a = candidate.get("file_a") or {}
            file_b = candidate.get("file_b") or {}
            a_rel = file_a.get("relative_path", "<unknown>")
            b_rel = file_b.get("relative_path", "<unknown>")
            chosen = decisions.get(candidate["id"], "skip")
            summary = f"{index + 1}. [{chosen}] {candidate['source']} A={a_rel} <-> B={b_rel}"
            if candidate["source"] == "fuzzy":
                summary += (
                    f" | score={candidate.get('score', 0):.3f}"
                    f" song={candidate.get('song_similarity', 0):.3f}"
                    f" artist={candidate.get('artist_similarity', 0):.3f}"
                )
            print(summary)

        raw = input("review> ").strip().lower()
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
    filtered_ops, mode_skipped = filter_operations_for_mode(plan_payload["operations"], args.mode)
    plan_payload["operations"] = filtered_ops
    plan_payload["mode"] = args.mode
    plan_payload["mode_skipped_count"] = len(mode_skipped)
    plan_payload["mode_skipped_operations"] = mode_skipped
    plan_payload["counts"]["operations"] = len(filtered_ops)
    plan_payload["counts"]["add_to_b"] = len([op for op in filtered_ops if op.get("action") == "add_to_b"])
    plan_payload["counts"]["replace_in_b_with_a"] = len(
        [op for op in filtered_ops if op.get("action") == "replace_in_b_with_a"]
    )
    plan_payload["counts"]["keep_both_versions"] = len(
        [op for op in filtered_ops if op.get("action") == "keep_both_versions"]
    )
    plan_payload["dir_a"] = str(args.dir_a)
    plan_payload["dir_b"] = str(args.dir_b)
    plan_payload["manual_review_count"] = len(candidates)
    plan_payload["summary"] = review_summary
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
            f"Mode skipped operations ({args.mode}): {plan_payload['mode_skipped_count']}"
        )
    if args.write_plan_json is not None:
        print(f"Reviewed plan saved to: {args.write_plan_json}")
        _print_next_apply_hints(args.dir_a, args.dir_b, args.write_plan_json)
    if args.export_manual_review_json is not None:
        print(f"Manual review export: {args.export_manual_review_json}")
    if args.decisions_file is not None:
        print(f"Decisions saved to: {args.decisions_file}")
    return EXIT_SUCCESS


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "parse":
        return cmd_parse(args)
    if args.command == "compare":
        return cmd_compare(args)
    if args.command == "plan":
        return cmd_plan(args)
    if args.command == "apply":
        return cmd_apply(args)
    if args.command == "review":
        return cmd_review(args)
    if args.command == "help":
        if args.topic:
            subparser = _find_subparser(parser, args.topic)
            if subparser is not None:
                subparser.print_help()
                return 0
        parser.print_help()
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

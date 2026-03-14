# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from ..compare import compare_collections
from ..mode import filter_operations_for_mode
from ..parser import collect_audio_metadata


def normalize_extensions(extensions: list[str]) -> set[str]:
    return {ext if ext.startswith(".") else f".{ext}" for ext in extensions}


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


def collect_audio_pair(dir_a: Path, dir_b: Path, extensions: set[str], progress: bool):
    files_a = collect_audio_metadata(
        dir_a,
        extensions=extensions,
        progress_callback=(make_progress_callback("A") if progress else None),
    )
    files_b = collect_audio_metadata(
        dir_b,
        extensions=extensions,
        progress_callback=(make_progress_callback("B") if progress else None),
    )
    return files_a, files_b


def compare_payload(files_a, files_b, compare_config) -> dict:
    return compare_collections(
        files_a=files_a,
        files_b=files_b,
        **compare_config.as_compare_kwargs(),
    )


def apply_mode_to_plan_payload(
    plan_payload: dict,
    mode: str,
    dir_a: Path,
    dir_b: Path,
    compare_payload: Optional[dict] = None,
) -> dict:
    filtered_ops, mode_skipped = filter_operations_for_mode(plan_payload["operations"], mode)
    plan_payload["operations"] = filtered_ops
    plan_payload["mode"] = mode
    plan_payload["mode_skipped_count"] = len(mode_skipped)
    plan_payload["mode_skipped_operations"] = mode_skipped
    plan_payload["counts"]["operations"] = len(filtered_ops)
    plan_payload["counts"]["add_to_b"] = len(
        [op for op in filtered_ops if op.get("action") == "add_to_b"]
    )
    plan_payload["counts"]["replace_in_b_with_a"] = len(
        [op for op in filtered_ops if op.get("action") == "replace_in_b_with_a"]
    )
    plan_payload["counts"]["keep_both_versions"] = len(
        [op for op in filtered_ops if op.get("action") == "keep_both_versions"]
    )
    plan_payload["dir_a"] = str(dir_a)
    plan_payload["dir_b"] = str(dir_b)
    if compare_payload is not None:
        plan_payload["compare_summary"] = {
            "exact_match_count": compare_payload["exact_match_count"],
            "only_in_a_count": compare_payload["only_in_a_count"],
            "only_in_b_count": compare_payload["only_in_b_count"],
            "fuzzy_candidate_count": compare_payload["fuzzy_candidate_count"],
            "fuzzy_dropped_count": compare_payload.get("fuzzy_dropped_count", 0),
            "fuzzy_rejection_count": compare_payload.get("fuzzy_rejection_count", 0),
            "action_counts": compare_payload["action_counts"],
        }
    return plan_payload


def print_parsed_items(label: str, root: Path, items: list) -> None:
    print(f"{label} ({root}) files: {len(items)}")
    for item in items:
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


def print_next_apply_hints(dir_a: Path, dir_b: Path, plan_path: Path) -> None:
    print("Next commands:")
    print(
        f"  trackloom apply {dir_a} {dir_b} "
        f"--from-plan-json {plan_path} --dry-run"
    )
    print(
        f"  trackloom apply {dir_a} {dir_b} "
        f"--from-plan-json {plan_path} --yes"
    )


def print_apply_change_summary(operations: list[dict], dir_b: str) -> None:
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

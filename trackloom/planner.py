# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set


COPY_ACTIONS = {"add_to_b", "replace_in_b_with_a", "keep_both_versions"}


def _unique_destination(dest_root: Path, relative_path: str, reserved: Set[str]) -> Path:
    base = dest_root / relative_path
    if str(base) not in reserved and not base.exists():
        reserved.add(str(base))
        return base

    stem = base.stem
    suffix = base.suffix
    parent = base.parent
    candidate = parent / f"{stem} (from A){suffix}"
    counter = 2
    while str(candidate) in reserved or candidate.exists():
        candidate = parent / f"{stem} (from A {counter}){suffix}"
        counter += 1
    reserved.add(str(candidate))
    return candidate


def build_copy_plan(compare_payload: Dict[str, Any], dir_b: Path) -> Dict[str, Any]:
    operations: List[Dict[str, Any]] = []
    reserved_destinations: Set[str] = set()

    def maybe_add_operation(
        action: str,
        file_record: Dict[str, Any],
        preferred_relative_path: str | None = None,
        replace_target_path: str | None = None,
    ) -> None:
        if action not in COPY_ACTIONS:
            return
        source_path = Path(file_record["absolute_path"])
        relative_path = file_record["relative_path"]
        preferred_rel = preferred_relative_path or relative_path
        preferred_destination = dir_b / preferred_rel
        destination_path = _unique_destination(dir_b, preferred_rel, reserved_destinations)
        operations.append(
            {
                "action": action,
                "source_path": str(source_path),
                "source_relative_path": relative_path,
                "source_extension": file_record.get("extension"),
                "source_codec": file_record.get("codec"),
                "preferred_destination_path": str(preferred_destination),
                "destination_path": str(destination_path),
                "replace_target_path": replace_target_path,
            }
        )

    for item in compare_payload.get("only_in_a", []):
        maybe_add_operation(item.get("recommended_action"), item.get("file", {}))

    for match in compare_payload.get("exact_matches", []):
        action = match.get("recommended_action")
        file_a = match.get("file_a", {})
        file_b = match.get("file_b", {})
        if action == "replace_in_b_with_a":
            maybe_add_operation(
                action,
                file_a,
                preferred_relative_path=file_b.get("relative_path") or file_a.get("relative_path"),
                replace_target_path=file_b.get("absolute_path"),
            )
        else:
            maybe_add_operation(action, file_a)

    counts = {
        "operations": len(operations),
        "add_to_b": 0,
        "replace_in_b_with_a": 0,
        "keep_both_versions": 0,
    }
    for op in operations:
        if op["action"] in counts:
            counts[op["action"]] += 1

    return {
        "counts": counts,
        "operations": operations,
    }

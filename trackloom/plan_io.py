# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .models import Operation

PLAN_SCHEMA_VERSION = 1

REQUIRED_OPERATION_KEYS = {
    "action",
    "source_path",
    "source_relative_path",
    "destination_path",
}

ALLOWED_ACTIONS = {"add_to_b", "replace_in_b_with_a", "keep_both_versions"}


def write_plan_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data.setdefault("schema_version", PLAN_SCHEMA_VERSION)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def load_plan_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError("Plan JSON must be an object.")

    schema_version = data.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, int):
        raise ValueError("Plan JSON schema_version must be an integer.")
    if schema_version is not None and schema_version > PLAN_SCHEMA_VERSION:
        raise ValueError(
            f"Plan JSON schema_version {schema_version} is newer than supported {PLAN_SCHEMA_VERSION}."
        )

    operations = data.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Plan JSON must include an operations list.")

    normalized_ops: List[Operation] = []
    for idx, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ValueError(f"Operation at index {idx} must be an object.")
        missing = REQUIRED_OPERATION_KEYS - set(op.keys())
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(
                f"Operation at index {idx} missing required key(s): {missing_list}"
            )
        normalized = dict(op)
        normalized["action"] = str(op["action"])
        normalized["source_path"] = str(op["source_path"])
        normalized["source_relative_path"] = str(op["source_relative_path"])
        normalized["destination_path"] = str(op["destination_path"])
        if "preferred_destination_path" in normalized and normalized["preferred_destination_path"] is not None:
            normalized["preferred_destination_path"] = str(normalized["preferred_destination_path"])
        if "replace_target_path" in normalized and normalized["replace_target_path"] is not None:
            normalized["replace_target_path"] = str(normalized["replace_target_path"])
        normalized_ops.append(normalized)

    result = dict(data)
    result["operations"] = normalized_ops
    return result


def _resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _ensure_within(root: Path, path: Path, label: str, idx: int) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Operation at index {idx} has {label} outside {root}"
        ) from exc


def validate_plan_operations(operations: List[Operation], dir_a: Path, dir_b: Path) -> None:
    root_a = _resolve_path(str(dir_a))
    root_b = _resolve_path(str(dir_b))

    for idx, op in enumerate(operations):
        action = op.get("action")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Operation at index {idx} has unsupported action: {action}")

        source_path = _resolve_path(str(op.get("source_path")))
        destination_path = _resolve_path(str(op.get("destination_path")))
        _ensure_within(root_a, source_path, "source_path", idx)
        _ensure_within(root_b, destination_path, "destination_path", idx)

        preferred_destination = op.get("preferred_destination_path")
        preferred_path = None
        if preferred_destination:
            preferred_path = _resolve_path(str(preferred_destination))
            _ensure_within(root_b, preferred_path, "preferred_destination_path", idx)

        replace_target = op.get("replace_target_path")
        replace_path = None
        if replace_target:
            replace_path = _resolve_path(str(replace_target))
            _ensure_within(root_b, replace_path, "replace_target_path", idx)

        if action == "replace_in_b_with_a":
            if not preferred_destination or not replace_target:
                raise ValueError(
                    "Operation at index "
                    f"{idx} replace_in_b_with_a requires preferred_destination_path and replace_target_path"
                )

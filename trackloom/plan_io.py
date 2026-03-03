# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


REQUIRED_OPERATION_KEYS = {
    "action",
    "source_path",
    "source_relative_path",
    "destination_path",
}


def write_plan_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def load_plan_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError("Plan JSON must be an object.")

    operations = data.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Plan JSON must include an operations list.")

    normalized_ops: List[Dict[str, Any]] = []
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

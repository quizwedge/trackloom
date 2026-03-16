# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import ExecuteResult


def write_report_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def write_report_csv(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result: ExecuteResult = payload.get("result", {})
    executed: list[dict[str, Any]] = result.get("executed", [])
    skipped: list[dict[str, Any]] = result.get("skipped", [])

    fieldnames = [
        "status",
        "reason",
        "action",
        "source_path",
        "source_relative_path",
        "destination_path",
        "effective_destination_path",
        "quarantine_from",
        "quarantine_to",
        "quarantine_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for item in executed:
            op = item.get("operation", {})
            quarantine_move = item.get("quarantine_move") or {}
            writer.writerow(
                {
                    "status": item.get("status", ""),
                    "reason": "",
                    "action": op.get("action", ""),
                    "source_path": op.get("source_path", ""),
                    "source_relative_path": op.get("source_relative_path", ""),
                    "destination_path": op.get("destination_path", ""),
                    "effective_destination_path": item.get(
                        "effective_destination_path", ""
                    ),
                    "quarantine_from": quarantine_move.get("from", ""),
                    "quarantine_to": quarantine_move.get("to", ""),
                    "quarantine_status": quarantine_move.get("status", ""),
                }
            )
        for item in skipped:
            op = item.get("operation", {})
            quarantine_move = item.get("quarantine_move") or {}
            writer.writerow(
                {
                    "status": "skipped",
                    "reason": item.get("reason", ""),
                    "action": op.get("action", ""),
                    "source_path": op.get("source_path", ""),
                    "source_relative_path": op.get("source_relative_path", ""),
                    "destination_path": op.get("destination_path", ""),
                    "effective_destination_path": item.get(
                        "effective_destination_path", ""
                    ),
                    "quarantine_from": quarantine_move.get("from", ""),
                    "quarantine_to": quarantine_move.get("to", ""),
                    "quarantine_status": quarantine_move.get("status", ""),
                }
            )

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def write_report_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def write_report_csv(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = payload.get("result", {})
    executed: List[Dict[str, Any]] = result.get("executed", [])
    skipped: List[Dict[str, Any]] = result.get("skipped", [])

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
            writer.writerow(
                {
                    "status": item.get("status", ""),
                    "reason": "",
                    "action": op.get("action", ""),
                    "source_path": op.get("source_path", ""),
                    "source_relative_path": op.get("source_relative_path", ""),
                    "destination_path": op.get("destination_path", ""),
                    "effective_destination_path": item.get("effective_destination_path", ""),
                    "quarantine_from": (item.get("quarantine_move") or {}).get("from", ""),
                    "quarantine_to": (item.get("quarantine_move") or {}).get("to", ""),
                    "quarantine_status": (item.get("quarantine_move") or {}).get("status", ""),
                }
            )
        for item in skipped:
            op = item.get("operation", {})
            writer.writerow(
                {
                    "status": "skipped",
                    "reason": item.get("reason", ""),
                    "action": op.get("action", ""),
                    "source_path": op.get("source_path", ""),
                    "source_relative_path": op.get("source_relative_path", ""),
                    "destination_path": op.get("destination_path", ""),
                    "effective_destination_path": item.get("effective_destination_path", ""),
                    "quarantine_from": (item.get("quarantine_move") or {}).get("from", ""),
                    "quarantine_to": (item.get("quarantine_move") or {}).get("to", ""),
                    "quarantine_status": (item.get("quarantine_move") or {}).get("status", ""),
                }
            )

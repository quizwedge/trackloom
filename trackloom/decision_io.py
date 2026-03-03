# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_decisions(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "decisions" in data:
        raw = data["decisions"]
    else:
        raw = data
    if not isinstance(raw, dict):
        raise ValueError("Decisions JSON must be an object or contain a decisions object.")
    return {str(k): str(v) for k, v in raw.items()}


def write_decisions(path: Path, decisions: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"decisions": decisions}
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


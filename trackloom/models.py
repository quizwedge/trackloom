# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

from typing import List, Optional, TypedDict


class Operation(TypedDict, total=False):
    action: str
    source_path: str
    source_relative_path: str
    source_extension: Optional[str]
    source_codec: Optional[str]
    preferred_destination_path: str
    destination_path: str
    replace_target_path: Optional[str]


class ExecutedOperation(TypedDict, total=False):
    operation: Operation
    effective_destination_path: str
    quarantine_move: dict
    status: str


class SkippedOperation(TypedDict, total=False):
    operation: Operation
    effective_destination_path: str
    quarantine_move: dict
    quarantine_rollback: Optional[str]
    reason: str
    error: str


class ExecuteResult(TypedDict):
    requested_count: int
    executed_count: int
    skipped_count: int
    executed: List[ExecutedOperation]
    skipped: List[SkippedOperation]

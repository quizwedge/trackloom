# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
from __future__ import annotations

from typing import TypedDict


class Operation(TypedDict, total=False):
    action: str
    source_path: str
    source_relative_path: str
    source_extension: str | None
    source_codec: str | None
    preferred_destination_path: str
    destination_path: str
    replace_target_path: str | None


class ExecutedOperation(TypedDict, total=False):
    operation: Operation
    effective_destination_path: str
    quarantine_move: dict
    status: str


class SkippedOperation(TypedDict, total=False):
    operation: Operation
    effective_destination_path: str
    quarantine_move: dict
    quarantine_rollback: str | None
    reason: str
    error: str


class ExecuteResult(TypedDict):
    requested_count: int
    executed_count: int
    skipped_count: int
    executed: list[ExecutedOperation]
    skipped: list[SkippedOperation]

# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
from __future__ import annotations

from pathlib import Path
from typing import Any

MODE_STANDARD = "standard"
MODE_PLEX = "plex"

PLEX_ALLOWED_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".flac",
    ".wav",
    ".ogg",
    ".aac",
    ".wma",
    ".aiff",
    ".aif",
    ".alac",
    ".opus",
}
PLEX_BLOCKED_EXTENSIONS = {".m4p", ".aa", ".aax"}


def _detect_extension(operation: dict[str, Any]) -> str:
    ext = operation.get("source_extension")
    if isinstance(ext, str) and ext:
        return ext.lower()
    src = operation.get("source_path") or operation.get("source_relative_path") or ""
    return Path(str(src)).suffix.lower()


def assess_plex_compatibility(operation: dict[str, Any]) -> tuple[bool, str | None]:
    ext = _detect_extension(operation)
    if ext in PLEX_BLOCKED_EXTENSIONS:
        return False, "drm_or_protected_extension"
    if ext and ext not in PLEX_ALLOWED_EXTENSIONS:
        return False, "unsupported_extension_for_plex_mode"

    codec = operation.get("source_codec")
    if codec is not None:
        text = str(codec).lower()
        if "drms" in text or "protected" in text:
            return False, "drm_or_protected_codec"

    return True, None


def filter_operations_for_mode(
    operations: list[dict[str, Any]], mode: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if mode == MODE_STANDARD:
        return operations, []
    if mode != MODE_PLEX:
        raise ValueError("Unsupported mode: " + mode)

    kept: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for op in operations:
        ok, reason = assess_plex_compatibility(op)
        if ok:
            kept.append(op)
        else:
            skipped.append({"operation": op, "reason": reason})
    return kept, skipped

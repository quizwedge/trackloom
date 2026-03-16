# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .models import ExecutedOperation, ExecuteResult, Operation, SkippedOperation


def _unique_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    counter = 2
    candidate = parent / f"{stem} ({counter}){suffix}"
    while candidate.exists():
        counter += 1
        candidate = parent / f"{stem} ({counter}){suffix}"
    return candidate


def _quarantine_destination(
    target_path: Path, dir_b: Path, quarantine_dir: Path
) -> Path:
    try:
        relative = target_path.relative_to(dir_b)
    except ValueError:
        try:
            relative = target_path.resolve(strict=False).relative_to(
                dir_b.resolve(strict=False)
            )
        except ValueError:
            relative = Path(target_path.name)
    return _unique_path(quarantine_dir / relative)


def _paths_equivalent(left: Path, right: Path) -> bool:
    return left.resolve(strict=False) == right.resolve(strict=False)


def _path_lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _copy_with_atomic_no_overwrite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".trackloom_tmp_", suffix=destination.suffix, dir=destination.parent
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    placeholder_created = False
    try:
        shutil.copy2(source, tmp_path)
        try:
            os.link(str(tmp_path), str(destination))
            tmp_path.unlink()
            return
        except FileExistsError:
            raise
        except OSError:
            fd_dest = os.open(str(destination), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd_dest)
            placeholder_created = True
            tmp_path.replace(destination)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
            if placeholder_created and _path_lexists(destination):
                destination.unlink()
        except Exception:
            pass
        raise


def execute_operations(
    operations: list[Operation],
    dry_run: bool = False,
    cleanup_mode: str = "none",
    quarantine_dir: Path | None = None,
    dir_b: Path | None = None,
) -> ExecuteResult:
    if cleanup_mode not in {"none", "move-to-quarantine"}:
        raise ValueError("cleanup_mode must be 'none' or 'move-to-quarantine'")
    if cleanup_mode == "move-to-quarantine":
        if quarantine_dir is None:
            raise ValueError("quarantine_dir is required for move-to-quarantine mode")
        if dir_b is None:
            raise ValueError("dir_b is required for move-to-quarantine mode")

    executed: list[ExecutedOperation] = []
    skipped: list[SkippedOperation] = []

    for operation in operations:
        src = Path(operation["source_path"])
        dst = Path(operation["destination_path"])
        preferred_dst_raw = operation.get("preferred_destination_path")
        preferred_dst = Path(preferred_dst_raw) if preferred_dst_raw else dst
        replace_target_raw = operation.get("replace_target_path")
        replace_target = Path(replace_target_raw) if replace_target_raw else None
        action = operation.get("action")
        quarantine_move = None
        preferred_differs = (
            action == "replace_in_b_with_a"
            and replace_target is not None
            and not _paths_equivalent(preferred_dst, replace_target)
        )
        should_quarantine = (
            cleanup_mode == "move-to-quarantine"
            and action == "replace_in_b_with_a"
            and replace_target is not None
            and _path_lexists(replace_target)
        )
        if action == "replace_in_b_with_a":
            if should_quarantine:
                effective_dst = preferred_dst
            else:
                effective_dst = (
                    preferred_dst if not _path_lexists(preferred_dst) else dst
                )
        else:
            effective_dst = dst

        try:
            if not src.exists():
                skipped.append(
                    {
                        "operation": operation,
                        "reason": "source_missing",
                    }
                )
                continue
            if (
                preferred_differs
                and replace_target is not None
                and _path_lexists(replace_target)
                and cleanup_mode != "move-to-quarantine"
            ):
                skipped.append(
                    {
                        "operation": operation,
                        "effective_destination_path": str(preferred_dst),
                        "quarantine_move": quarantine_move,
                        "reason": "replace_requires_quarantine",
                    }
                )
                continue

            will_clear_effective_dst = (
                should_quarantine
                and replace_target is not None
                and _paths_equivalent(effective_dst, replace_target)
            )
            destination_blocked = (
                _path_lexists(effective_dst) and not will_clear_effective_dst
            )
            if destination_blocked:
                skipped.append(
                    {
                        "operation": operation,
                        "effective_destination_path": str(effective_dst),
                        "quarantine_move": quarantine_move,
                        "reason": "destination_exists",
                    }
                )
                continue

            if should_quarantine:
                qdst = _quarantine_destination(replace_target, dir_b, quarantine_dir)
                if dry_run:
                    quarantine_move = {
                        "from": str(replace_target),
                        "to": str(qdst),
                        "status": "dry_run",
                    }
                else:
                    qdst.parent.mkdir(parents=True, exist_ok=True)
                    replace_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(replace_target), str(qdst))
                    quarantine_move = {
                        "from": str(replace_target),
                        "to": str(qdst),
                        "status": "moved",
                    }

            if dry_run:
                executed.append(
                    {
                        "operation": operation,
                        "effective_destination_path": str(effective_dst),
                        "quarantine_move": quarantine_move,
                        "status": "dry_run",
                    }
                )
                continue

            _copy_with_atomic_no_overwrite(src, effective_dst)
            executed.append(
                {
                    "operation": operation,
                    "effective_destination_path": str(effective_dst),
                    "quarantine_move": quarantine_move,
                    "status": "copied",
                }
            )
        except FileExistsError:
            rollback_status = None
            if (
                quarantine_move
                and quarantine_move.get("status") == "moved"
                and replace_target is not None
            ):
                moved_to = Path(quarantine_move["to"])
                try:
                    if moved_to.exists() and not _path_lexists(replace_target):
                        replace_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(moved_to), str(replace_target))
                        rollback_status = "rolled_back"
                except Exception:
                    rollback_status = "rollback_failed"
            skipped.append(
                {
                    "operation": operation,
                    "effective_destination_path": str(effective_dst),
                    "quarantine_move": quarantine_move,
                    "quarantine_rollback": rollback_status,
                    "reason": "destination_exists",
                }
            )
            continue
        except Exception as err:
            rollback_status = None
            if (
                quarantine_move
                and quarantine_move.get("status") == "moved"
                and replace_target is not None
            ):
                moved_to = Path(quarantine_move["to"])
                try:
                    if moved_to.exists() and not _path_lexists(replace_target):
                        replace_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(moved_to), str(replace_target))
                        rollback_status = "rolled_back"
                except Exception:
                    rollback_status = "rollback_failed"
            skipped.append(
                {
                    "operation": operation,
                    "effective_destination_path": str(effective_dst),
                    "quarantine_move": quarantine_move,
                    "quarantine_rollback": rollback_status,
                    "reason": "io_error",
                    "error": str(err),
                }
            )
            continue

    return {
        "requested_count": len(operations),
        "executed_count": len(executed),
        "skipped_count": len(skipped),
        "executed": executed,
        "skipped": skipped,
    }

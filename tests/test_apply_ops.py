# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trackloom.apply_ops import (
    _copy_with_atomic_no_overwrite,
    _quarantine_destination,
    execute_operations,
)


class ApplyOpsTests(unittest.TestCase):
    def test_copy_with_atomic_no_overwrite_falls_back_when_link_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.mp3"
            dst = root / "nested" / "song.mp3"
            src.write_text("audio")

            with patch("trackloom.apply_ops.os.link", side_effect=OSError("no link")):
                _copy_with_atomic_no_overwrite(src, dst)

            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_text(), "audio")
            temp_files = [
                p for p in dst.parent.iterdir() if p.name.startswith(".trackloom_tmp_")
            ]
            self.assertEqual(temp_files, [])

    def test_copy_with_atomic_no_overwrite_cleans_placeholder_on_replace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.mp3"
            dst = root / "nested" / "song.mp3"
            src.write_text("audio")

            original_replace = Path.replace

            def flaky_replace(path_obj, target):
                if path_obj.name.startswith(".trackloom_tmp_"):
                    raise OSError("replace failed")
                return original_replace(path_obj, target)

            with patch(
                "trackloom.apply_ops.os.link", side_effect=OSError("no link")
            ), patch("pathlib.Path.replace", new=flaky_replace), self.assertRaises(
                OSError
            ):
                _copy_with_atomic_no_overwrite(src, dst)

            self.assertFalse(dst.exists())

    def test_copy_with_atomic_no_overwrite_ignores_cleanup_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.mp3"
            dst = root / "nested" / "song.mp3"
            src.write_text("audio")

            original_exists = Path.exists
            original_unlink = Path.unlink

            def fake_exists(path_obj):
                if path_obj.name.startswith(".trackloom_tmp_"):
                    return True
                return original_exists(path_obj)

            def fake_unlink(path_obj, *args, **kwargs):
                if path_obj.name.startswith(".trackloom_tmp_"):
                    raise OSError("cleanup failed")
                return original_unlink(path_obj, *args, **kwargs)

            with patch(
                "trackloom.apply_ops.shutil.copy2",
                side_effect=OSError("copy failed"),
            ), patch("pathlib.Path.exists", new=fake_exists), patch(
                "pathlib.Path.unlink", new=fake_unlink
            ), self.assertRaises(OSError):
                _copy_with_atomic_no_overwrite(src, dst)

            self.assertFalse(dst.exists())

    def test_execute_operations_skips_missing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "src" / "missing.mp3"
            dst = root / "dst" / "song.mp3"

            result = execute_operations(
                [
                    {
                        "action": "add_to_b",
                        "source_path": str(missing),
                        "destination_path": str(dst),
                    }
                ]
            )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "source_missing")

    def test_execute_operations_copies_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            result = execute_operations(
                [
                    {
                        "action": "add_to_b",
                        "source_path": str(src),
                        "destination_path": str(dst),
                    }
                ]
            )

            self.assertTrue(dst.exists())
            self.assertEqual(result["executed_count"], 1)
            self.assertEqual(result["skipped_count"], 0)

    def test_execute_operations_skips_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            dst.parent.mkdir(parents=True)
            src.write_text("hello")
            dst.write_text("existing")

            result = execute_operations(
                [
                    {
                        "action": "add_to_b",
                        "source_path": str(src),
                        "destination_path": str(dst),
                    }
                ]
            )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "destination_exists")

    def test_execute_operations_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            result = execute_operations(
                [
                    {
                        "action": "add_to_b",
                        "source_path": str(src),
                        "destination_path": str(dst),
                    }
                ],
                dry_run=True,
            )

            self.assertFalse(dst.exists())
            self.assertEqual(result["executed_count"], 1)
            self.assertEqual(result["executed"][0]["status"], "dry_run")

    def test_replace_with_quarantine_moves_old_file_then_copies_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"
            preferred_dst = dir_b / "Artist" / "Album" / "song.wav"
            planned_dst = dir_b / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(preferred_dst),
                "destination_path": str(planned_dst),
                "replace_target_path": str(old_b),
            }
            result = execute_operations(
                [operation],
                cleanup_mode="move-to-quarantine",
                quarantine_dir=quarantine,
                dir_b=dir_b,
            )

            self.assertEqual(result["executed_count"], 1)
            self.assertTrue(preferred_dst.exists())
            self.assertFalse(planned_dst.exists())
            moved = quarantine / "Artist" / "Album" / "song.mp3"
            self.assertTrue(moved.exists())
            self.assertEqual(preferred_dst.read_text(), "new")
            self.assertEqual(moved.read_text(), "old")

    def test_replace_with_quarantine_dry_run_reports_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"
            preferred_dst = dir_b / "Artist" / "Album" / "song.wav"
            planned_dst = dir_b / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(preferred_dst),
                "destination_path": str(planned_dst),
                "replace_target_path": str(old_b),
            }
            result = execute_operations(
                [operation],
                dry_run=True,
                cleanup_mode="move-to-quarantine",
                quarantine_dir=quarantine,
                dir_b=dir_b,
            )

            self.assertEqual(result["executed_count"], 1)
            self.assertEqual(result["skipped_count"], 0)
            self.assertEqual(result["executed"][0]["status"], "dry_run")
            self.assertEqual(
                result["executed"][0]["quarantine_move"]["status"], "dry_run"
            )
            self.assertTrue(old_b.exists())
            self.assertFalse(quarantine.exists())

    def test_replace_with_quarantine_skips_without_moving_when_destination_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"
            existing_dst = dir_b / "Artist" / "Album" / "song.wav"
            planned_dst = dir_b / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            existing_dst.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("new")
            old_b.write_text("old")
            existing_dst.write_text("existing")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(existing_dst),
                "destination_path": str(planned_dst),
                "replace_target_path": str(old_b),
            }
            result = execute_operations(
                [operation],
                cleanup_mode="move-to-quarantine",
                quarantine_dir=quarantine,
                dir_b=dir_b,
            )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "destination_exists")
            self.assertTrue(old_b.exists())
            self.assertEqual(old_b.read_text(), "old")
            self.assertFalse(quarantine.exists())

    def test_replace_without_target_uses_preferred_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            src = root / "a" / "song.wav"
            preferred_dst = dir_b / "Artist" / "Album" / "song.mp3"
            planned_dst = dir_b / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            src.write_text("new")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(preferred_dst),
                "destination_path": str(planned_dst),
                "replace_target_path": str(preferred_dst),
            }
            result = execute_operations([operation])

            self.assertEqual(result["executed_count"], 1)
            self.assertTrue(preferred_dst.exists())
            self.assertFalse(planned_dst.exists())
            self.assertEqual(preferred_dst.read_text(), "new")

    def test_replace_with_quarantine_allows_symlinked_dir_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b_real = root / "library_b_real"
            dir_b_real.mkdir(parents=True)
            dir_b_link = root / "library_b"
            try:
                dir_b_link.symlink_to(dir_b_real, target_is_directory=True)
            except OSError:
                self.skipTest("symlink not supported on this platform")

            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b_real / "Artist" / "Album" / "song.mp3"
            preferred_dst = dir_b_link / "Artist" / "Album" / "song.wav"
            planned_dst = dir_b_link / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(preferred_dst),
                "destination_path": str(planned_dst),
                "replace_target_path": str(old_b),
            }
            result = execute_operations(
                [operation],
                cleanup_mode="move-to-quarantine",
                quarantine_dir=quarantine,
                dir_b=dir_b_link,
            )

            self.assertEqual(result["executed_count"], 1)
            self.assertTrue(preferred_dst.exists())
            moved = quarantine / "Artist" / "Album" / "song.mp3"
            self.assertTrue(moved.exists())

    def test_replace_requires_quarantine_when_destination_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"
            preferred_dst = dir_b / "Artist" / "Album" / "song.wav"
            planned_dst = dir_b / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(preferred_dst),
                "destination_path": str(planned_dst),
                "replace_target_path": str(old_b),
            }
            result = execute_operations([operation])

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(
                result["skipped"][0]["reason"], "replace_requires_quarantine"
            )
            self.assertTrue(old_b.exists())
            self.assertFalse(preferred_dst.exists())

    def test_quarantine_mode_requires_quarantine_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.mp3"
            src.write_text("x")
            with self.assertRaises(ValueError):
                execute_operations(
                    [
                        {
                            "action": "add_to_b",
                            "source_path": str(src),
                            "destination_path": str(root / "d.mp3"),
                        }
                    ],
                    cleanup_mode="move-to-quarantine",
                    dir_b=root,
                )

    def test_quarantine_mode_requires_dir_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.mp3"
            src.write_text("x")
            with self.assertRaises(ValueError):
                execute_operations(
                    [
                        {
                            "action": "add_to_b",
                            "source_path": str(src),
                            "destination_path": str(root / "d.mp3"),
                        }
                    ],
                    cleanup_mode="move-to-quarantine",
                    quarantine_dir=root / "quarantine",
                )

    def test_invalid_cleanup_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            execute_operations([], cleanup_mode="delete")

    def test_execute_operations_continues_after_io_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src1 = root / "src" / "bad.mp3"
            src2 = root / "src" / "good.mp3"
            dst1 = root / "dst" / "bad.mp3"
            dst2 = root / "dst" / "good.mp3"
            src1.parent.mkdir(parents=True)
            src1.write_text("bad")
            src2.write_text("good")

            original_copy2 = __import__("shutil").copy2

            def flaky_copy2(src, dst, *args, **kwargs):
                if Path(src) == src1:
                    raise OSError("simulated copy failure")
                return original_copy2(src, dst, *args, **kwargs)

            operations = [
                {
                    "action": "add_to_b",
                    "source_path": str(src1),
                    "destination_path": str(dst1),
                },
                {
                    "action": "add_to_b",
                    "source_path": str(src2),
                    "destination_path": str(dst2),
                },
            ]
            with patch("trackloom.apply_ops.shutil.copy2", side_effect=flaky_copy2):
                result = execute_operations(operations)

            self.assertEqual(result["requested_count"], 2)
            self.assertEqual(result["executed_count"], 1)
            self.assertEqual(result["skipped_count"], 1)
            self.assertTrue(dst2.exists())
            self.assertFalse(dst1.exists())
            self.assertEqual(result["skipped"][0]["reason"], "io_error")

    def test_execute_operations_skips_broken_symlink_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            dst.parent.mkdir(parents=True)
            src.write_text("hello")
            try:
                dst.symlink_to(root / "missing.mp3")
            except OSError:
                self.skipTest("symlink not supported on this platform")

            result = execute_operations(
                [
                    {
                        "action": "add_to_b",
                        "source_path": str(src),
                        "destination_path": str(dst),
                    }
                ]
            )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "destination_exists")
            self.assertTrue(os.path.lexists(dst))

    def test_execute_operations_handles_racy_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            with patch("trackloom.apply_ops.os.link", side_effect=FileExistsError):
                result = execute_operations(
                    [
                        {
                            "action": "add_to_b",
                            "source_path": str(src),
                            "destination_path": str(dst),
                        }
                    ]
                )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "destination_exists")
            self.assertFalse(dst.exists())

    def test_partial_copy_cleanup_does_not_leave_temp_or_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            src.write_text("new")

            def flaky_copy2(source, dest, *args, **kwargs):
                Path(dest).write_text("partial")
                raise OSError("simulated copy failure")

            with patch("trackloom.apply_ops.shutil.copy2", side_effect=flaky_copy2):
                result = execute_operations(
                    [
                        {
                            "action": "add_to_b",
                            "source_path": str(src),
                            "destination_path": str(dst),
                        }
                    ]
                )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertFalse(dst.exists())
            if dst.parent.exists():
                temp_files = [
                    p.name
                    for p in dst.parent.iterdir()
                    if p.name.startswith(".trackloom_tmp_")
                ]
                self.assertEqual(temp_files, [])

    def test_replace_quarantine_rolls_back_on_copy_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"
            planned_dst = dir_b / "Artist" / "Album" / "song (from A).wav"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(old_b),
                "destination_path": str(planned_dst),
                "replace_target_path": str(old_b),
            }

            with patch(
                "trackloom.apply_ops.shutil.copy2", side_effect=OSError("copy failure")
            ):
                result = execute_operations(
                    [operation],
                    cleanup_mode="move-to-quarantine",
                    quarantine_dir=quarantine,
                    dir_b=dir_b,
                )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "io_error")
            self.assertEqual(result["skipped"][0]["quarantine_rollback"], "rolled_back")
            self.assertTrue(old_b.exists())
            self.assertEqual(old_b.read_text(), "old")
            self.assertFalse((quarantine / "Artist" / "Album" / "song.mp3").exists())

    def test_replace_destination_exists_after_quarantine_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(old_b),
                "destination_path": str(
                    dir_b / "Artist" / "Album" / "song (from A).wav"
                ),
                "replace_target_path": str(old_b),
            }

            with patch(
                "trackloom.apply_ops._copy_with_atomic_no_overwrite",
                side_effect=FileExistsError,
            ):
                result = execute_operations(
                    [operation],
                    cleanup_mode="move-to-quarantine",
                    quarantine_dir=quarantine,
                    dir_b=dir_b,
                )

            self.assertEqual(result["skipped"][0]["reason"], "destination_exists")
            self.assertEqual(result["skipped"][0]["quarantine_rollback"], "rolled_back")
            self.assertTrue(old_b.exists())

    def test_replace_quarantine_rollback_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            src = root / "a" / "song.wav"
            old_b = dir_b / "Artist" / "Album" / "song.mp3"

            src.parent.mkdir(parents=True)
            old_b.parent.mkdir(parents=True)
            src.write_text("new")
            old_b.write_text("old")

            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(src),
                "source_relative_path": "Artist/Album/song.wav",
                "preferred_destination_path": str(old_b),
                "destination_path": str(
                    dir_b / "Artist" / "Album" / "song (from A).wav"
                ),
                "replace_target_path": str(old_b),
            }
            qdst = quarantine / "Artist" / "Album" / "song.mp3"
            original_move = __import__("shutil").move

            def flaky_move(source, dest, *args, **kwargs):
                if Path(source) == qdst:
                    raise OSError("rollback failed")
                return original_move(source, dest, *args, **kwargs)

            with patch(
                "trackloom.apply_ops._copy_with_atomic_no_overwrite",
                side_effect=FileExistsError,
            ), patch("trackloom.apply_ops.shutil.move", side_effect=flaky_move):
                result = execute_operations(
                    [operation],
                    cleanup_mode="move-to-quarantine",
                    quarantine_dir=quarantine,
                    dir_b=dir_b,
                )

            self.assertEqual(result["executed_count"], 0)
            self.assertEqual(result["skipped_count"], 1)
            self.assertEqual(result["skipped"][0]["reason"], "destination_exists")
            self.assertEqual(
                result["skipped"][0]["quarantine_rollback"], "rollback_failed"
            )
            self.assertFalse(old_b.exists())
            self.assertTrue(qdst.exists())

    def test_quarantine_destination_uses_unique_suffix_and_outside_dir_basename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_b = root / "library_b"
            quarantine = root / "quarantine"
            existing = quarantine / "song.mp3"
            existing_two = quarantine / "song (2).mp3"
            existing.parent.mkdir(parents=True)
            existing.write_text("old")
            existing_two.write_text("older")

            target = root / "elsewhere" / "song.mp3"
            destination = _quarantine_destination(target, dir_b, quarantine)

            self.assertEqual(destination, quarantine / "song (3).mp3")


if __name__ == "__main__":
    unittest.main()

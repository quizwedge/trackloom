# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trackloom.apply_ops import execute_operations


class ApplyOpsTests(unittest.TestCase):
    def test_execute_operations_copies_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "song.mp3"
            dst = root / "dst" / "song.mp3"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            result = execute_operations(
                [{"action": "add_to_b", "source_path": str(src), "destination_path": str(dst)}]
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
                [{"action": "add_to_b", "source_path": str(src), "destination_path": str(dst)}]
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
                [{"action": "add_to_b", "source_path": str(src), "destination_path": str(dst)}],
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
            preferred_dst = old_b
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

    def test_quarantine_mode_requires_quarantine_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.mp3"
            src.write_text("x")
            with self.assertRaises(ValueError):
                execute_operations(
                    [{"action": "add_to_b", "source_path": str(src), "destination_path": str(root / "d.mp3")}],
                    cleanup_mode="move-to-quarantine",
                    dir_b=root,
                )

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
                {"action": "add_to_b", "source_path": str(src1), "destination_path": str(dst1)},
                {"action": "add_to_b", "source_path": str(src2), "destination_path": str(dst2)},
            ]
            with patch("trackloom.apply_ops.shutil.copy2", side_effect=flaky_copy2):
                result = execute_operations(operations)

            self.assertEqual(result["requested_count"], 2)
            self.assertEqual(result["executed_count"], 1)
            self.assertEqual(result["skipped_count"], 1)
            self.assertTrue(dst2.exists())
            self.assertFalse(dst1.exists())
            self.assertEqual(result["skipped"][0]["reason"], "io_error")

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

            with patch("trackloom.apply_ops.shutil.copy2", side_effect=OSError("copy failure")):
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


if __name__ == "__main__":
    unittest.main()

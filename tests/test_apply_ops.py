# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

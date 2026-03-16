# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import tempfile
import unittest
from pathlib import Path

from trackloom.planner import build_copy_plan


class PlannerTests(unittest.TestCase):
    def test_build_copy_plan_includes_copy_actions_only(self):
        payload = {
            "only_in_a": [
                {
                    "recommended_action": "add_to_b",
                    "file": {
                        "absolute_path": "/src/a/song1.mp3",
                        "relative_path": "Artist/Album/song1.mp3",
                    },
                }
            ],
            "exact_matches": [
                {
                    "recommended_action": "replace_in_b_with_a",
                    "file_a": {
                        "absolute_path": "/src/a/song2.wav",
                        "relative_path": "Artist/Album/song2.wav",
                    },
                },
                {
                    "recommended_action": "keep_b",
                    "file_a": {
                        "absolute_path": "/src/a/song3.mp3",
                        "relative_path": "Artist/Album/song3.mp3",
                    },
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_copy_plan(payload, Path(tmp))

        self.assertEqual(plan["counts"]["operations"], 2)
        actions = [op["action"] for op in plan["operations"]]
        self.assertEqual(actions, ["add_to_b", "replace_in_b_with_a"])

    def test_build_copy_plan_deconflicts_destination_names(self):
        payload = {
            "only_in_a": [
                {
                    "recommended_action": "add_to_b",
                    "file": {
                        "absolute_path": "/src/a/song1.mp3",
                        "relative_path": "Artist/Album/song1.mp3",
                    },
                },
                {
                    "recommended_action": "keep_both_versions",
                    "file": {
                        "absolute_path": "/src/a/song1-alt.mp3",
                        "relative_path": "Artist/Album/song1.mp3",
                    },
                },
            ],
            "exact_matches": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Artist" / "Album").mkdir(parents=True)
            (root / "Artist" / "Album" / "song1.mp3").touch()
            plan = build_copy_plan(payload, root)

        self.assertEqual(plan["counts"]["operations"], 2)
        destinations = [Path(op["destination_path"]).name for op in plan["operations"]]
        self.assertEqual(destinations[0], "song1 (from A).mp3")
        self.assertEqual(destinations[1], "song1 (from A 2).mp3")

    def test_replace_uses_b_directory_with_a_filename(self):
        payload = {
            "only_in_a": [],
            "exact_matches": [
                {
                    "recommended_action": "replace_in_b_with_a",
                    "file_a": {
                        "absolute_path": "/src/a/Artist/Album/newname.flac",
                        "relative_path": "Artist/Album/newname.flac",
                    },
                    "file_b": {
                        "absolute_path": "/dst/b/Artist/Album/oldname.mp3",
                        "relative_path": "Artist/Album/oldname.mp3",
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_copy_plan(payload, Path(tmp))

        op = plan["operations"][0]
        self.assertTrue(
            op["preferred_destination_path"].endswith("Artist/Album/newname.flac")
        )
        self.assertEqual(op["replace_target_path"], "/dst/b/Artist/Album/oldname.mp3")


if __name__ == "__main__":
    unittest.main()

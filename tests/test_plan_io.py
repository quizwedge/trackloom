# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import json
import tempfile
import unittest
from pathlib import Path

from trackloom.plan_io import load_plan_json, write_plan_json


class PlanIoTests(unittest.TestCase):
    def test_write_and_load_plan_json_round_trip(self):
        payload = {
            "operations": [
                {
                    "action": "add_to_b",
                    "source_path": "/tmp/a.mp3",
                    "source_relative_path": "Artist/Album/a.mp3",
                    "destination_path": "/tmp/b.mp3",
                }
            ],
            "counts": {"operations": 1},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plans" / "plan.json"
            write_plan_json(path, payload)
            self.assertTrue(path.exists())
            loaded = load_plan_json(path)
        self.assertEqual(loaded["operations"][0]["action"], "add_to_b")

    def test_load_plan_json_success(self):
        payload = {
            "operations": [
                {
                    "action": "add_to_b",
                    "source_path": "/tmp/a.mp3",
                    "source_relative_path": "Artist/Album/a.mp3",
                    "destination_path": "/tmp/b.mp3",
                    "preferred_destination_path": "/tmp/b.mp3",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_plan_json(path)
        self.assertEqual(len(loaded["operations"]), 1)
        self.assertEqual(loaded["operations"][0]["action"], "add_to_b")
        self.assertEqual(loaded["operations"][0]["preferred_destination_path"], "/tmp/b.mp3")

    def test_load_plan_json_missing_key(self):
        payload = {
            "operations": [
                {
                    "action": "add_to_b",
                    "source_path": "/tmp/a.mp3",
                    "destination_path": "/tmp/b.mp3",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan_json(path)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import json
import tempfile
import unittest
from pathlib import Path

from trackloom.plan_io import load_plan_json, validate_plan_operations, write_plan_json


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
            raw = path.read_text(encoding="utf-8")
            loaded = load_plan_json(path)
        self.assertEqual(loaded["operations"][0]["action"], "add_to_b")
        self.assertIn("schema_version", loaded)
        self.assertTrue(raw.endswith("\n"))

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
        self.assertEqual(
            loaded["operations"][0]["preferred_destination_path"], "/tmp/b.mp3"
        )

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

    def test_load_plan_json_rejects_non_object_schema_version_and_operation_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(
                json.dumps({"schema_version": "1", "operations": []}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_plan_json(path)

            path.write_text(
                json.dumps({"schema_version": 1, "operations": ["bad"]}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_plan_json(path)

    def test_load_plan_json_stringifies_path_fields_but_preserves_none(self):
        payload = {
            "schema_version": 1,
            "operations": [
                {
                    "action": "replace_in_b_with_a",
                    "source_path": Path("/tmp/a.wav"),
                    "source_relative_path": Path("Artist/Album/a.wav"),
                    "destination_path": Path("/tmp/b.wav"),
                    "preferred_destination_path": None,
                    "replace_target_path": None,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(payload, default=str), encoding="utf-8")
            loaded = load_plan_json(path)

        op = loaded["operations"][0]
        self.assertEqual(op["source_path"], "/tmp/a.wav")
        self.assertEqual(op["source_relative_path"], "Artist/Album/a.wav")
        self.assertIsNone(op["preferred_destination_path"])
        self.assertIsNone(op["replace_target_path"])

    def test_validate_plan_rejects_source_outside_dir_a(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "a"
            dir_b = root / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            operation = {
                "action": "add_to_b",
                "source_path": str(root / "outside.mp3"),
                "source_relative_path": "outside.mp3",
                "destination_path": str(dir_b / "song.mp3"),
            }
            with self.assertRaises(ValueError):
                validate_plan_operations([operation], dir_a, dir_b)

    def test_validate_plan_rejects_destination_outside_dir_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "a"
            dir_b = root / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            operation = {
                "action": "add_to_b",
                "source_path": str(dir_a / "song.mp3"),
                "source_relative_path": "song.mp3",
                "destination_path": str(root / "outside.mp3"),
            }
            with self.assertRaises(ValueError):
                validate_plan_operations([operation], dir_a, dir_b)

    def test_validate_plan_rejects_unknown_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "a"
            dir_b = root / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            operation = {
                "action": "delete_everything",
                "source_path": str(dir_a / "song.mp3"),
                "source_relative_path": "song.mp3",
                "destination_path": str(dir_b / "song.mp3"),
            }
            with self.assertRaises(ValueError):
                validate_plan_operations([operation], dir_a, dir_b)

    def test_validate_plan_replace_requires_preferred_and_replace_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "a"
            dir_b = root / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(dir_a / "song.wav"),
                "source_relative_path": "song.wav",
                "destination_path": str(dir_b / "song (from A).wav"),
            }
            with self.assertRaises(ValueError):
                validate_plan_operations([operation], dir_a, dir_b)

    def test_validate_plan_replace_allows_different_preferred_and_replace_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "a"
            dir_b = root / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            operation = {
                "action": "replace_in_b_with_a",
                "source_path": str(dir_a / "song.wav"),
                "source_relative_path": "song.wav",
                "destination_path": str(dir_b / "song (from A).wav"),
                "preferred_destination_path": str(dir_b / "song.mp3"),
                "replace_target_path": str(dir_b / "other.mp3"),
            }
            validate_plan_operations([operation], dir_a, dir_b)

    def test_validate_plan_checks_preferred_and_replace_target_stay_within_dir_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "a"
            dir_b = root / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            op_bad_preferred = {
                "action": "replace_in_b_with_a",
                "source_path": str(dir_a / "song.wav"),
                "source_relative_path": "song.wav",
                "destination_path": str(dir_b / "song (from A).wav"),
                "preferred_destination_path": str(root / "outside-preferred.wav"),
                "replace_target_path": str(dir_b / "song.wav"),
            }
            op_bad_replace = {
                "action": "replace_in_b_with_a",
                "source_path": str(dir_a / "song.wav"),
                "source_relative_path": "song.wav",
                "destination_path": str(dir_b / "song (from A).wav"),
                "preferred_destination_path": str(dir_b / "song.wav"),
                "replace_target_path": str(root / "outside-replace.wav"),
            }

            with self.assertRaises(ValueError):
                validate_plan_operations([op_bad_preferred], dir_a, dir_b)
            with self.assertRaises(ValueError):
                validate_plan_operations([op_bad_replace], dir_a, dir_b)

    def test_load_plan_rejects_future_schema_version(self):
        payload = {
            "schema_version": 999,
            "operations": [
                {
                    "action": "add_to_b",
                    "source_path": "/tmp/a.mp3",
                    "source_relative_path": "Artist/Album/a.mp3",
                    "destination_path": "/tmp/b.mp3",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_plan_json(path)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import json
import tempfile
import unittest
from pathlib import Path

from trackloom.decision_io import load_decisions, write_decisions


class DecisionIoTests(unittest.TestCase):
    def test_load_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            loaded = load_decisions(path)
        self.assertEqual(loaded, {})

    def test_write_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            write_decisions(path, {"fuzzy:1": "replace_in_b_with_a"})
            raw = path.read_text(encoding="utf-8")
            loaded = load_decisions(path)
        self.assertEqual(loaded["fuzzy:1"], "replace_in_b_with_a")
        self.assertTrue(raw.endswith("\n"))
        self.assertIn('"decisions"', raw)

    def test_load_plain_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            path.write_text(json.dumps({"exact:2": "keep_b"}), encoding="utf-8")
            loaded = load_decisions(path)
        self.assertEqual(loaded["exact:2"], "keep_b")

    def test_load_decisions_rejects_non_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            path.write_text(json.dumps(["bad"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_decisions(path)

    def test_load_decisions_stringifies_keys_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            path.write_text(json.dumps({"decisions": {1: 2}}), encoding="utf-8")
            loaded = load_decisions(path)
        self.assertEqual(loaded, {"1": "2"})


if __name__ == "__main__":
    unittest.main()

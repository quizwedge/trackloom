# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
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
            loaded = load_decisions(path)
        self.assertEqual(loaded["fuzzy:1"], "replace_in_b_with_a")

    def test_load_plain_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.json"
            path.write_text(json.dumps({"exact:2": "keep_b"}), encoding="utf-8")
            loaded = load_decisions(path)
        self.assertEqual(loaded["exact:2"], "keep_b")


if __name__ == "__main__":
    unittest.main()

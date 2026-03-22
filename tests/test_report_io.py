# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import csv
import json
import tempfile
import unittest
from pathlib import Path

from trackloom.report_io import write_report_csv, write_report_json


class ReportIoTests(unittest.TestCase):
    def test_write_report_json(self):
        payload = {"foo": "bar"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reports" / "report.json"
            write_report_json(path, payload)
            raw = path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
        self.assertEqual(loaded["foo"], "bar")
        self.assertTrue(raw.endswith("\n"))

    def test_write_report_csv(self):
        payload = {
            "result": {
                "executed": [
                    {
                        "status": "copied",
                        "operation": {
                            "action": "add_to_b",
                            "source_path": "/tmp/a.mp3",
                            "source_relative_path": "Artist/Album/a.mp3",
                            "destination_path": "/tmp/b.mp3",
                        },
                    }
                ],
                "skipped": [
                    {
                        "reason": "destination_exists",
                        "operation": {
                            "action": "replace_in_b_with_a",
                            "source_path": "/tmp/c.flac",
                            "source_relative_path": "Artist/Album/c.flac",
                            "destination_path": "/tmp/d.flac",
                        },
                    }
                ],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reports" / "report.csv"
            write_report_csv(path, payload)
            with path.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["status"], "copied")
        self.assertEqual(rows[1]["status"], "skipped")
        self.assertEqual(rows[1]["reason"], "destination_exists")

    def test_write_report_csv_handles_missing_optional_fields(self):
        payload = {
            "result": {
                "executed": [{"operation": {"action": "add_to_b"}}],
                "skipped": [{"operation": {"action": "keep_both_versions"}}],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reports" / "report.csv"
            write_report_csv(path, payload)
            with path.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(rows[0]["status"], "")
        self.assertEqual(rows[0]["source_path"], "")
        self.assertEqual(rows[1]["status"], "skipped")
        self.assertEqual(rows[1]["reason"], "")


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import csv
import tempfile
import unittest
from pathlib import Path

from trackloom.decision_io import load_decisions
from trackloom.plan_io import load_plan_json
from trackloom.report_io import write_report_csv

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "contracts"


class ContractCompatibilityTests(unittest.TestCase):
    def test_plan_v1_fixture_loads_with_expected_required_fields(self):
        payload = load_plan_json(FIXTURES / "plan_schema_v1_add.json")

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["operations"]), 1)
        operation = payload["operations"][0]
        self.assertEqual(
            set(["action", "source_path", "source_relative_path", "destination_path"])
            - set(operation.keys()),
            set(),
        )
        self.assertEqual(operation["action"], "add_to_b")
        self.assertEqual(operation["source_extension"], ".mp3")
        self.assertIsNone(operation["replace_target_path"])

    def test_wrapped_and_legacy_decision_fixtures_both_load(self):
        wrapped = load_decisions(FIXTURES / "decisions_wrapped_v1.json")
        legacy = load_decisions(FIXTURES / "decisions_legacy_plain.json")

        self.assertEqual(wrapped["exact:abc123"], "replace_in_b_with_a")
        self.assertEqual(wrapped["fuzzy:def456"], "keep_both_versions")
        self.assertEqual(legacy["exact:legacy1"], "keep_b")
        self.assertEqual(legacy["fuzzy:legacy2"], "skip")

    def test_report_csv_header_order_is_stable(self):
        payload = {
            "result": {
                "executed": [],
                "skipped": [],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.csv"
            write_report_csv(path, payload)
            header = path.read_text(encoding="utf-8").splitlines()[0]

        self.assertEqual(
            header,
            ",".join(
                [
                    "status",
                    "reason",
                    "action",
                    "source_path",
                    "source_relative_path",
                    "destination_path",
                    "effective_destination_path",
                    "quarantine_from",
                    "quarantine_to",
                    "quarantine_status",
                ]
            ),
        )

    def test_report_csv_round_trip_uses_stable_columns(self):
        payload = {
            "result": {
                "executed": [
                    {
                        "status": "copied",
                        "effective_destination_path": "/music/B/Artist/Album/song.mp3",
                        "quarantine_move": None,
                        "operation": {
                            "action": "add_to_b",
                            "source_path": "/music/A/Artist/Album/song.mp3",
                            "source_relative_path": "Artist/Album/song.mp3",
                            "destination_path": "/music/B/Artist/Album/song.mp3",
                        },
                    }
                ],
                "skipped": [],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.csv"
            write_report_csv(path, payload)
            with path.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))

        self.assertEqual(rows[0]["status"], "copied")
        self.assertEqual(rows[0]["action"], "add_to_b")
        self.assertEqual(rows[0]["source_relative_path"], "Artist/Album/song.mp3")


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _run_cli(args, cwd):
    cmd = [sys.executable, "-m", "trackloom.cli"] + args
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


class CliIntegrationSmokeTests(unittest.TestCase):
    def test_parse_compare_plan_and_apply_dry_run_on_generated_demo(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            demo_out = tmp / "demo_data"
            plan_path = tmp / "plan.json"

            # Generate demo fixtures in a temp location.
            subprocess.run(
                [
                    sys.executable,
                    "scripts/make_demo_data.py",
                    "--output",
                    str(demo_out),
                    "--force",
                ],
                cwd=repo_root,
                check=True,
                text=True,
                capture_output=True,
            )

            dir_a = demo_out / "A"
            dir_b = demo_out / "B"
            self.assertTrue(dir_a.is_dir())
            self.assertTrue(dir_b.is_dir())

            parse = _run_cli(
                [
                    "parse",
                    str(dir_a),
                    "--extensions",
                    ".wav",
                    ".mp3",
                    ".m4a",
                    ".flac",
                    ".m4p",
                    "--json",
                ],
                cwd=repo_root,
            )
            parse_payload = json.loads(parse.stdout)
            self.assertIn("count_a", parse_payload)
            self.assertGreater(parse_payload["count_a"], 0)

            compare = _run_cli(
                [
                    "compare",
                    str(dir_a),
                    str(dir_b),
                    "--extensions",
                    ".wav",
                    ".mp3",
                    ".m4a",
                    ".flac",
                    ".m4p",
                    "--top-k",
                    "1",
                    "--json",
                ],
                cwd=repo_root,
            )
            compare_payload = json.loads(compare.stdout)
            self.assertIn("exact_match_count", compare_payload)
            self.assertIn("action_counts", compare_payload)
            self.assertIn("fuzzy_dropped_count", compare_payload)

            plan = _run_cli(
                [
                    "plan",
                    str(dir_a),
                    str(dir_b),
                    "--extensions",
                    ".wav",
                    ".mp3",
                    ".m4a",
                    ".flac",
                    ".m4p",
                    "--write-plan-json",
                    str(plan_path),
                    "--json",
                ],
                cwd=repo_root,
            )
            plan_payload = json.loads(plan.stdout)
            self.assertTrue(plan_path.exists())
            self.assertIn("counts", plan_payload)
            self.assertIn("operations", plan_payload)

            apply_dry_run = _run_cli(
                [
                    "apply",
                    str(dir_a),
                    str(dir_b),
                    "--from-plan-json",
                    str(plan_path),
                    "--dry-run",
                    "--yes",
                    "--json",
                ],
                cwd=repo_root,
            )
            apply_payload = json.loads(apply_dry_run.stdout)
            self.assertTrue(apply_payload["dry_run"])
            self.assertIn("result", apply_payload)
            self.assertEqual(
                apply_payload["result"]["requested_count"],
                len(plan_payload["operations"]),
            )

    def test_apply_from_plan_json_uses_plan_dir_metadata(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "A_plan" / "song.wav"
            dst = tmp / "B_plan" / "song.wav"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("audio")
            plan_path = tmp / "plan.json"
            plan_payload = {
                "dir_a": str(tmp / "A_plan"),
                "dir_b": str(tmp / "B_plan"),
                "schema_version": 1,
                "operations": [
                    {
                        "action": "add_to_b",
                        "source_path": str(src),
                        "source_relative_path": "song.wav",
                        "source_extension": ".wav",
                        "source_codec": None,
                        "preferred_destination_path": str(dst),
                        "destination_path": str(dst),
                        "replace_target_path": None,
                    }
                ],
                "counts": {"operations": 1, "add_to_b": 1, "replace_in_b_with_a": 0, "keep_both_versions": 0},
            }
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

            # Pass different CLI dirs; payload should still report plan's dir_a/dir_b.
            out = _run_cli(
                [
                    "apply",
                    str(tmp / "CLI_A"),
                    str(tmp / "CLI_B"),
                    "--from-plan-json",
                    str(plan_path),
                    "--dry-run",
                    "--yes",
                    "--json",
                ],
                cwd=repo_root,
            )
            payload = json.loads(out.stdout)
            self.assertEqual(payload["dir_a"], str(tmp / "A_plan"))
            self.assertEqual(payload["dir_b"], str(tmp / "B_plan"))


if __name__ == "__main__":
    unittest.main()

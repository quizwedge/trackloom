# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import csv
import io
import json
import tempfile
import unittest
import wave
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from trackloom.commands.apply import cmd_apply
from trackloom.commands.plan import cmd_plan
from trackloom.commands.review import cmd_review


def _write_wav(path: Path, duration_s: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    n_samples = max(1, int(duration_s * sample_rate))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * n_samples)


class ContractScenarioTests(unittest.TestCase):
    def test_plex_mode_workflow_preserves_mode_skips_from_plan_to_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "plan.json"
            (dir_a / "Artist" / "Album").mkdir(parents=True)
            dir_b.mkdir()
            (dir_a / "Artist" / "Album" / "01 - Good Song.mp3").write_text("audio")
            (dir_a / "Artist" / "Album" / "02 - Protected Song.m4p").write_text("audio")

            plan_args = Namespace(
                dir_a=dir_a,
                dir_b=dir_b,
                extensions=[".mp3", ".m4p"],
                fuzzy_threshold=0.75,
                close_duration_seconds=1.0,
                duration_conflict_seconds=5.0,
                min_song_sim=0.82,
                min_artist_sim=0.65,
                top_k=20,
                mode="standard",
                json=True,
                write_plan_json=plan_path,
                progress=False,
            )
            with redirect_stdout(io.StringIO()) as stdout:
                result = cmd_plan(plan_args)
            self.assertEqual(result, 0)
            plan_payload = json.loads(stdout.getvalue())
            self.assertEqual(plan_payload["counts"]["operations"], 2)

            apply_args = Namespace(
                dir_a=dir_a,
                dir_b=dir_b,
                from_plan_json=plan_path,
                extensions=[".mp3", ".m4p"],
                fuzzy_threshold=0.75,
                close_duration_seconds=1.0,
                duration_conflict_seconds=5.0,
                min_song_sim=0.82,
                min_artist_sim=0.65,
                top_k=20,
                mode="plex",
                yes=True,
                force=False,
                cleanup_mode="move-to-quarantine",
                quarantine_dir=None,
                dry_run=True,
                json=True,
                report_json=None,
                report_csv=None,
                progress=False,
            )
            with redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(apply_args)
            self.assertEqual(result, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "plex")
            self.assertEqual(payload["mode_skipped_count"], 1)
            self.assertEqual(payload["result"]["requested_count"], 1)
            self.assertEqual(
                payload["mode_skipped_operations"][0]["reason"],
                "drm_or_protected_extension",
            )

    def test_review_decisions_persist_and_replay_to_same_reviewed_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            decisions_path = root / "decisions.json"
            reviewed_plan_one = root / "reviewed-one.json"
            reviewed_plan_two = root / "reviewed-two.json"

            _write_wav(dir_a / "Artist" / "Album" / "Song.wav", 1.0)
            _write_wav(dir_b / "Artist" / "Album" / "Song.wav", 7.0)

            base_args = dict(
                dir_a=dir_a,
                dir_b=dir_b,
                extensions=[".wav"],
                fuzzy_threshold=0.75,
                close_duration_seconds=1.0,
                duration_conflict_seconds=5.0,
                min_song_sim=0.82,
                min_artist_sim=0.65,
                top_k=20,
                mode="standard",
                page_size=20,
                max_manual_items=1000,
                start_index=1,
                export_manual_review_json=None,
                decisions_file=decisions_path,
                json=False,
                progress=False,
            )

            with patch("builtins.input", side_effect=["1 r", "done"]), redirect_stdout(
                io.StringIO()
            ):
                result = cmd_review(
                    Namespace(write_plan_json=reviewed_plan_one, **base_args)
                )
            self.assertEqual(result, 0)

            with patch("builtins.input", side_effect=["done"]), redirect_stdout(
                io.StringIO()
            ):
                result = cmd_review(
                    Namespace(write_plan_json=reviewed_plan_two, **base_args)
                )
            self.assertEqual(result, 0)

            decisions_payload = json.loads(decisions_path.read_text(encoding="utf-8"))
            plan_one = json.loads(reviewed_plan_one.read_text(encoding="utf-8"))
            plan_two = json.loads(reviewed_plan_two.read_text(encoding="utf-8"))

            self.assertEqual(len(decisions_payload["decisions"]), 1)
            self.assertEqual(
                list(decisions_payload["decisions"].values()),
                ["replace_in_b_with_a"],
            )
            self.assertEqual(plan_one["operations"], plan_two["operations"])
            self.assertEqual(
                plan_one["review_action_counts"],
                plan_two["review_action_counts"],
            )
            self.assertEqual(plan_one["source_decisions_file"], str(decisions_path))
            self.assertEqual(plan_two["source_decisions_file"], str(decisions_path))

    def test_apply_dry_run_reports_preserve_contract_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "plan.json"
            report_json = root / "apply-report.json"
            report_csv = root / "apply-report.csv"
            (dir_a / "Artist" / "Album").mkdir(parents=True)
            dir_b.mkdir()
            (dir_a / "Artist" / "Album" / "01 - Song.mp3").write_text("audio")

            plan_args = Namespace(
                dir_a=dir_a,
                dir_b=dir_b,
                extensions=[".mp3"],
                fuzzy_threshold=0.75,
                close_duration_seconds=1.0,
                duration_conflict_seconds=5.0,
                min_song_sim=0.82,
                min_artist_sim=0.65,
                top_k=20,
                mode="standard",
                json=False,
                write_plan_json=plan_path,
                progress=False,
            )
            with redirect_stdout(io.StringIO()):
                result = cmd_plan(plan_args)
            self.assertEqual(result, 0)

            apply_args = Namespace(
                dir_a=dir_a,
                dir_b=dir_b,
                from_plan_json=plan_path,
                extensions=[".mp3"],
                fuzzy_threshold=0.75,
                close_duration_seconds=1.0,
                duration_conflict_seconds=5.0,
                min_song_sim=0.82,
                min_artist_sim=0.65,
                top_k=20,
                mode="standard",
                yes=True,
                force=False,
                cleanup_mode="move-to-quarantine",
                quarantine_dir=None,
                dry_run=True,
                json=True,
                report_json=report_json,
                report_csv=report_csv,
                progress=False,
            )
            with redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(apply_args)
            self.assertEqual(result, 0)

            payload = json.loads(stdout.getvalue())
            report_payload = json.loads(report_json.read_text(encoding="utf-8"))
            with report_csv.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))

            for body in (payload, report_payload):
                self.assertIn("run_metadata", body)
                self.assertIn("result", body)
                self.assertIn("mode_skipped_operations", body)
                self.assertEqual(
                    body["run_metadata"]["compare_settings_source"], "plan_json"
                )
                self.assertEqual(body["result"]["requested_count"], 1)
            self.assertEqual(rows[0]["status"], "dry_run")
            self.assertEqual(rows[0]["action"], "add_to_b")


if __name__ == "__main__":
    unittest.main()

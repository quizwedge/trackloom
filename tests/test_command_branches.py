# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import io
import json
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from trackloom.cli import _find_subparser, build_arg_parser
from trackloom.commands.apply import EXIT_CANCELLED as APPLY_EXIT_CANCELLED
from trackloom.commands.apply import cmd_apply
from trackloom.commands.common import (
    apply_mode_to_plan_payload,
    make_progress_callback,
    print_apply_change_summary,
    validate_directory,
)
from trackloom.commands.compare import cmd_compare
from trackloom.commands.parse import cmd_parse
from trackloom.commands.plan import cmd_plan
from trackloom.commands.review import EXIT_BLOCKED as REVIEW_EXIT_BLOCKED
from trackloom.commands.review import EXIT_CANCELLED as REVIEW_EXIT_CANCELLED
from trackloom.commands.review import cmd_review


class DummyItem:
    def __init__(self, relative_path):
        self.relative_path = relative_path
        self.path_fields = Namespace(artist="Artist", album="Album", song="Song")
        self.tag_fields = Namespace(artist="Artist", album="Album", song="Song")
        self.normalized_path_fields = Namespace(
            artist="artist", album="album", song="song"
        )
        self.duration_seconds = 123.0
        self.bitrate_kbps = 320
        self.sample_rate_hz = 44100
        self.bit_depth = 16
        self.channels = 2
        self.codec = "flac"
        self.version_hints = ["live"]

    def to_dict(self):
        return {"relative_path": self.relative_path}


def _base_compare_args(**overrides):
    args = {
        "dir_a": Path("/tmp/A"),
        "dir_b": Path("/tmp/B"),
        "extensions": [".mp3"],
        "fuzzy_threshold": 0.75,
        "close_duration_seconds": 1.0,
        "duration_conflict_seconds": 5.0,
        "min_song_sim": 0.82,
        "min_artist_sim": 0.65,
        "top_k": 20,
        "json": False,
        "progress": False,
    }
    args.update(overrides)
    return Namespace(**args)


def _base_plan_args(**overrides):
    args = vars(_base_compare_args())
    args.update(
        {
            "mode": "standard",
            "write_plan_json": None,
        }
    )
    args.update(overrides)
    return Namespace(**args)


def _base_apply_args(dir_a, dir_b, plan_path, **overrides):
    args = {
        "dir_a": dir_a,
        "dir_b": dir_b,
        "from_plan_json": plan_path,
        "extensions": [".wav"],
        "fuzzy_threshold": 0.75,
        "close_duration_seconds": 1.0,
        "duration_conflict_seconds": 5.0,
        "min_song_sim": 0.82,
        "min_artist_sim": 0.65,
        "top_k": 20,
        "mode": "standard",
        "yes": False,
        "force": False,
        "cleanup_mode": "move-to-quarantine",
        "quarantine_dir": None,
        "dry_run": True,
        "json": False,
        "report_json": None,
        "report_csv": None,
        "progress": False,
    }
    args.update(overrides)
    return Namespace(**args)


def _base_review_args(dir_a, dir_b, **overrides):
    args = {
        "dir_a": dir_a,
        "dir_b": dir_b,
        "extensions": [".wav"],
        "fuzzy_threshold": 0.75,
        "close_duration_seconds": 1.0,
        "duration_conflict_seconds": 5.0,
        "min_song_sim": 0.82,
        "min_artist_sim": 0.65,
        "top_k": 20,
        "mode": "standard",
        "page_size": 2,
        "max_manual_items": 1000,
        "start_index": 1,
        "write_plan_json": None,
        "export_manual_review_json": None,
        "decisions_file": None,
        "json": False,
        "progress": False,
    }
    args.update(overrides)
    return Namespace(**args)


class ApplyCommandTests(unittest.TestCase):
    def test_cmd_apply_can_build_plan_from_cli_args(self):
        args = _base_apply_args(
            Path("/tmp/A"),
            Path("/tmp/B"),
            None,
            yes=True,
            force=True,
            json=True,
        )

        with patch("trackloom.commands.apply.validate_directory"), patch(
            "trackloom.commands.apply.collect_audio_pair", return_value=([], [])
        ), patch(
            "trackloom.commands.apply.compare_payload", return_value={"action_counts": {}}
        ), patch(
            "trackloom.commands.apply.build_copy_plan",
            return_value={
                "operations": [
                    {
                        "action": "add_to_b",
                        "source_path": "/tmp/A/song.wav",
                        "destination_path": "/tmp/B/song.wav",
                    }
                ]
            },
        ), patch(
            "trackloom.commands.apply.execute_operations",
            return_value={
                "requested_count": 1,
                "executed_count": 1,
                "skipped_count": 0,
                "executed": [],
                "skipped": [],
            },
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_apply(args)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["run_metadata"]["compare_settings_source"], "cli_args")
        self.assertEqual(payload["run_metadata"]["top_k"], 20)

    def test_cmd_apply_rejects_missing_plan_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            dir_a.mkdir()
            dir_b.mkdir()

            with self.assertRaises(ValueError):
                cmd_apply(_base_apply_args(dir_a, dir_b, root / "missing.json"))

    def test_cmd_apply_rejects_plan_path_that_is_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_dir = root / "plan_dir"
            dir_a.mkdir()
            dir_b.mkdir()
            plan_dir.mkdir()

            with self.assertRaises(ValueError):
                cmd_apply(_base_apply_args(dir_a, dir_b, plan_dir))

    def test_cmd_apply_rejects_non_object_plan_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "plan.json"
            dir_a.mkdir()
            dir_b.mkdir()
            plan_path.write_text("[]", encoding="utf-8")

            with self.assertRaises(ValueError):
                cmd_apply(_base_apply_args(dir_a, dir_b, plan_path))

    def test_cmd_apply_rejects_plan_without_operations_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "plan.json"
            dir_a.mkdir()
            dir_b.mkdir()
            plan_path.write_text(
                json.dumps({"dir_a": str(dir_a), "dir_b": str(dir_b)}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                cmd_apply(_base_apply_args(dir_a, dir_b, plan_path))

    def test_cmd_apply_no_operations_writes_reports_and_returns_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            dir_a.mkdir()
            dir_b.mkdir()
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [],
                        "compare_settings": {},
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(
                dir_a,
                dir_b,
                plan_path,
                report_json=root / "report.json",
                report_csv=root / "report.csv",
            )

            with patch("trackloom.commands.apply.write_report_json") as write_json, patch(
                "trackloom.commands.apply.write_report_csv"
            ) as write_csv, redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

            self.assertEqual(result, 0)
            self.assertIn("No operations to apply.", stdout.getvalue())
            write_json.assert_called_once()
            write_csv.assert_called_once()

    def test_cmd_apply_no_operations_json_payload_for_cli_path(self):
        args = _base_apply_args(
            Path("/tmp/A"),
            Path("/tmp/B"),
            None,
            json=True,
        )

        with patch("trackloom.commands.apply.validate_directory"), patch(
            "trackloom.commands.apply.collect_audio_pair", return_value=([], [])
        ), patch(
            "trackloom.commands.apply.compare_payload", return_value={"action_counts": {}}
        ), patch(
            "trackloom.commands.apply.build_copy_plan", return_value={"operations": []}
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_apply(args)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["message"], "No operations to apply.")

    def test_cmd_apply_cancelled_json_payload_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.wav"
            dst = dir_b / "song.wav"
            src.parent.mkdir(parents=True)
            dir_b.mkdir()
            src.write_text("audio")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [
                            {
                                "action": "add_to_b",
                                "source_path": str(src),
                                "source_relative_path": "song.wav",
                                "destination_path": str(dst),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(
                dir_a,
                dir_b,
                plan_path,
                json=True,
                report_json=root / "report.json",
                report_csv=root / "report.csv",
            )

            with patch("builtins.input", return_value="n"), patch(
                "trackloom.commands.apply.write_report_json"
            ) as write_json, patch(
                "trackloom.commands.apply.write_report_csv"
            ) as write_csv, redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

            self.assertEqual(result, APPLY_EXIT_CANCELLED)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["message"], "Cancelled by user.")
            write_json.assert_called_once()
            write_csv.assert_called_once()

    def test_cmd_apply_safeguard_confirmation_can_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.wav"
            dst = dir_b / "song.wav"
            src.parent.mkdir(parents=True)
            dir_b.mkdir()
            src.write_text("audio")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [
                            {
                                "action": "add_to_b",
                                "source_path": str(src),
                                "source_relative_path": "song.wav",
                                "destination_path": str(dst),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(dir_a, dir_b, plan_path, yes=True, dry_run=False)

            with patch("builtins.input", return_value="NO"), patch(
                "trackloom.commands.apply.execute_operations"
            ) as execute_operations, redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

            self.assertEqual(result, APPLY_EXIT_CANCELLED)
            self.assertIn("Cancelled by safeguard confirmation.", stdout.getvalue())
            execute_operations.assert_not_called()

    def test_cmd_apply_safeguard_eof_json_writes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.wav"
            dst = dir_b / "song.wav"
            src.parent.mkdir(parents=True)
            dir_b.mkdir()
            src.write_text("audio")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [
                            {
                                "action": "add_to_b",
                                "source_path": str(src),
                                "source_relative_path": "song.wav",
                                "destination_path": str(dst),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(
                dir_a,
                dir_b,
                plan_path,
                yes=True,
                dry_run=False,
                json=True,
                report_json=root / "report.json",
                report_csv=root / "report.csv",
            )

            with patch("builtins.input", side_effect=EOFError), patch(
                "trackloom.commands.apply.write_report_json"
            ) as write_json, patch(
                "trackloom.commands.apply.write_report_csv"
            ) as write_csv, redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

        self.assertEqual(result, APPLY_EXIT_CANCELLED)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["message"], "Cancelled due to EOF on stdin.")
        write_json.assert_called_once()
        write_csv.assert_called_once()

    def test_cmd_apply_text_cancelled_from_cli_path_prints_tip_and_report(self):
        args = _base_apply_args(
            Path("/tmp/A"),
            Path("/tmp/B"),
            None,
            report_json=Path("/tmp/report.json"),
        )

        with patch("trackloom.commands.apply.validate_directory"), patch(
            "trackloom.commands.apply.collect_audio_pair", return_value=([], [])
        ), patch(
            "trackloom.commands.apply.compare_payload", return_value={"action_counts": {}}
        ), patch(
            "trackloom.commands.apply.build_copy_plan",
            return_value={
                "operations": [
                    {
                        "action": "add_to_b",
                        "source_path": "/tmp/A/song.wav",
                        "destination_path": "/tmp/B/song.wav",
                    }
                ]
            },
        ), patch("builtins.input", return_value="n"), redirect_stdout(
            io.StringIO()
        ) as stdout:
            result = cmd_apply(args)

        self.assertEqual(result, APPLY_EXIT_CANCELLED)
        text = stdout.getvalue()
        self.assertIn("Report JSON: /tmp/report.json", text)
        self.assertIn("Tip: run 'trackloom plan A B --write-plan-json plan.json'", text)

    def test_cmd_apply_force_bypasses_extra_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.wav"
            dst = dir_b / "song.wav"
            src.parent.mkdir(parents=True)
            dir_b.mkdir()
            src.write_text("audio")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [
                            {
                                "action": "add_to_b",
                                "source_path": str(src),
                                "source_relative_path": "song.wav",
                                "destination_path": str(dst),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(
                dir_a, dir_b, plan_path, yes=True, dry_run=False, force=True
            )

            with patch("builtins.input") as input_mock, patch(
                "trackloom.commands.apply.execute_operations",
                return_value={
                    "requested_count": 1,
                    "executed_count": 1,
                    "skipped_count": 0,
                    "executed": [],
                    "skipped": [],
                },
            ) as execute_operations, redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

            self.assertEqual(result, 0)
            self.assertIn("Apply result: requested=1 executed=1 skipped=0", stdout.getvalue())
            input_mock.assert_not_called()
            execute_operations.assert_called_once()

    def test_cmd_apply_text_success_prints_mode_skips_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.wav"
            dst = dir_b / "song.wav"
            src.parent.mkdir(parents=True)
            dir_b.mkdir()
            src.write_text("audio")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [
                            {
                                "action": "add_to_b",
                                "source_path": str(src),
                                "source_relative_path": "song.wav",
                                "destination_path": str(dst),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(
                dir_a,
                dir_b,
                plan_path,
                yes=True,
                report_json=root / "report.json",
                report_csv=root / "report.csv",
            )

            with patch(
                "trackloom.commands.apply.filter_operations_for_mode",
                return_value=(
                    [
                        {
                            "action": "add_to_b",
                            "source_path": str(src),
                            "destination_path": str(dst),
                        }
                    ],
                    [{"reason": "unsupported"}],
                ),
            ), patch(
                "trackloom.commands.apply.execute_operations",
                return_value={
                    "requested_count": 1,
                    "executed_count": 1,
                    "skipped_count": 0,
                    "executed": [],
                    "skipped": [],
                },
            ), redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

            self.assertEqual(result, 0)
            text = stdout.getvalue()
            self.assertIn("Mode skipped operations (standard): 1", text)
            self.assertIn(f"Report JSON: {root / 'report.json'}", text)
            self.assertIn(f"Report CSV: {root / 'report.csv'}", text)

    def test_cmd_apply_plex_mode_surfaces_skipped_operations_in_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.mp3"
            dst = dir_b / "song.mp3"
            src.parent.mkdir(parents=True)
            dir_b.mkdir()
            src.write_text("audio")
            plan_path = root / "plan.json"
            plan_path.write_text(
                json.dumps(
                    {
                        "dir_a": str(dir_a),
                        "dir_b": str(dir_b),
                        "operations": [
                            {
                                "action": "add_to_b",
                                "source_path": str(src),
                                "source_relative_path": "song.mp3",
                                "destination_path": str(dst),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            args = _base_apply_args(dir_a, dir_b, plan_path, mode="plex", json=True, yes=True)

            with patch(
                "trackloom.commands.apply.filter_operations_for_mode",
                return_value=([], [{"reason": "drm_or_protected_extension"}]),
            ), redirect_stdout(io.StringIO()) as stdout:
                result = cmd_apply(args)

            self.assertEqual(result, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["mode"], "plex")
            self.assertEqual(payload["mode_skipped_count"], 1)
            self.assertEqual(
                payload["mode_skipped_operations"][0]["reason"],
                "drm_or_protected_extension",
            )


class ReviewCommandTests(unittest.TestCase):
    def test_cmd_review_rejects_invalid_paging_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            dir_a.mkdir()
            dir_b.mkdir()

            for overrides in (
                {"page_size": 0},
                {"max_manual_items": -1},
                {"start_index": 0},
            ):
                with self.assertRaises(ValueError):
                    cmd_review(_base_review_args(dir_a, dir_b, **overrides))

    def test_cmd_review_returns_blocked_for_manual_item_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            dir_a.mkdir()
            dir_b.mkdir()
            args = _base_review_args(dir_a, dir_b, json=True)

            with patch("trackloom.commands.review.collect_audio_pair", return_value=([], [])), patch(
                "trackloom.commands.review.compare_payload", return_value={}
            ), patch(
                "trackloom.commands.review.extract_manual_review_candidates",
                return_value=[{"id": "1"}],
            ), patch(
                "trackloom.commands.review.summarize_manual_review_candidates",
                return_value={"source_counts": {}, "policy_counts": {}},
            ), patch(
                "trackloom.commands.review.validate_manual_item_limit",
                side_effect=RuntimeError("too many items"),
            ), redirect_stdout(io.StringIO()) as stdout:
                result = cmd_review(args)

            self.assertEqual(result, REVIEW_EXIT_BLOCKED)
            self.assertIn("too many items", stdout.getvalue())

    def test_cmd_review_handles_no_candidates_and_writes_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "reviewed-plan.json"
            export_path = root / "manual-review.json"
            dir_a.mkdir()
            dir_b.mkdir()
            args = _base_review_args(
                dir_a,
                dir_b,
                write_plan_json=plan_path,
                export_manual_review_json=export_path,
            )

            with patch("trackloom.commands.review.collect_audio_pair", return_value=([], [])), patch(
                "trackloom.commands.review.compare_payload",
                return_value={"fuzzy_dropped_count": 0},
            ), patch(
                "trackloom.commands.review.extract_manual_review_candidates",
                return_value=[],
            ), patch(
                "trackloom.commands.review.summarize_manual_review_candidates",
                return_value={"source_counts": {}, "policy_counts": {}},
            ), redirect_stdout(io.StringIO()) as stdout:
                result = cmd_review(args)

            self.assertEqual(result, 0)
            self.assertTrue(plan_path.exists())
            self.assertTrue(export_path.exists())
            self.assertIn("No manual review items found.", stdout.getvalue())

    def test_cmd_review_interactive_loop_covers_navigation_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            decisions_file = root / "decisions.json"
            dir_a.mkdir()
            dir_b.mkdir()
            candidates = [
                {
                    "id": "exact-1",
                    "source": "exact",
                    "file_a": {"relative_path": "A/1.wav"},
                    "file_b": {"relative_path": "B/1.wav"},
                },
                {
                    "id": "fuzzy-2",
                    "source": "fuzzy",
                    "file_a": {"relative_path": "A/2.wav"},
                    "file_b": {"relative_path": "B/2.wav"},
                    "score": 0.91,
                    "song_similarity": 0.88,
                    "artist_similarity": 0.79,
                },
            ]
            args = _base_review_args(dir_a, dir_b, decisions_file=decisions_file)
            commands = ["4 a", "1 x", "wat", "1 a", "n", "p", "q"]

            with patch("trackloom.commands.review.collect_audio_pair", return_value=([], [])), patch(
                "trackloom.commands.review.compare_payload",
                return_value={"fuzzy_dropped_count": 1},
            ), patch(
                "trackloom.commands.review.extract_manual_review_candidates",
                return_value=candidates,
            ), patch(
                "trackloom.commands.review.summarize_manual_review_candidates",
                return_value={
                    "source_counts": {"exact": 1, "fuzzy": 1},
                    "policy_counts": {"duration_conflict": 1},
                },
            ), patch("builtins.input", side_effect=commands), redirect_stdout(
                io.StringIO()
            ) as stdout:
                result = cmd_review(args)

            self.assertEqual(result, REVIEW_EXIT_CANCELLED)
            self.assertIn("Invalid index.", stdout.getvalue())
            self.assertIn("Invalid choice. Use one of: a r k b s", stdout.getvalue())
            self.assertIn("Unknown command.", stdout.getvalue())
            self.assertIn("Review cancelled by user.", stdout.getvalue())
            self.assertTrue(decisions_file.exists())
            self.assertEqual(
                json.loads(decisions_file.read_text()),
                {"decisions": {"exact-1": "add_to_b"}},
            )

    def test_cmd_review_done_writes_reviewed_plan_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "reviewed-plan.json"
            decisions_file = root / "decisions.json"
            dir_a.mkdir()
            dir_b.mkdir()
            candidates = [
                {
                    "id": "exact-1",
                    "source": "exact",
                    "file_a": {"relative_path": "A/1.wav"},
                    "file_b": {"relative_path": "B/1.wav"},
                }
            ]
            args = _base_review_args(
                dir_a,
                dir_b,
                decisions_file=decisions_file,
                write_plan_json=plan_path,
                json=True,
            )

            with patch("trackloom.commands.review.collect_audio_pair", return_value=([], [])), patch(
                "trackloom.commands.review.compare_payload",
                return_value={"fuzzy_dropped_count": 0},
            ), patch(
                "trackloom.commands.review.extract_manual_review_candidates",
                return_value=candidates,
            ), patch(
                "trackloom.commands.review.summarize_manual_review_candidates",
                return_value={
                    "source_counts": {"exact": 1, "fuzzy": 0},
                    "policy_counts": {},
                },
            ), patch(
                "trackloom.commands.review.build_plan_from_review_decisions",
                return_value={
                    "counts": {
                        "operations": 1,
                        "add_to_b": 1,
                        "replace_in_b_with_a": 0,
                        "keep_both_versions": 0,
                    },
                    "operations": [{"action": "add_to_b"}],
                    "review_action_counts": {
                        "add_to_b": 1,
                        "replace_in_b_with_a": 0,
                        "keep_b": 0,
                        "keep_both_versions": 0,
                        "skip": 0,
                    },
                },
            ), patch("builtins.input", side_effect=["1 a", "done"]), redirect_stdout(
                io.StringIO()
            ) as stdout:
                result = cmd_review(args)

            self.assertEqual(result, 0)
            output = stdout.getvalue()
            self.assertIn('"manual_review_count": 1', output)
            self.assertIn(
                f'"source_decisions_file": "{str(decisions_file)}"',
                output,
            )
            self.assertTrue(plan_path.exists())

    def test_cmd_review_done_text_output_reports_saved_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            plan_path = root / "reviewed-plan.json"
            export_path = root / "manual-review.json"
            decisions_file = root / "decisions.json"
            dir_a.mkdir()
            dir_b.mkdir()
            candidates = [
                {
                    "id": "exact-1",
                    "source": "exact",
                    "file_a": {"relative_path": "A/1.wav"},
                    "file_b": {"relative_path": "B/1.wav"},
                }
            ]
            args = _base_review_args(
                dir_a,
                dir_b,
                decisions_file=decisions_file,
                write_plan_json=plan_path,
                export_manual_review_json=export_path,
                json=False,
            )

            with patch("trackloom.commands.review.collect_audio_pair", return_value=([], [])), patch(
                "trackloom.commands.review.compare_payload",
                return_value={"fuzzy_dropped_count": 0},
            ), patch(
                "trackloom.commands.review.extract_manual_review_candidates",
                return_value=candidates,
            ), patch(
                "trackloom.commands.review.summarize_manual_review_candidates",
                return_value={
                    "source_counts": {"exact": 1, "fuzzy": 0},
                    "policy_counts": {},
                },
            ), patch(
                "trackloom.commands.review.build_plan_from_review_decisions",
                return_value={
                    "counts": {
                        "operations": 1,
                        "add_to_b": 1,
                        "replace_in_b_with_a": 0,
                        "keep_both_versions": 0,
                    },
                    "operations": [{"action": "add_to_b"}],
                    "review_action_counts": {
                        "add_to_b": 1,
                        "replace_in_b_with_a": 0,
                        "keep_b": 0,
                        "keep_both_versions": 0,
                        "skip": 0,
                    },
                },
            ), patch("builtins.input", side_effect=["1 a", "done"]), redirect_stdout(
                io.StringIO()
            ) as stdout:
                result = cmd_review(args)

            self.assertEqual(result, 0)
            text = stdout.getvalue()
            self.assertIn("Reviewed plan operations: 1", text)
            self.assertIn(f"Reviewed plan saved to: {plan_path}", text)
            self.assertIn(f"Manual review export: {export_path}", text)
            self.assertIn(f"Decisions saved to: {decisions_file}", text)


class CommandOutputTests(unittest.TestCase):
    def test_cmd_compare_text_output_includes_fuzzy_and_rejections(self):
        args = _base_compare_args()
        payload = {
            "exact_match_count": 1,
            "only_in_a_count": 2,
            "only_in_b_count": 3,
            "fuzzy_candidate_count": 1,
            "duplicate_policy_counts": {
                "likely_duplicate": 1,
                "version_conflict": 0,
                "duration_conflict": 1,
            },
            "action_counts": {
                "add_to_b": 2,
                "replace_in_b_with_a": 1,
                "keep_b": 3,
                "keep_both_versions": 4,
                "manual_review": 5,
            },
            "fuzzy_candidates": [
                {
                    "score": 0.91,
                    "file_a": {"relative_path": "A/song.mp3"},
                    "file_b": {"relative_path": "B/song.mp3"},
                }
            ],
            "fuzzy_dropped_count": 2,
            "fuzzy_rejection_count": 3,
        }

        with patch("trackloom.commands.compare.validate_directory"), patch(
            "trackloom.commands.compare.collect_audio_pair", return_value=([], [])
        ), patch("trackloom.commands.compare.compare_payload", return_value=payload), redirect_stdout(
            io.StringIO()
        ) as stdout:
            result = cmd_compare(args)

        self.assertEqual(result, 0)
        text = stdout.getvalue()
        self.assertIn("Duplicate policy (exact matches):", text)
        self.assertIn("Top fuzzy candidates:", text)
        self.assertIn("Fuzzy candidates dropped due to --top-k: 2", text)
        self.assertIn("Fuzzy rejections logged: 3", text)

    def test_cmd_plan_text_output_covers_manual_review_and_apply_hints(self):
        args = _base_plan_args(write_plan_json=Path("/tmp/plan.json"))
        compare_result = {
            "action_counts": {"manual_review": 2},
            "exact_match_count": 1,
            "only_in_a_count": 1,
            "only_in_b_count": 0,
            "fuzzy_candidate_count": 0,
            "fuzzy_rejection_count": 0,
            "fuzzy_dropped_count": 0,
        }
        plan_payload = {
            "counts": {
                "operations": 1,
                "add_to_b": 1,
                "replace_in_b_with_a": 0,
                "keep_both_versions": 0,
            },
            "operations": [
                {
                    "action": "add_to_b",
                    "source_relative_path": "Artist/Album/song.mp3",
                    "destination_path": "B/Artist/Album/song.mp3",
                }
            ],
            "mode_skipped_count": 1,
        }

        with patch("trackloom.commands.plan.validate_directory"), patch(
            "trackloom.commands.plan.collect_audio_pair", return_value=([], [])
        ), patch("trackloom.commands.plan.compare_payload", return_value=compare_result), patch(
            "trackloom.commands.plan.build_copy_plan", return_value=plan_payload
        ), patch(
            "trackloom.commands.plan.apply_mode_to_plan_payload", return_value=plan_payload
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_plan(args)

        self.assertEqual(result, 0)
        text = stdout.getvalue()
        self.assertIn("Mode skipped operations (standard): 1", text)
        self.assertIn("Manual review items detected: 2", text)
        self.assertIn("trackloom review", text)

    def test_cmd_plan_without_manual_review_prints_apply_steps(self):
        args = _base_plan_args(write_plan_json=None)
        compare_result = {
            "action_counts": {"manual_review": 0},
            "exact_match_count": 1,
            "only_in_a_count": 1,
            "only_in_b_count": 0,
            "fuzzy_candidate_count": 0,
            "fuzzy_rejection_count": 0,
            "fuzzy_dropped_count": 0,
        }
        plan_payload = {
            "counts": {
                "operations": 1,
                "add_to_b": 1,
                "replace_in_b_with_a": 0,
                "keep_both_versions": 0,
            },
            "operations": [
                {
                    "action": "add_to_b",
                    "source_relative_path": "Artist/Album/song.mp3",
                    "destination_path": "B/Artist/Album/song.mp3",
                }
            ],
            "mode_skipped_count": 0,
        }

        with patch("trackloom.commands.plan.validate_directory"), patch(
            "trackloom.commands.plan.collect_audio_pair", return_value=([], [])
        ), patch("trackloom.commands.plan.compare_payload", return_value=compare_result), patch(
            "trackloom.commands.plan.build_copy_plan", return_value=plan_payload
        ), patch(
            "trackloom.commands.plan.apply_mode_to_plan_payload", return_value=plan_payload
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_plan(args)

        self.assertEqual(result, 0)
        text = stdout.getvalue()
        self.assertIn("Tip: re-run with --write-plan-json plan.json", text)
        self.assertIn("trackloom apply", text)

    def test_cmd_plan_plex_mode_exposes_mode_skipped_operations_in_json(self):
        args = _base_plan_args(mode="plex", json=True)
        compare_result = {
            "action_counts": {"manual_review": 0},
            "exact_match_count": 1,
            "only_in_a_count": 1,
            "only_in_b_count": 0,
            "fuzzy_candidate_count": 0,
            "fuzzy_rejection_count": 0,
            "fuzzy_dropped_count": 0,
        }
        plan_payload = {
            "counts": {
                "operations": 0,
                "add_to_b": 0,
                "replace_in_b_with_a": 0,
                "keep_both_versions": 0,
            },
            "operations": [],
            "mode_skipped_count": 1,
            "mode_skipped_operations": [{"reason": "drm_or_protected_codec"}],
        }

        with patch("trackloom.commands.plan.validate_directory"), patch(
            "trackloom.commands.plan.collect_audio_pair", return_value=([], [])
        ), patch("trackloom.commands.plan.compare_payload", return_value=compare_result), patch(
            "trackloom.commands.plan.build_copy_plan", return_value=plan_payload
        ), patch(
            "trackloom.commands.plan.apply_mode_to_plan_payload", return_value=plan_payload
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_plan(args)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode_skipped_count"], 1)
        self.assertEqual(
            payload["mode_skipped_operations"][0]["reason"],
            "drm_or_protected_codec",
        )

    def test_cmd_review_plex_mode_exposes_mode_skipped_operations_in_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            dir_a.mkdir()
            dir_b.mkdir()
            args = _base_review_args(dir_a, dir_b, mode="plex", json=True)
            candidates = [
                {
                    "id": "exact-1",
                    "source": "exact",
                    "file_a": {"relative_path": "A/1.m4p"},
                    "file_b": {"relative_path": "B/1.m4p"},
                }
            ]

            with patch("trackloom.commands.review.collect_audio_pair", return_value=([], [])), patch(
                "trackloom.commands.review.compare_payload",
                return_value={"fuzzy_dropped_count": 0},
            ), patch(
                "trackloom.commands.review.extract_manual_review_candidates",
                return_value=candidates,
            ), patch(
                "trackloom.commands.review.summarize_manual_review_candidates",
                return_value={
                    "source_counts": {"exact": 1, "fuzzy": 0},
                    "policy_counts": {},
                },
            ), patch(
                "trackloom.commands.review.build_plan_from_review_decisions",
                return_value={
                    "counts": {
                        "operations": 0,
                        "add_to_b": 0,
                        "replace_in_b_with_a": 0,
                        "keep_both_versions": 0,
                    },
                    "operations": [],
                    "review_action_counts": {
                        "add_to_b": 1,
                        "replace_in_b_with_a": 0,
                        "keep_b": 0,
                        "keep_both_versions": 0,
                        "skip": 0,
                    },
                    "mode_skipped_count": 1,
                    "mode_skipped_operations": [{"reason": "drm_or_protected_extension"}],
                },
            ), patch(
                "trackloom.commands.review.apply_mode_to_plan_payload",
                return_value={
                    "counts": {
                        "operations": 0,
                        "add_to_b": 0,
                        "replace_in_b_with_a": 0,
                        "keep_both_versions": 0,
                    },
                    "operations": [],
                    "review_action_counts": {
                        "add_to_b": 1,
                        "replace_in_b_with_a": 0,
                        "keep_b": 0,
                        "keep_both_versions": 0,
                        "skip": 0,
                    },
                    "mode_skipped_count": 1,
                    "mode_skipped_operations": [{"reason": "drm_or_protected_extension"}],
                },
            ), patch("builtins.input", side_effect=["1 a", "done"]), redirect_stdout(
                io.StringIO()
            ) as stdout:
                result = cmd_review(args)

            self.assertEqual(result, 0)
            output = stdout.getvalue()
            self.assertIn('"mode_skipped_count": 1', output)
            self.assertIn('"reason": "drm_or_protected_extension"', output)

    def test_cmd_parse_text_output_prints_a_and_b_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            dir_a.mkdir()
            dir_b.mkdir()
            args = Namespace(
                dir_a=dir_a,
                dir_b=dir_b,
                extensions=["mp3"],
                json=False,
                progress=False,
            )

            with patch(
                "trackloom.commands.parse.collect_audio_metadata",
                side_effect=[[DummyItem("Artist/Album/A.mp3")], [DummyItem("Artist/Album/B.mp3")]],
            ), redirect_stdout(io.StringIO()) as stdout:
                result = cmd_parse(args)

            self.assertEqual(result, 0)
            self.assertIn("Parse A=", stdout.getvalue())
            self.assertIn("A (", stdout.getvalue())
            self.assertIn("B (", stdout.getvalue())


class CommonAndCliTests(unittest.TestCase):
    def test_validate_directory_rejects_missing_and_non_directory_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing"
            file_path = root / "file.txt"
            file_path.write_text("x")

            with self.assertRaises(ValueError):
                validate_directory(missing, "dir_a")
            with self.assertRaises(ValueError):
                validate_directory(file_path, "dir_b")

    def test_make_progress_callback_prints_final_newline(self):
        callback = make_progress_callback("A")
        buffer = io.StringIO()

        with redirect_stderr(buffer):
            callback(1, 2, Path("/tmp/a"))
            callback(2, 2, Path("/tmp/b"))

        self.assertIn("[A] scanned 1/2 files", buffer.getvalue())
        self.assertTrue(buffer.getvalue().endswith("\n"))

    def test_apply_mode_to_plan_payload_recomputes_counts_and_compare_summary(self):
        payload = {
            "operations": [
                {
                    "action": "add_to_b",
                    "source_path": "/tmp/song.mp3",
                    "source_extension": ".mp3",
                },
                {
                    "action": "add_to_b",
                    "source_path": "/tmp/song.m4p",
                    "source_extension": ".m4p",
                },
            ],
            "counts": {
                "operations": 2,
                "add_to_b": 2,
                "replace_in_b_with_a": 0,
                "keep_both_versions": 0,
            },
        }

        result = apply_mode_to_plan_payload(
            payload,
            "plex",
            Path("/tmp/A"),
            Path("/tmp/B"),
            compare_payload={
                "exact_match_count": 1,
                "only_in_a_count": 2,
                "only_in_b_count": 3,
                "fuzzy_candidate_count": 4,
                "fuzzy_dropped_count": 5,
                "fuzzy_rejection_count": 6,
                "action_counts": {"manual_review": 7},
            },
        )

        self.assertEqual(result["counts"]["operations"], 1)
        self.assertEqual(result["counts"]["add_to_b"], 1)
        self.assertEqual(result["mode_skipped_count"], 1)
        self.assertEqual(result["compare_summary"]["fuzzy_rejection_count"], 6)

    def test_print_apply_change_summary_handles_unknown_actions(self):
        buffer = io.StringIO()

        with redirect_stdout(buffer):
            print_apply_change_summary(
                [
                    {"action": "custom_action", "destination_path": "B/song1.mp3"},
                    {"action": "custom_action", "destination_path": "B/song2.mp3"},
                ],
                "/music/B",
            )

        self.assertIn("custom_action=2", buffer.getvalue())
        self.assertIn("destination preview:", buffer.getvalue())

    def test_build_arg_parser_hides_advanced_flags_until_requested(self):
        parser = build_arg_parser()
        advanced_parser = build_arg_parser(show_advanced=True)

        compare_help = _find_subparser(parser, "compare").format_help()
        advanced_help = _find_subparser(advanced_parser, "compare").format_help()

        self.assertNotIn("--top-k", compare_help)
        self.assertIn("--top-k", advanced_help)


if __name__ == "__main__":
    unittest.main()

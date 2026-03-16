# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import json
import tempfile
import unittest
import wave
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from trackloom.commands.apply import EXIT_CANCELLED as APPLY_EXIT_CANCELLED
from trackloom.commands.apply import cmd_apply
from trackloom.commands.review import EXIT_CANCELLED as REVIEW_EXIT_CANCELLED
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


class InteractiveEofTests(unittest.TestCase):
    def test_apply_cmd_eof_cancels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            src = dir_a / "song.wav"
            dst = dir_b / "song.wav"
            _write_wav(src, 1.0)
            dir_b.mkdir(parents=True, exist_ok=True)

            plan_payload = {
                "dir_a": str(dir_a),
                "dir_b": str(dir_b),
                "schema_version": 1,
                "operations": [
                    {
                        "action": "add_to_b",
                        "source_path": str(src),
                        "source_relative_path": "song.wav",
                        "destination_path": str(dst),
                    }
                ],
                "counts": {"operations": 1},
            }
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

            args = Namespace(
                dir_a=dir_a,
                dir_b=dir_b,
                from_plan_json=plan_path,
                extensions=[".wav"],
                fuzzy_threshold=0.75,
                close_duration_seconds=1.0,
                duration_conflict_seconds=5.0,
                min_song_sim=0.82,
                min_artist_sim=0.65,
                top_k=20,
                mode="standard",
                yes=False,
                force=False,
                cleanup_mode="move-to-quarantine",
                quarantine_dir=None,
                dry_run=True,
                json=False,
                report_json=None,
                report_csv=None,
                progress=False,
            )

            with patch("builtins.input", side_effect=EOFError):
                result = cmd_apply(args)

            self.assertEqual(result, APPLY_EXIT_CANCELLED)

    def test_review_cmd_eof_cancels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dir_a = root / "A"
            dir_b = root / "B"
            _write_wav(dir_a / "Artist" / "Album" / "Song.wav", 1.0)
            _write_wav(dir_b / "Artist" / "Album" / "Song.wav", 7.0)

            args = Namespace(
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
                write_plan_json=None,
                export_manual_review_json=None,
                decisions_file=None,
                json=False,
                progress=False,
            )

            with patch("builtins.input", side_effect=EOFError):
                result = cmd_review(args)

            self.assertEqual(result, REVIEW_EXIT_CANCELLED)


if __name__ == "__main__":
    unittest.main()

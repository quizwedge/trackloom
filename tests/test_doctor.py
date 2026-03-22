# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import patch

from trackloom.commands.doctor import (
    EXIT_BLOCKED,
    EXIT_SUCCESS,
    _check_import,
    cmd_doctor,
)


class DoctorTests(unittest.TestCase):
    def test_check_import_reports_failure(self):
        with patch("builtins.__import__", side_effect=ImportError("boom")):
            ok, detail = _check_import("mutagen")

        self.assertFalse(ok)
        self.assertIn("mutagen import failed", detail)

    def test_cmd_doctor_json_success_contract(self):
        args = Namespace(json=True)

        with patch(
            "trackloom.commands.doctor._check_import",
            side_effect=[(True, "ok"), (True, "ok")],
        ), patch(
            "trackloom.commands.doctor.shutil.which",
            return_value="/usr/bin/ffmpeg",
        ), patch(
            "trackloom.commands.doctor.sys.version_info", (3, 8, 2)
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_doctor(args)

        self.assertEqual(result, EXIT_SUCCESS)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["python_version"], "3.8.2")
        self.assertTrue(payload["python_ok"])
        self.assertTrue(payload["mutagen_ok"])
        self.assertTrue(payload["rapidfuzz_ok"])
        self.assertTrue(payload["ffmpeg_ok"])
        self.assertEqual(payload["ffmpeg_path"], "/usr/bin/ffmpeg")

    def test_cmd_doctor_text_output_and_blocked_when_dependency_missing(self):
        args = Namespace(json=False)

        with patch(
            "trackloom.commands.doctor._check_import",
            side_effect=[(False, "mutagen import failed: nope"), (True, "ok")],
        ), patch("trackloom.commands.doctor.shutil.which", return_value=None), patch(
            "trackloom.commands.doctor.sys.version_info", (3, 9, 1)
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_doctor(args)

        self.assertEqual(result, EXIT_BLOCKED)
        text = stdout.getvalue()
        self.assertIn("Doctor checks:", text)
        self.assertIn("- Python >=3.8: OK (3.9.1)", text)
        self.assertIn("- mutagen installed: FAIL (mutagen import failed: nope)", text)
        self.assertIn("- rapidfuzz installed: OK (ok)", text)
        self.assertIn("- ffmpeg: MISSING", text)

    def test_cmd_doctor_blocked_when_python_too_old_even_if_deps_exist(self):
        args = Namespace(json=True)

        with patch(
            "trackloom.commands.doctor._check_import",
            side_effect=[(True, "ok"), (True, "ok")],
        ), patch(
            "trackloom.commands.doctor.shutil.which",
            return_value="/usr/bin/ffmpeg",
        ), patch(
            "trackloom.commands.doctor.sys.version_info", (3, 7, 9)
        ), redirect_stdout(io.StringIO()) as stdout:
            result = cmd_doctor(args)

        self.assertEqual(result, EXIT_BLOCKED)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["python_ok"])
        self.assertEqual(payload["python_version"], "3.7.9")


if __name__ == "__main__":
    unittest.main()

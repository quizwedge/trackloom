# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
import shutil
import sys
from argparse import Namespace

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2


def _check_import(module: str) -> tuple[bool, str]:
    try:
        __import__(module)
    except Exception as exc:
        return False, f"{module} import failed: {exc}"
    return True, "ok"


def cmd_doctor(args: Namespace) -> int:
    py_version = sys.version_info
    py_ok = py_version >= (3, 8)
    mutagen_ok, mutagen_detail = _check_import("mutagen")
    rapidfuzz_ok, rapidfuzz_detail = _check_import("rapidfuzz")
    ffmpeg_path = shutil.which("ffmpeg")

    payload = {
        "python_version": ".".join(str(part) for part in py_version[:3]),
        "python_ok": py_ok,
        "mutagen_ok": mutagen_ok,
        "mutagen_detail": mutagen_detail,
        "rapidfuzz_ok": rapidfuzz_ok,
        "rapidfuzz_detail": rapidfuzz_detail,
        "ffmpeg_ok": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Doctor checks:")
        print(
            f"- Python >=3.8: {'OK' if py_ok else 'FAIL'} "
            f"({payload['python_version']})"
        )
        print(
            f"- mutagen installed: {'OK' if mutagen_ok else 'FAIL'} "
            f"({mutagen_detail})"
        )
        print(
            f"- rapidfuzz installed: {'OK' if rapidfuzz_ok else 'FAIL'} "
            f"({rapidfuzz_detail})"
        )
        if payload["ffmpeg_ok"]:
            print(f"- ffmpeg: OK ({payload['ffmpeg_path']})")
        else:
            print("- ffmpeg: MISSING (optional, needed for tagged demo fixtures)")

    if py_ok and mutagen_ok and rapidfuzz_ok:
        return EXIT_SUCCESS
    return EXIT_BLOCKED

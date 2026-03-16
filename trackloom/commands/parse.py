# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import json
from argparse import Namespace

from ..parser import collect_audio_metadata
from .common import make_progress_callback, normalize_extensions, print_parsed_items


def cmd_parse(args: Namespace) -> int:
    extensions = normalize_extensions(args.extensions)
    left_progress = make_progress_callback("A") if args.progress else None
    left = collect_audio_metadata(
        args.dir_a,
        extensions=extensions,
        progress_callback=left_progress,
    )
    right = (
        collect_audio_metadata(
            args.dir_b,
            extensions=extensions,
            progress_callback=(make_progress_callback("B") if args.progress else None),
        )
        if args.dir_b is not None
        else []
    )

    payload = {
        "dir_a": str(args.dir_a),
        "dir_b": str(args.dir_b) if args.dir_b is not None else None,
        "count_a": len(left),
        "count_b": len(right) if args.dir_b is not None else None,
        "files_a": [item.to_dict() for item in left],
        "files_b": [item.to_dict() for item in right]
        if args.dir_b is not None
        else None,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print_parsed_items("A", args.dir_a, left)
    if args.dir_b is not None:
        print_parsed_items("B", args.dir_b, right)
    return 0

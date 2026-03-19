# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
from __future__ import annotations

import json
from argparse import Namespace

from ..parser import collect_audio_metadata
from .common import (
    make_progress_callback,
    normalize_extensions,
    print_ab_header,
    print_parsed_items,
    validate_directory,
)


def cmd_parse(args: Namespace) -> int:
    validate_directory(args.dir_a, "dir_a")
    if args.dir_b is not None:
        validate_directory(args.dir_b, "dir_b")
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

    print_ab_header("Parse", args.dir_a, args.dir_b)
    print_parsed_items("A", args.dir_a, left)
    if args.dir_b is not None:
        print_parsed_items("B", args.dir_b, right)
    return 0

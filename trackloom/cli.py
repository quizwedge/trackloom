# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .commands.apply import cmd_apply
from .commands.compare import cmd_compare
from .commands.parse import cmd_parse
from .commands.plan import cmd_plan
from .commands.review import cmd_review
from .mode import MODE_PLEX, MODE_STANDARD
from .parser import SUPPORTED_EXTENSIONS

EXIT_SUCCESS = 0
EXIT_BLOCKED = 2
EXIT_CANCELLED = 3


def _find_subparser(
    parser: argparse.ArgumentParser, name: str
) -> argparse.ArgumentParser | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparser = action.choices.get(name)
            if isinstance(subparser, argparse.ArgumentParser):
                return subparser
    return None


def _advanced_help(help_text: str, show_advanced: bool) -> str:
    return help_text if show_advanced else argparse.SUPPRESS


def build_arg_parser(show_advanced: bool = False) -> argparse.ArgumentParser:
    def adv(help_text: str) -> str:
        return _advanced_help(help_text, show_advanced)

    parser = argparse.ArgumentParser(
        prog="trackloom",
        description="Compare audio files in two directories (step 1: parsing fields).",
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    parse_cmd = subparsers.add_parser(
        "parse",
        help="Catalog one directory or compare two directories by parsed fields.",
    )
    parse_cmd.add_argument(
        "dir_a",
        type=Path,
        help="Audio library directory A",
    )
    parse_cmd.add_argument(
        "dir_b",
        nargs="?",
        type=Path,
        default=None,
        help="Optional audio library directory B",
    )
    parse_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help=adv("Audio extensions to scan (ex: .mp3 .flac .m4a)"),
    )
    parse_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print results as JSON",
    )
    parse_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    compare_cmd = subparsers.add_parser(
        "compare",
        help="Compare two directories using exact and fuzzy matching.",
    )
    compare_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    compare_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    compare_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help=adv("Audio extensions to scan (ex: .mp3 .flac .m4a)"),
    )
    compare_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help=adv("Minimum fuzzy score to include a candidate (0.0-1.0)"),
    )
    compare_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help=adv("Duration considered close for fuzzy scoring"),
    )
    compare_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help=adv("Duration difference above this is a conflict"),
    )
    compare_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help=adv("Minimum song similarity to consider fuzzy candidate"),
    )
    compare_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help=adv("Minimum artist similarity to consider fuzzy candidate"),
    )
    compare_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help=adv("Maximum fuzzy candidates to include in output"),
    )
    compare_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print results as JSON",
    )
    compare_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    plan_cmd = subparsers.add_parser(
        "plan",
        help="Create a copy/add plan to bring tracks from A into B.",
    )
    plan_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    plan_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    plan_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help=adv("Audio extensions to scan (ex: .mp3 .flac .m4a)"),
    )
    plan_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help=adv("Minimum fuzzy score to include a candidate (0.0-1.0)"),
    )
    plan_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help=adv("Duration considered close for fuzzy scoring"),
    )
    plan_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help=adv("Duration difference above this is a conflict"),
    )
    plan_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help=adv("Minimum song similarity to consider fuzzy candidate"),
    )
    plan_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help=adv("Minimum artist similarity to consider fuzzy candidate"),
    )
    plan_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help=adv("Maximum fuzzy candidates to include in output"),
    )
    plan_cmd.add_argument(
        "--mode",
        choices=[MODE_STANDARD, MODE_PLEX],
        default=MODE_STANDARD,
        help="Operation filtering mode",
    )
    plan_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print plan as JSON",
    )
    plan_cmd.add_argument(
        "--write-plan-json",
        type=Path,
        default=None,
        help="Write plan payload to a JSON file",
    )
    plan_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    apply_cmd = subparsers.add_parser(
        "apply",
        help="Apply copy/add operations to bring tracks from A into B.",
    )
    apply_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    apply_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    apply_cmd.add_argument(
        "--from-plan-json",
        type=Path,
        default=None,
        help="Apply operations from a saved plan JSON file",
    )
    apply_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help=adv("Audio extensions to scan (ex: .mp3 .flac .m4a)"),
    )
    apply_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help=adv("Minimum fuzzy score to include a candidate (0.0-1.0)"),
    )
    apply_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help=adv("Duration considered close for fuzzy scoring"),
    )
    apply_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help=adv("Duration difference above this is a conflict"),
    )
    apply_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help=adv("Minimum song similarity to consider fuzzy candidate"),
    )
    apply_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help=adv("Minimum artist similarity to consider fuzzy candidate"),
    )
    apply_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help=adv("Maximum fuzzy candidates to include in output"),
    )
    apply_cmd.add_argument(
        "--mode",
        choices=[MODE_STANDARD, MODE_PLEX],
        default=MODE_STANDARD,
        help="Operation filtering mode",
    )
    apply_cmd.add_argument(
        "--yes",
        action="store_true",
        help="Apply operations without confirmation prompt",
    )
    apply_cmd.add_argument(
        "--force",
        action="store_true",
        help="Bypass extra confirmation when using --yes without --dry-run",
    )
    apply_cmd.add_argument(
        "--cleanup-mode",
        choices=["none", "move-to-quarantine"],
        default="move-to-quarantine",
        help="Cleanup behavior for replace actions (default: move-to-quarantine)",
    )
    apply_cmd.add_argument(
        "--quarantine-dir",
        type=Path,
        default=None,
        help="Optional quarantine destination (default: <dir_b>/.trackloom_quarantine)",
    )
    apply_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing files",
    )
    apply_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print apply result as JSON",
    )
    apply_cmd.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Write apply report payload to a JSON file",
    )
    apply_cmd.add_argument(
        "--report-csv",
        type=Path,
        default=None,
        help="Write apply operation report to a CSV file",
    )
    apply_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    review_cmd = subparsers.add_parser(
        "review",
        help="Interactively review manual-review items and build a plan.",
    )
    review_cmd.add_argument("dir_a", type=Path, help="Audio library directory A")
    review_cmd.add_argument("dir_b", type=Path, help="Audio library directory B")
    review_cmd.add_argument(
        "--extensions",
        nargs="+",
        default=sorted(SUPPORTED_EXTENSIONS),
        help=adv("Audio extensions to scan (ex: .mp3 .flac .m4a)"),
    )
    review_cmd.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        help=adv("Minimum fuzzy score to include a candidate (0.0-1.0)"),
    )
    review_cmd.add_argument(
        "--close-duration-seconds",
        type=float,
        default=1.0,
        help=adv("Duration considered close for fuzzy scoring"),
    )
    review_cmd.add_argument(
        "--duration-conflict-seconds",
        type=float,
        default=5.0,
        help=adv("Duration difference above this is a conflict"),
    )
    review_cmd.add_argument(
        "--min-song-sim",
        type=float,
        default=0.82,
        help=adv("Minimum song similarity to consider fuzzy candidate"),
    )
    review_cmd.add_argument(
        "--min-artist-sim",
        type=float,
        default=0.65,
        help=adv("Minimum artist similarity to consider fuzzy candidate"),
    )
    review_cmd.add_argument(
        "--top-k",
        type=int,
        default=20,
        help=adv("Maximum fuzzy candidates to include in output"),
    )
    review_cmd.add_argument(
        "--mode",
        choices=[MODE_STANDARD, MODE_PLEX],
        default=MODE_STANDARD,
        help="Operation filtering mode for reviewed plan output",
    )
    review_cmd.add_argument(
        "--page-size",
        type=int,
        default=20,
        help="Number of manual-review items shown per page",
    )
    review_cmd.add_argument(
        "--max-manual-items",
        type=int,
        default=1000,
        help="Safety cap for interactive manual-review items (0 disables cap)",
    )
    review_cmd.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="1-based item index to start review from",
    )
    review_cmd.add_argument(
        "--write-plan-json",
        type=Path,
        default=None,
        help="Write reviewed plan payload to a JSON file",
    )
    review_cmd.add_argument(
        "--export-manual-review-json",
        type=Path,
        default=None,
        help="Write manual-review candidate details and summary to JSON",
    )
    review_cmd.add_argument(
        "--decisions-file",
        type=Path,
        default=None,
        help="Load and autosave review decisions to a JSON file",
    )
    review_cmd.add_argument(
        "--json",
        action="store_true",
        help="Print reviewed plan as JSON",
    )
    review_cmd.add_argument(
        "--progress",
        action="store_true",
        help="Show live scan progress on stderr",
    )

    help_cmd = subparsers.add_parser("help", help="Show help for commands.")
    help_cmd.add_argument(
        "topic",
        nargs="?",
        choices=["parse", "compare", "plan", "apply", "review"],
        help="Optional command to show detailed help for",
    )
    help_adv_cmd = subparsers.add_parser(
        "help-advanced", help="Show advanced help for commands."
    )
    help_adv_cmd.add_argument(
        "topic",
        nargs="?",
        choices=["parse", "compare", "plan", "apply", "review"],
        help="Optional command to show detailed help for",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "parse":
            return cmd_parse(args)
        if args.command == "compare":
            return cmd_compare(args)
        if args.command == "plan":
            return cmd_plan(args)
        if args.command == "apply":
            return cmd_apply(args)
        if args.command == "review":
            return cmd_review(args)
        if args.command == "help":
            if args.topic:
                subparser = _find_subparser(parser, args.topic)
                if subparser is not None:
                    subparser.print_help()
                    return 0
            parser.print_help()
            return 0
        if args.command == "help-advanced":
            advanced_parser = build_arg_parser(show_advanced=True)
            if args.topic:
                subparser = _find_subparser(advanced_parser, args.topic)
                if subparser is not None:
                    subparser.print_help()
                    return 0
            advanced_parser.print_help()
            return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

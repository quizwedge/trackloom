# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import tempfile
import unittest
from pathlib import Path

from trackloom.review import (
    build_plan_from_review_decisions,
    extract_manual_review_candidates,
    summarize_manual_review_candidates,
    validate_manual_item_limit,
)


def _file_record(path: str, rel: str):
    return {"absolute_path": path, "relative_path": rel}


class ReviewTests(unittest.TestCase):
    def test_extract_manual_review_candidates(self):
        payload = {
            "exact_matches": [
                {
                    "recommended_action": "manual_review",
                    "file_a": _file_record("/a/1.mp3", "Artist/Album/1.mp3"),
                    "file_b": _file_record("/b/1.mp3", "Artist/Album/1.mp3"),
                },
                {
                    "recommended_action": "keep_b",
                    "file_a": _file_record("/a/2.mp3", "Artist/Album/2.mp3"),
                    "file_b": _file_record("/b/2.mp3", "Artist/Album/2.mp3"),
                },
            ],
            "fuzzy_candidates": [
                {
                    "recommended_action": "manual_review",
                    "score": 0.9,
                    "file_a": _file_record("/a/3.mp3", "Artist/Album/3.mp3"),
                    "file_b": _file_record("/b/3.mp3", "Artist/Album/3.mp3"),
                }
            ],
        }
        candidates = extract_manual_review_candidates(payload)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["source"], "exact")
        self.assertEqual(candidates[1]["source"], "fuzzy")

    def test_build_plan_from_review_decisions(self):
        candidates = [
            {
                "id": "exact:0",
                "source": "exact",
                "file_a": _file_record("/tmp/a/song.wav", "Artist/Album/song.wav"),
                "file_b": _file_record("/tmp/b/song.mp3", "Artist/Album/song.mp3"),
            },
            {
                "id": "fuzzy:0",
                "source": "fuzzy",
                "file_a": _file_record("/tmp/a/song2.mp3", "Artist/Album/song2.mp3"),
                "file_b": _file_record("/tmp/b/song2.mp3", "Artist/Album/song2.mp3"),
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan_from_review_decisions(
                candidates,
                decisions={"exact:0": "replace_in_b_with_a", "fuzzy:0": "add_to_b"},
                dir_b=Path(tmp),
            )
        self.assertEqual(plan["review_action_counts"]["replace_in_b_with_a"], 1)
        self.assertEqual(plan["review_action_counts"]["add_to_b"], 1)
        self.assertEqual(plan["counts"]["operations"], 2)

    def test_validate_manual_item_limit_allows_under_cap(self):
        validate_manual_item_limit(total=10, max_manual_items=10)
        validate_manual_item_limit(total=9, max_manual_items=10)

    def test_validate_manual_item_limit_raises_over_cap(self):
        with self.assertRaises(RuntimeError):
            validate_manual_item_limit(total=11, max_manual_items=10)

    def test_summarize_manual_review_candidates(self):
        candidates = [
            {"source": "exact", "duplicate_policy": {"classification": "duration_conflict"}},
            {"source": "fuzzy", "duplicate_policy": {"classification": "duration_conflict"}},
            {"source": "fuzzy", "duplicate_policy": {"classification": "version_conflict"}},
        ]
        summary = summarize_manual_review_candidates(candidates)
        self.assertEqual(summary["total_manual_review_items"], 3)
        self.assertEqual(summary["source_counts"]["exact"], 1)
        self.assertEqual(summary["source_counts"]["fuzzy"], 2)
        self.assertEqual(summary["policy_counts"]["duration_conflict"], 2)
        self.assertEqual(summary["policy_counts"]["version_conflict"], 1)


if __name__ == "__main__":
    unittest.main()

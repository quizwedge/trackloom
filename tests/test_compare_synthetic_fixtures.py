# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import unittest
from pathlib import Path
from typing import List, Optional

from trackloom.compare import compare_collections
from trackloom.parser import ParsedAudioFile, ParsedFields


def make_file(
    relative_path: str,
    artist: str,
    album: str,
    song: str,
    duration: float,
    *,
    extension: Optional[str] = None,
    version_hints: Optional[List[str]] = None,
) -> ParsedAudioFile:
    ext = extension or (Path(relative_path).suffix.lower() or ".mp3")
    path_fields = ParsedFields(artist=artist, album=album, song=song)
    return ParsedAudioFile(
        root="/music",
        absolute_path="/music/" + relative_path,
        relative_path=relative_path,
        extension=ext,
        duration_seconds=duration,
        bitrate_kbps=None,
        sample_rate_hz=None,
        bit_depth=None,
        channels=None,
        codec=None,
        path_fields=path_fields,
        tag_fields=ParsedFields(None, None, None),
        normalized_path_fields=ParsedFields(artist=artist, album=album, song=song),
        normalized_tag_fields=ParsedFields(None, None, None),
        version_hints=version_hints or [],
    )


class SyntheticFixtureSuiteTests(unittest.TestCase):
    def test_exact_duration_boundary_behaviors(self):
        close_a = make_file(
            "A/Artist/Album/Close.mp3", "Artist", "Album", "Close", 200.0
        )
        close_b = make_file(
            "B/Artist/Album/Close.mp3", "Artist", "Album", "Close", 200.9
        )
        conflict_a = make_file(
            "A/Artist/Album/Conflict.mp3", "Artist", "Album", "Conflict", 210.0
        )
        conflict_b = make_file(
            "B/Artist/Album/Conflict.mp3", "Artist", "Album", "Conflict", 215.0
        )

        result = compare_collections([close_a, conflict_a], [close_b, conflict_b])
        self.assertEqual(result["exact_match_count"], 2)

        by_song = {item["key"]["song"]: item for item in result["exact_matches"]}
        self.assertEqual(
            by_song["Close"]["duplicate_policy"]["classification"], "likely_duplicate"
        )
        self.assertEqual(
            by_song["Conflict"]["duplicate_policy"]["classification"],
            "duration_conflict",
        )
        self.assertEqual(by_song["Conflict"]["recommended_action"], "manual_review")

    def test_exact_version_and_lossless_boundaries(self):
        version_a = make_file(
            "A/Artist/Album/Song.mp3",
            "Artist",
            "Album",
            "Versioned Song",
            200.0,
            version_hints=["remaster", "remaster_year_1994"],
        )
        version_b = make_file(
            "B/Artist/Album/Song.mp3",
            "Artist",
            "Album",
            "Versioned Song",
            200.0,
            version_hints=["remaster", "remaster_year_2011"],
        )

        quality_a = make_file(
            "A/Artist/Album/Quality.wav",
            "Artist",
            "Album",
            "Quality",
            190.0,
            extension=".wav",
        )
        quality_b = make_file(
            "B/Artist/Album/Quality.mp3",
            "Artist",
            "Album",
            "Quality",
            190.0,
            extension=".mp3",
        )

        result = compare_collections([version_a, quality_a], [version_b, quality_b])
        by_song = {item["key"]["song"]: item for item in result["exact_matches"]}

        self.assertEqual(
            by_song["Versioned Song"]["duplicate_policy"]["classification"],
            "version_conflict",
        )
        self.assertEqual(
            by_song["Versioned Song"]["recommended_action"], "keep_both_versions"
        )

        self.assertEqual(by_song["Quality"]["duplicate_policy"]["preferred_side"], "a")
        self.assertIn(
            "lossless_vs_lossy_hard_boundary",
            by_song["Quality"]["duplicate_policy"]["reasons"],
        )
        self.assertEqual(
            by_song["Quality"]["recommended_action"], "replace_in_b_with_a"
        )

    def test_fuzzy_typo_candidate_and_duration_rejection(self):
        # Candidate should pass fuzzy text match but still require manual review.
        fuzzy_a = make_file(
            "A/Artist/Album/Believer.wav",
            "Imagine Dragons",
            "Evolve",
            "Believer",
            204.0,
            extension=".wav",
        )
        fuzzy_b = make_file(
            "B/Artist/Album/Beliver.mp3",
            "Imagine Dragon",
            "Evolve",
            "Beliver",
            205.0,
            extension=".mp3",
        )

        # Similar title/artist but duration over conflict threshold should reject.
        reject_a = make_file(
            "A/Artist/Album/Natural.mp3", "Imagine Dragons", "Evolve", "Natural", 180.0
        )
        reject_b = make_file(
            "B/Artist/Album/Naturl.mp3", "Imagine Dragon", "Evolve", "Naturl", 186.0
        )

        result = compare_collections(
            [fuzzy_a, reject_a],
            [fuzzy_b, reject_b],
            fuzzy_threshold=0.60,
            min_song_similarity=0.60,
            min_artist_similarity=0.60,
            close_duration_seconds=1.0,
            duration_conflict_seconds=5.0,
            top_k=10,
        )

        self.assertEqual(result["fuzzy_candidate_count"], 1)
        candidate = result["fuzzy_candidates"][0]
        self.assertEqual(candidate["recommended_action"], "manual_review")
        self.assertLessEqual(candidate["duration_diff_seconds"], 5.0)

        self.assertGreaterEqual(result["fuzzy_rejection_count"], 1)
        reasons = {
            reason for item in result["fuzzy_rejections"] for reason in item["reasons"]
        }
        self.assertIn("duration_conflict", reasons)


if __name__ == "__main__":
    unittest.main()

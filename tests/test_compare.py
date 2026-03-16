# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import unittest
from pathlib import Path

from trackloom.compare import assess_duplicate_pair, canonical_key, compare_collections
from trackloom.parser import ParsedAudioFile, ParsedFields


def make_file(
    relative_path,
    artist,
    album,
    song,
    duration,
    norm_artist=None,
    norm_album=None,
    norm_song=None,
):
    path_fields = ParsedFields(artist=artist, album=album, song=song)
    return ParsedAudioFile(
        root="/music",
        absolute_path="/music/" + relative_path,
        relative_path=relative_path,
        extension=Path(relative_path).suffix.lower() or ".mp3",
        duration_seconds=duration,
        bitrate_kbps=None,
        sample_rate_hz=None,
        bit_depth=None,
        channels=None,
        codec=None,
        path_fields=path_fields,
        tag_fields=ParsedFields(None, None, None),
        normalized_path_fields=ParsedFields(
            artist=norm_artist or artist,
            album=norm_album or album,
            song=norm_song or song,
        ),
        normalized_tag_fields=ParsedFields(None, None, None),
        version_hints=[],
    )


class CompareCollectionsTests(unittest.TestCase):
    def test_canonical_key_prefers_normalized_tag_fields(self):
        item = ParsedAudioFile(
            root="/music",
            absolute_path="/music/a.mp3",
            relative_path="a.mp3",
            extension=".mp3",
            duration_seconds=100.0,
            bitrate_kbps=None,
            sample_rate_hz=None,
            bit_depth=None,
            channels=None,
            codec=None,
            path_fields=ParsedFields("Path Artist", "Path Album", "Path Song"),
            tag_fields=ParsedFields("Tag Artist", "Tag Album", "Tag Song"),
            normalized_path_fields=ParsedFields(
                "path artist", "path album", "path song"
            ),
            normalized_tag_fields=ParsedFields("tag artist", "tag album", "tag song"),
            version_hints=[],
        )
        self.assertEqual(canonical_key(item), ("tag artist", "tag album", "tag song"))

    def test_compare_returns_exact_and_only_sets(self):
        a1 = make_file("A/Album/Song1.mp3", "A", "Album", "Song1", 100.0)
        a2 = make_file("A/Album/OnlyA.mp3", "A", "Album", "OnlyA", 120.0)
        b1 = make_file("A/Album/Song1-copy.mp3", "A", "Album", "Song1", 100.2)
        b2 = make_file("A/Album/OnlyB.mp3", "A", "Album", "OnlyB", 130.0)

        result = compare_collections([a1, a2], [b1, b2], top_k=5, fuzzy_threshold=0.5)

        self.assertEqual(result["exact_match_count"], 1)
        self.assertEqual(result["only_in_a_count"], 1)
        self.assertEqual(result["only_in_b_count"], 1)
        self.assertGreaterEqual(result["action_counts"]["add_to_b"], 1)
        self.assertGreaterEqual(result["action_counts"]["keep_b"], 1)

    def test_compare_emits_fuzzy_candidate_for_close_song_artist_duration(self):
        a = make_file(
            "A/Album/Believer.mp3", "Imagine Dragons", "Evolve", "Believer", 204.0
        )
        b = make_file(
            "B/Album/Beliver.mp3",
            "Imagine Dragon",
            "Evolve",
            "Beliver",
            205.0,
        )

        result = compare_collections(
            [a],
            [b],
            fuzzy_threshold=0.60,
            close_duration_seconds=3.0,
            duration_conflict_seconds=12.0,
            top_k=5,
        )

        self.assertEqual(result["exact_match_count"], 0)
        self.assertEqual(result["fuzzy_candidate_count"], 1)
        candidate = result["fuzzy_candidates"][0]
        self.assertGreater(candidate["score"], 0.60)
        self.assertLess(candidate["duration_diff_seconds"], 3.0)

    def test_duplicate_policy_prefers_higher_fidelity(self):
        a = make_file("A/Album/Song.wav", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        policy = assess_duplicate_pair(a, b)
        self.assertEqual(policy["classification"], "likely_duplicate")
        self.assertEqual(policy["preferred_side"], "a")

    def test_exact_match_recommends_replace_when_a_has_higher_fidelity(self):
        a = make_file("A/Album/Song.wav", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        result = compare_collections([a], [b])
        self.assertEqual(result["exact_match_count"], 1)
        match = result["exact_matches"][0]
        self.assertEqual(match["recommended_action"], "replace_in_b_with_a")
        self.assertEqual(result["action_counts"]["replace_in_b_with_a"], 1)

    def test_duplicate_policy_detects_version_conflict(self):
        a = make_file("A/Album/Song (Live).mp3", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 201.0)
        a.version_hints = ["live"]
        b.version_hints = []
        policy = assess_duplicate_pair(a, b)
        self.assertEqual(policy["classification"], "version_conflict")
        result = compare_collections([a], [b])
        self.assertEqual(
            result["exact_matches"][0]["recommended_action"], "keep_both_versions"
        )
        self.assertEqual(result["action_counts"]["keep_both_versions"], 1)

    def test_fuzzy_match_is_manual_review(self):
        a = make_file(
            "A/Album/Believer.wav", "Imagine Dragons", "Evolve", "Believer", 204.0
        )
        b = make_file(
            "B/Album/Beliver.mp3", "Imagine Dragon", "Evolve", "Beliver", 205.0
        )
        result = compare_collections(
            [a],
            [b],
            fuzzy_threshold=0.60,
            close_duration_seconds=3.0,
            duration_conflict_seconds=12.0,
            top_k=5,
        )
        self.assertEqual(result["fuzzy_candidate_count"], 1)
        candidate = result["fuzzy_candidates"][0]
        self.assertEqual(candidate["recommended_action"], "manual_review")

    def test_lossless_vs_lossy_is_hard_boundary(self):
        a = make_file("A/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.flac", "Artist", "Album", "Song", 200.0)
        policy = assess_duplicate_pair(a, b)
        self.assertEqual(policy["preferred_side"], "b")
        self.assertIn("lossless_vs_lossy_hard_boundary", policy["reasons"])

    def test_remaster_year_mismatch_keeps_both_versions(self):
        a = make_file("A/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        a.version_hints = ["remaster", "remaster_year_1994"]
        b.version_hints = ["remaster", "remaster_year_2011"]
        result = compare_collections([a], [b])
        self.assertEqual(
            result["exact_matches"][0]["duplicate_policy"]["classification"],
            "version_conflict",
        )
        self.assertEqual(
            result["exact_matches"][0]["recommended_action"], "keep_both_versions"
        )

    def test_duration_conflict_at_exactly_5_seconds(self):
        a = make_file("A/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 205.0)
        result = compare_collections([a], [b])
        match = result["exact_matches"][0]
        self.assertEqual(
            match["duplicate_policy"]["classification"], "duration_conflict"
        )
        self.assertEqual(match["recommended_action"], "manual_review")

    def test_manual_review_action_count_matches_top_k_truncated_fuzzy_candidates(self):
        a1 = make_file(
            "A/Album/Believer.wav", "Imagine Dragons", "Evolve", "Believer", 204.0
        )
        a2 = make_file(
            "A/Album/Natural.wav", "Imagine Dragons", "Evolve", "Natural", 185.0
        )
        b1 = make_file(
            "B/Album/Beliver.mp3", "Imagine Dragon", "Evolve", "Beliver", 205.0
        )
        b2 = make_file(
            "B/Album/Naturl.mp3", "Imagine Dragon", "Evolve", "Naturl", 186.0
        )

        result = compare_collections(
            [a1, a2],
            [b1, b2],
            fuzzy_threshold=0.55,
            min_song_similarity=0.55,
            min_artist_similarity=0.55,
            close_duration_seconds=1.0,
            duration_conflict_seconds=5.0,
            top_k=1,
        )

        self.assertEqual(result["fuzzy_candidate_count"], 1)
        self.assertEqual(result["fuzzy_dropped_count"], 1)
        self.assertEqual(result["action_counts"]["manual_review"], 1)
        self.assertEqual(result["only_in_a_count"], 0)
        self.assertEqual(result["only_in_b_count"], 0)

    def test_missing_canonical_fields_are_not_exact_matches(self):
        a = make_file("A/Unknown.mp3", None, None, None, 200.0)
        b = make_file("B/Unknown.mp3", None, None, None, 201.0)

        result = compare_collections([a], [b], top_k=5)

        self.assertEqual(result["exact_match_count"], 0)
        self.assertEqual(result["only_in_a_count"], 1)
        self.assertEqual(result["only_in_b_count"], 1)
        self.assertEqual(result["fuzzy_candidate_count"], 0)

    def test_fuzzy_candidates_are_not_counted_as_only_in(self):
        a = make_file(
            "A/Album/Believer.wav", "Imagine Dragons", "Evolve", "Believer", 204.0
        )
        b = make_file(
            "B/Album/Beliver.mp3", "Imagine Dragon", "Evolve", "Beliver", 205.0
        )

        result = compare_collections(
            [a],
            [b],
            fuzzy_threshold=0.60,
            close_duration_seconds=3.0,
            duration_conflict_seconds=12.0,
            top_k=5,
        )

        self.assertEqual(result["fuzzy_candidate_count"], 1)
        self.assertEqual(result["only_in_a_count"], 0)
        self.assertEqual(result["only_in_b_count"], 0)
        self.assertEqual(result["action_counts"]["add_to_b"], 0)

    def test_fuzzy_rejects_duration_conflict_at_threshold(self):
        a = make_file(
            "A/Album/Believer.wav", "Imagine Dragons", "Evolve", "Believer", 200.0
        )
        b = make_file(
            "B/Album/Beliver.mp3", "Imagine Dragon", "Evolve", "Beliver", 205.0
        )

        result = compare_collections(
            [a],
            [b],
            fuzzy_threshold=0.0,
            min_song_similarity=0.5,
            min_artist_similarity=0.5,
            close_duration_seconds=1.0,
            duration_conflict_seconds=5.0,
            top_k=10,
        )

        self.assertEqual(result["fuzzy_candidate_count"], 0)
        self.assertGreaterEqual(result["fuzzy_rejection_count"], 1)
        reasons = {
            reason for item in result["fuzzy_rejections"] for reason in item["reasons"]
        }
        self.assertIn("duration_conflict", reasons)

    def test_exact_pairing_prefers_matching_version_hints(self):
        a_live = make_file(
            "A/Album/01 - Song Live.mp3", "Artist", "Album", "Song", 200.0
        )
        a_clean = make_file("A/Album/02 - Song.mp3", "Artist", "Album", "Song", 200.0)
        b_clean = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        b_live = make_file("B/Album/Song (Live).mp3", "Artist", "Album", "Song", 200.0)

        a_live.version_hints = ["live"]
        b_live.version_hints = ["live"]

        result = compare_collections([a_live, a_clean], [b_clean, b_live])

        self.assertEqual(result["exact_match_count"], 2)
        self.assertEqual(result["duplicate_policy_counts"]["version_conflict"], 0)
        reasons = [
            reason
            for item in result["exact_matches"]
            for reason in item["duplicate_policy"].get("reasons", [])
        ]
        self.assertIn("matching_version_hints", reasons)
        self.assertEqual(result["action_counts"]["manual_review"], 0)

    def test_manual_review_action_count_includes_exact_matches(self):
        a = make_file("A/Album/Song.mp3", "Artist", "Album", "Song", 200.0)
        b = make_file("B/Album/Song.mp3", "Artist", "Album", "Song", 205.0)

        result = compare_collections([a], [b], top_k=0)

        self.assertEqual(result["exact_match_count"], 1)
        self.assertEqual(result["action_counts"]["manual_review"], 1)

    def test_deterministic_pairing_for_duplicate_keys(self):
        a1 = make_file("A/Album/02.mp3", "Artist", "Album", "Song", 200.0)
        a2 = make_file("A/Album/01.mp3", "Artist", "Album", "Song", 200.0)
        b1 = make_file("B/Album/01.mp3", "Artist", "Album", "Song", 200.0)
        b2 = make_file("B/Album/02.mp3", "Artist", "Album", "Song", 200.0)

        result = compare_collections([a1, a2], [b1, b2], top_k=0)

        pairs = {
            (
                Path(match["file_a"]["relative_path"]).name,
                Path(match["file_b"]["relative_path"]).name,
            )
            for match in result["exact_matches"]
        }
        self.assertEqual(pairs, {("01.mp3", "01.mp3"), ("02.mp3", "02.mp3")})


if __name__ == "__main__":
    unittest.main()

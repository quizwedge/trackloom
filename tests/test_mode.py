# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import unittest

from trackloom.mode import (
    MODE_PLEX,
    MODE_STANDARD,
    _detect_extension,
    assess_plex_compatibility,
    filter_operations_for_mode,
)


class ModeTests(unittest.TestCase):
    def test_detect_extension_prefers_explicit_source_extension(self):
        self.assertEqual(
            _detect_extension(
                {
                    "source_extension": ".FLAC",
                    "source_path": "/tmp/song.mp3",
                    "source_relative_path": "Artist/Album/song.aac",
                }
            ),
            ".flac",
        )

    def test_detect_extension_falls_back_to_relative_path_and_empty(self):
        self.assertEqual(
            _detect_extension({"source_relative_path": "Artist/Album/song.opus"}),
            ".opus",
        )
        self.assertEqual(_detect_extension({}), "")

    def test_assess_plex_compatibility_blocks_m4p(self):
        ok, reason = assess_plex_compatibility(
            {
                "source_path": "/tmp/song.m4p",
                "source_relative_path": "Artist/Album/song.m4p",
            }
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "drm_or_protected_extension")

    def test_assess_plex_compatibility_allows_mp3(self):
        ok, reason = assess_plex_compatibility(
            {
                "source_path": "/tmp/song.mp3",
                "source_relative_path": "Artist/Album/song.mp3",
                "source_extension": ".mp3",
            }
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_assess_plex_compatibility_blocks_unknown_extension(self):
        ok, reason = assess_plex_compatibility(
            {
                "source_path": "/tmp/song.xyz",
                "source_relative_path": "Artist/Album/song.xyz",
            }
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "unsupported_extension_for_plex_mode")

    def test_assess_plex_compatibility_blocks_drm_codec(self):
        ok, reason = assess_plex_compatibility(
            {
                "source_path": "/tmp/song.m4a",
                "source_relative_path": "Artist/Album/song.m4a",
                "source_codec": "Protected AAC",
            }
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "drm_or_protected_codec")

    def test_filter_operations_for_mode(self):
        operations = [
            {"action": "add_to_b", "source_path": "/tmp/a.mp3"},
            {"action": "add_to_b", "source_path": "/tmp/b.m4p"},
        ]
        kept, skipped = filter_operations_for_mode(operations, MODE_PLEX)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["reason"], "drm_or_protected_extension")

    def test_filter_operations_standard_mode(self):
        operations = [{"action": "add_to_b", "source_path": "/tmp/b.m4p"}]
        kept, skipped = filter_operations_for_mode(operations, MODE_STANDARD)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(skipped), 0)

    def test_filter_operations_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            filter_operations_for_mode([], "foobar")


if __name__ == "__main__":
    unittest.main()

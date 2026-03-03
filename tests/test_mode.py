# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
import unittest

from trackloom.mode import (
    MODE_PLEX,
    MODE_STANDARD,
    assess_plex_compatibility,
    filter_operations_for_mode,
)


class ModeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

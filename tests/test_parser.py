# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trackloom import parser


class NormalizeSongFromStemTests(unittest.TestCase):
    def test_strips_common_track_prefix_patterns(self) -> None:
        cases = {
            "01 - Song Name": "Song Name",
            "1. Song Name": "Song Name",
            "07_Song Name": "Song Name",
            "Track 09 - Song Name": "Song Name",
            "CD1-03 - Song Name": "Song Name",
        }
        for stem, expected in cases.items():
            with self.subTest(stem=stem):
                self.assertEqual(parser.normalize_song_from_stem(stem), expected)

    def test_leaves_plain_titles_unchanged(self) -> None:
        self.assertEqual(parser.normalize_song_from_stem("Song Name"), "Song Name")

    def test_returns_none_for_empty_or_missing_stem(self) -> None:
        self.assertIsNone(parser.normalize_song_from_stem(""))
        self.assertIsNone(parser.normalize_song_from_stem(None))


class NormalizeForMatchTests(unittest.TestCase):
    def test_replaces_hyphens_and_underscores_with_spaces(self) -> None:
        value = "The_Best-Song---Ever"
        self.assertEqual(parser.normalize_for_match(value), "the best song ever")

    def test_cleans_up_whitespace(self) -> None:
        value = "  Song___Name   -  Live "
        self.assertEqual(parser.normalize_for_match(value), "song name live")

    def test_normalizes_ampersand_and_punctuation(self) -> None:
        value = "Lost & Found!!!"
        self.assertEqual(parser.normalize_for_match(value), "lost and found")


class ParsePathFieldsTests(unittest.TestCase):
    def test_parses_artist_album_song_from_nested_path(self) -> None:
        root = Path("/library")
        file_path = root / "Artist A" / "Album B" / "01 - Song C.mp3"

        parsed = parser.parse_fields_from_path(file_path, root)

        self.assertEqual(parsed.artist, "Artist A")
        self.assertEqual(parsed.album, "Album B")
        self.assertEqual(parsed.song, "Song C")

    def test_parses_album_and_song_from_two_level_path(self) -> None:
        root = Path("/library")
        file_path = root / "Album B" / "07 - Song C.flac"

        parsed = parser.parse_fields_from_path(file_path, root)

        self.assertIsNone(parsed.artist)
        self.assertEqual(parsed.album, "Album B")
        self.assertEqual(parsed.song, "Song C")

    def test_parses_disc_folder_paths_with_artist_album(self) -> None:
        root = Path("/library")
        file_path = root / "Artist A" / "Album B" / "CD1" / "01 - Song C.mp3"

        parsed = parser.parse_fields_from_path(file_path, root)

        self.assertEqual(parsed.artist, "Artist A")
        self.assertEqual(parsed.album, "Album B")
        self.assertEqual(parsed.song, "Song C")

    def test_disc_folder_requires_artist_album_depth(self) -> None:
        root = Path("/library")
        file_path = root / "Album B" / "Disc 2" / "01 - Song C.mp3"

        parsed = parser.parse_fields_from_path(file_path, root)

        self.assertEqual(parsed.artist, "Album B")
        self.assertEqual(parsed.album, "Disc 2")
        self.assertEqual(parsed.song, "Song C")


class ParseTagFieldsTests(unittest.TestCase):
    def test_returns_none_fields_when_mutagen_unavailable(self) -> None:
        with patch.object(parser, "MutagenFile", None):
            parsed = parser.parse_fields_from_tags(Path("/tmp/test.mp3"))
        self.assertIsNone(parsed.artist)
        self.assertIsNone(parsed.album)
        self.assertIsNone(parsed.song)

    def test_reads_common_tag_keys(self) -> None:
        fake_audio = type(
            "FakeAudio",
            (),
            {
                "tags": {
                    "artist": ["Artist X"],
                    "album": ["Album Y"],
                    "title": ["Song Z"],
                }
            },
        )()
        with patch.object(parser, "MutagenFile", return_value=fake_audio):
            parsed = parser.parse_fields_from_tags(Path("/tmp/test.mp3"))

        self.assertEqual(parsed.artist, "Artist X")
        self.assertEqual(parsed.album, "Album Y")
        self.assertEqual(parsed.song, "Song Z")

    def test_reads_id3_style_keys(self) -> None:
        fake_audio = type(
            "FakeAudio",
            (),
            {"tags": {"TPE1": ["Artist X"], "TALB": ["Album Y"], "TIT2": ["Song Z"]}},
        )()
        with patch.object(parser, "MutagenFile", return_value=fake_audio):
            parsed = parser.parse_fields_from_tags(Path("/tmp/test.mp3"))

        self.assertEqual(parsed.artist, "Artist X")
        self.assertEqual(parsed.album, "Album Y")
        self.assertEqual(parsed.song, "Song Z")

    def test_parses_duration_seconds(self) -> None:
        fake_info = type("FakeInfo", (), {"length": 245.7})()
        fake_audio = type("FakeAudio", (), {"tags": {}, "info": fake_info})()
        with patch.object(parser, "MutagenFile", return_value=fake_audio):
            duration = parser.parse_duration_seconds(Path("/tmp/test.mp3"))
        self.assertEqual(duration, 245.7)

    def test_duration_parsing_handles_missing_or_invalid_length(self) -> None:
        no_info_audio = type("FakeAudio", (), {"tags": {}, "info": None})()
        bad_info_audio = type(
            "FakeAudio",
            (),
            {
                "tags": {},
                "info": type("FakeInfo", (), {"length": "bad"})(),
            },
        )()

        with patch.object(parser, "MutagenFile", return_value=no_info_audio):
            self.assertIsNone(parser.parse_duration_seconds(Path("/tmp/test.mp3")))
        with patch.object(parser, "MutagenFile", return_value=bad_info_audio):
            self.assertIsNone(parser.parse_duration_seconds(Path("/tmp/test.mp3")))

    def test_parses_audio_quality_fields(self) -> None:
        fake_info = type(
            "FakeInfo",
            (),
            {
                "bitrate": 320000,
                "sample_rate": 48000,
                "bits_per_sample": 24,
                "channels": 2,
                "codec": "FLAC",
            },
        )()
        fake_audio = type("FakeAudio", (), {"tags": {}, "info": fake_info})()
        with patch.object(parser, "MutagenFile", return_value=fake_audio):
            quality = parser.parse_audio_quality(Path("/tmp/test.flac"))
        self.assertEqual(quality["bitrate_kbps"], 320)
        self.assertEqual(quality["sample_rate_hz"], 48000)
        self.assertEqual(quality["bit_depth"], 24)
        self.assertEqual(quality["channels"], 2)
        self.assertEqual(quality["codec"], "FLAC")

    def test_audio_quality_handles_missing_info_and_invalid_numbers(self) -> None:
        no_info_audio = type("FakeAudio", (), {"tags": {}, "info": None})()
        bad_info = type(
            "FakeInfo",
            (),
            {
                "bitrate": "bad",
                "sample_rate": "bad",
                "bits_per_sample": "bad",
                "channels": "bad",
                "codec": None,
                "codec_description": "AAC",
            },
        )()
        bad_audio = type("FakeAudio", (), {"tags": {}, "info": bad_info})()

        with patch.object(parser, "MutagenFile", return_value=no_info_audio):
            quality = parser.parse_audio_quality(Path("/tmp/test.flac"))
        self.assertEqual(
            quality,
            {
                "bitrate_kbps": None,
                "sample_rate_hz": None,
                "bit_depth": None,
                "channels": None,
                "codec": None,
            },
        )
        with patch.object(parser, "MutagenFile", return_value=bad_audio):
            quality = parser.parse_audio_quality(Path("/tmp/test.flac"))
        self.assertEqual(quality["codec"], "AAC")
        self.assertIsNone(quality["bitrate_kbps"])


class VersionClassifierTests(unittest.TestCase):
    def test_classifies_common_version_hints(self) -> None:
        hints = parser.classify_version_hints(
            song_from_path="Song Name (Live) - Remastered 2011",
            song_from_tag="Song Name (Radio Edit)",
        )
        self.assertIn("live", hints)
        self.assertIn("remaster", hints)
        self.assertIn("radio_edit", hints)

    def test_classifies_remaster_year_as_distinct_hint(self) -> None:
        hints = parser.classify_version_hints(
            song_from_path="Song Name (Remastered 2011)",
            song_from_tag=None,
        )
        self.assertIn("remaster", hints)
        self.assertIn("remaster_year_2011", hints)

    def test_classify_version_hints_handles_empty_and_deduplicates(self) -> None:
        self.assertEqual(parser.classify_version_hints(None, None), [])
        hints = parser.classify_version_hints(
            song_from_path=(
                "Live Live Clean Explicit Stereo Mono Acoustic Instrumental Karaoke"
            ),
            song_from_tag="Live",
        )
        self.assertEqual(hints.count("live"), 1)
        self.assertIn("acoustic", hints)
        self.assertIn("instrumental", hints)
        self.assertIn("karaoke", hints)
        self.assertIn("mono", hints)
        self.assertIn("stereo", hints)
        self.assertIn("clean", hints)
        self.assertIn("explicit", hints)


class CollectAudioMetadataTests(unittest.TestCase):
    def test_collects_audio_files_and_supports_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artist_album = root / "Artist A" / "Album B"
            artist_album.mkdir(parents=True)
            (artist_album / "01 - Song One.mp3").touch()
            (artist_album / "Song Two.wav").touch()
            (artist_album / "cover.jpg").touch()

            results = parser.collect_audio_metadata(root)

            self.assertEqual(len(results), 2)
            self.assertEqual(sorted([r.extension for r in results]), [".mp3", ".wav"])
            songs = sorted([r.path_fields.song for r in results])
            self.assertEqual(songs, ["Song One", "Song Two"])

    def test_collect_respects_extension_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artist_album = root / "Artist A" / "Album B"
            artist_album.mkdir(parents=True)
            (artist_album / "Song One.mp3").touch()
            (artist_album / "Song Two.wav").touch()

            results = parser.collect_audio_metadata(root, extensions={".mp3"})

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].extension, ".mp3")
            self.assertEqual(results[0].normalized_path_fields.song, "song one")

    def test_collect_raises_for_missing_directory(self) -> None:
        with self.assertRaises(FileNotFoundError):
            parser.collect_audio_metadata(Path("/definitely/missing/path"))

    def test_collect_raises_for_non_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "song.mp3"
            file_path.write_text("x")

            with self.assertRaises(NotADirectoryError):
                parser.collect_audio_metadata(file_path)

    def test_collect_calls_progress_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artist_album = root / "Artist A" / "Album B"
            artist_album.mkdir(parents=True)
            (artist_album / "Song One.mp3").touch()
            (artist_album / "Song Two.wav").touch()

            calls = []

            def callback(current, total, path):
                calls.append((current, total, path.name))

            parser.collect_audio_metadata(root, progress_callback=callback)

            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][0], 1)
            self.assertEqual(calls[0][1], 2)
            self.assertEqual(calls[1][0], 2)
            self.assertEqual(calls[1][1], 2)

    def test_collect_includes_normalized_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artist_album = root / "Artist_Name" / "Best-Hits"
            artist_album.mkdir(parents=True)
            (artist_album / "01-The_Best-Song.mp3").touch()

            results = parser.collect_audio_metadata(root)

            self.assertEqual(len(results), 1)
            item = results[0]
            self.assertEqual(item.path_fields.artist, "Artist_Name")
            self.assertEqual(item.normalized_path_fields.artist, "artist name")
            self.assertEqual(item.path_fields.album, "Best-Hits")
            self.assertEqual(item.normalized_path_fields.album, "best hits")
            self.assertEqual(item.path_fields.song, "The_Best-Song")
            self.assertEqual(item.normalized_path_fields.song, "the best song")
            self.assertEqual(item.version_hints, [])

    def test_is_audio_file_respects_extension_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "song.mp3"
            art = root / "cover.jpg"
            audio.touch()
            art.touch()

            self.assertTrue(parser.is_audio_file(audio, extensions={".mp3"}))
            self.assertFalse(parser.is_audio_file(art, extensions={".mp3"}))


if __name__ == "__main__":
    unittest.main()

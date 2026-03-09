#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from trackloom.compare import compare_collections
from trackloom.parser import ParsedAudioFile, ParsedFields


def make_file(
    relative_path: str,
    artist: str,
    album: str,
    song: str,
    duration: float,
    extension: str = ".mp3",
) -> ParsedAudioFile:
    return ParsedAudioFile(
        root="/music",
        absolute_path="/music/" + relative_path,
        relative_path=relative_path,
        extension=extension or (Path(relative_path).suffix.lower() or ".mp3"),
        duration_seconds=duration,
        bitrate_kbps=None,
        sample_rate_hz=None,
        bit_depth=None,
        channels=None,
        codec=None,
        path_fields=ParsedFields(artist=artist, album=album, song=song),
        tag_fields=ParsedFields(None, None, None),
        normalized_path_fields=ParsedFields(artist=artist, album=album, song=song),
        normalized_tag_fields=ParsedFields(None, None, None),
        version_hints=[],
    )


def _has_candidate_with_paths(result: Dict, a_path: str, b_path: str) -> bool:
    for c in result.get("fuzzy_candidates", []):
        if c["file_a"]["relative_path"] == a_path and c["file_b"]["relative_path"] == b_path:
            return True
    return False


def _has_rejection_reason_for_paths(result: Dict, a_path: str, b_path: str, reason: str) -> bool:
    for r in result.get("fuzzy_rejections", []):
        if (
            r.get("file_a_relative_path") == a_path
            and r.get("file_b_relative_path") == b_path
            and reason in r.get("reasons", [])
        ):
            return True
    return False


def evaluate_config(
    fuzzy_threshold: float,
    min_song_similarity: float,
    min_artist_similarity: float,
    close_duration_seconds: float = 1.0,
    duration_conflict_seconds: float = 5.0,
) -> Tuple[int, int, Dict]:
    # Positive fuzzy candidate (should pass and become manual_review).
    pos_a = make_file(
        "A/Album/Believer.wav",
        "Imagine Dragons",
        "Evolve",
        "Believer",
        204.0,
        extension=".wav",
    )
    pos_b = make_file(
        "B/Album/Beliver.mp3",
        "Imagine Dragon",
        "Evolve",
        "Beliver",
        205.0,
        extension=".mp3",
    )

    # Negative candidate: similar text but duration conflict should reject.
    neg_a = make_file("A/Album/Natural.mp3", "Imagine Dragons", "Evolve", "Natural", 180.0)
    neg_b = make_file("B/Album/Naturl.mp3", "Imagine Dragon", "Evolve", "Naturl", 186.0)

    # Negative candidate: artist mismatch should reject.
    artist_a = make_file("A/Album/Thunder.mp3", "Imagine Dragons", "Evolve", "Thunder", 187.0)
    artist_b = make_file("B/Album/Thunder.mp3", "Totally Different", "Evolve", "Thunder", 187.2)

    result = compare_collections(
        [pos_a, neg_a, artist_a],
        [pos_b, neg_b, artist_b],
        fuzzy_threshold=fuzzy_threshold,
        min_song_similarity=min_song_similarity,
        min_artist_similarity=min_artist_similarity,
        close_duration_seconds=close_duration_seconds,
        duration_conflict_seconds=duration_conflict_seconds,
        top_k=20,
        max_rejections=50,
    )

    checks = [
        _has_candidate_with_paths(result, pos_a.relative_path, pos_b.relative_path),
        _has_rejection_reason_for_paths(
            result, neg_a.relative_path, neg_b.relative_path, "duration_conflict"
        ),
        _has_rejection_reason_for_paths(
            result, artist_a.relative_path, artist_b.relative_path, "artist_similarity_below_min"
        ),
    ]
    passed = sum(1 for x in checks if x)
    return passed, len(checks), result


def main() -> int:
    fuzzy_thresholds = [0.55, 0.60, 0.65, 0.70, 0.75]
    min_song_sims = [0.60, 0.70, 0.75, 0.80, 0.82]
    min_artist_sims = [0.55, 0.60, 0.65, 0.70]

    ranked: List[Tuple[int, int, float, float, float, Dict]] = []
    for ft in fuzzy_thresholds:
        for ms in min_song_sims:
            for ma in min_artist_sims:
                passed, total, result = evaluate_config(
                    fuzzy_threshold=ft,
                    min_song_similarity=ms,
                    min_artist_similarity=ma,
                )
                ranked.append((passed, total, ft, ms, ma, result))

    ranked.sort(key=lambda x: (x[0], -x[2]), reverse=True)
    best = ranked[:8]

    print("Synthetic threshold tuning (decision-boundary cases)")
    print("Top configurations:")
    for passed, total, ft, ms, ma, result in best:
        print(
            f"- pass={passed}/{total} "
            f"fuzzy_threshold={ft:.2f} min_song_sim={ms:.2f} min_artist_sim={ma:.2f} "
            f"(candidates={result['fuzzy_candidate_count']} rejections={result['fuzzy_rejection_count']})"
        )

    default = evaluate_config(
        fuzzy_threshold=0.75, min_song_similarity=0.82, min_artist_similarity=0.65
    )
    print(
        "\nCurrent defaults score: "
        f"{default[0]}/{default[1]} "
        "(fuzzy_threshold=0.75, min_song_sim=0.82, min_artist_sim=0.65)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

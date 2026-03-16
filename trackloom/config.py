# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompareConfig:
    fuzzy_threshold: float
    close_duration_seconds: float
    duration_conflict_seconds: float
    min_song_similarity: float
    min_artist_similarity: float
    top_k: int

    @classmethod
    def from_args(cls, args: Any) -> CompareConfig:
        return cls(
            fuzzy_threshold=float(args.fuzzy_threshold),
            close_duration_seconds=float(args.close_duration_seconds),
            duration_conflict_seconds=float(args.duration_conflict_seconds),
            min_song_similarity=float(args.min_song_sim),
            min_artist_similarity=float(args.min_artist_sim),
            top_k=int(args.top_k),
        )

    def validate(self) -> None:
        if self.fuzzy_threshold < 0 or self.fuzzy_threshold > 1:
            raise ValueError("--fuzzy-threshold must be between 0.0 and 1.0")
        if self.close_duration_seconds < 0:
            raise ValueError("--close-duration-seconds must be >= 0")
        if self.duration_conflict_seconds < 0:
            raise ValueError("--duration-conflict-seconds must be >= 0")
        if self.duration_conflict_seconds < self.close_duration_seconds:
            raise ValueError(
                "--duration-conflict-seconds must be >= --close-duration-seconds"
            )
        if self.min_song_similarity < 0 or self.min_song_similarity > 1:
            raise ValueError("--min-song-sim must be between 0.0 and 1.0")
        if self.min_artist_similarity < 0 or self.min_artist_similarity > 1:
            raise ValueError("--min-artist-sim must be between 0.0 and 1.0")
        if self.top_k < 0:
            raise ValueError("--top-k must be >= 0")

    def as_compare_kwargs(self) -> dict:
        return {
            "fuzzy_threshold": self.fuzzy_threshold,
            "close_duration_seconds": self.close_duration_seconds,
            "duration_conflict_seconds": self.duration_conflict_seconds,
            "min_song_similarity": self.min_song_similarity,
            "min_artist_similarity": self.min_artist_similarity,
            "top_k": self.top_k,
        }

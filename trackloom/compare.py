# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from .parser import ParsedAudioFile


def _choose_field(tag_value: Optional[str], path_value: Optional[str]) -> Optional[str]:
    return tag_value or path_value


def canonical_key(item: ParsedAudioFile) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    artist = _choose_field(
        item.normalized_tag_fields.artist, item.normalized_path_fields.artist
    )
    album = _choose_field(item.normalized_tag_fields.album, item.normalized_path_fields.album)
    song = _choose_field(item.normalized_tag_fields.song, item.normalized_path_fields.song)
    return (artist, album, song)


def _has_complete_key(key: Tuple[Optional[str], Optional[str], Optional[str]]) -> bool:
    return all(part is not None for part in key)


def _stable_item_sort_key(item: ParsedAudioFile) -> str:
    return (item.relative_path or "").casefold()


def _stable_key_sort_value(key: Tuple[Optional[str], Optional[str], Optional[str]]) -> Tuple[str, str, str]:
    return (
        (key[0] or "").casefold(),
        (key[1] or "").casefold(),
        (key[2] or "").casefold(),
    )


def _text_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _duration_score(
    duration_a: Optional[float],
    duration_b: Optional[float],
    close_duration_seconds: float,
    duration_conflict_seconds: float,
) -> Tuple[float, Optional[float]]:
    if duration_a is None or duration_b is None:
        return 0.5, None
    diff = abs(duration_a - duration_b)
    if close_duration_seconds <= 0:
        return (1.0 if diff == 0 else 0.0), diff
    if duration_conflict_seconds <= close_duration_seconds:
        duration_conflict_seconds = close_duration_seconds
    if diff >= duration_conflict_seconds:
        return 0.0, diff
    if diff <= close_duration_seconds:
        # Keep close durations high confidence (1.0 down to 0.5).
        return 1.0 - ((diff / close_duration_seconds) * 0.5), diff
    # Between close and conflict, taper from 0.5 to 0.0.
    span = duration_conflict_seconds - close_duration_seconds
    ratio = (diff - close_duration_seconds) / span if span > 0 else 1.0
    return 0.5 * max(0.0, 1.0 - ratio), diff


FORMAT_RANK = {
    ".wav": 6,
    ".aiff": 6,
    ".flac": 5,
    ".alac": 5,
    ".m4a": 4,
    ".aac": 3,
    ".ogg": 3,
    ".mp3": 2,
}
LOSSLESS_EXTENSIONS = {".wav", ".aiff", ".flac", ".alac"}


def _fidelity_score(item: ParsedAudioFile) -> float:
    score = float(FORMAT_RANK.get(item.extension.lower(), 1)) * 10000.0
    if item.bit_depth is not None:
        score += float(item.bit_depth) * 100.0
    if item.sample_rate_hz is not None:
        score += float(item.sample_rate_hz) / 100.0
    if item.bitrate_kbps is not None:
        score += float(item.bitrate_kbps)
    return score


def _is_lossless(item: ParsedAudioFile) -> bool:
    return item.extension.lower() in LOSSLESS_EXTENSIONS


def _pair_classification(
    file_a: ParsedAudioFile,
    file_b: ParsedAudioFile,
    duration_conflict_seconds: float,
) -> Tuple[str, Optional[float], List[str]]:
    reasons = []
    hints_a: Set[str] = set(file_a.version_hints)
    hints_b: Set[str] = set(file_b.version_hints)
    duration_diff = None
    if file_a.duration_seconds is not None and file_b.duration_seconds is not None:
        duration_diff = abs(file_a.duration_seconds - file_b.duration_seconds)

    if hints_a != hints_b and (hints_a or hints_b):
        reasons.append("version_hints_mismatch")
        return "version_conflict", duration_diff, reasons

    if duration_diff is not None and duration_diff >= duration_conflict_seconds:
        reasons.append("duration_diff_gt_conflict_threshold")
        return "duration_conflict", duration_diff, reasons

    if hints_a and hints_b and hints_a == hints_b:
        reasons.append("matching_version_hints")
    if duration_diff is not None and duration_diff <= 8.0:
        reasons.append("duration_close")
    return "likely_duplicate", duration_diff, reasons


def assess_duplicate_pair(
    file_a: ParsedAudioFile, file_b: ParsedAudioFile, duration_conflict_seconds: float = 5.0
) -> Dict[str, Any]:
    classification, duration_diff, reasons = _pair_classification(
        file_a, file_b, duration_conflict_seconds=duration_conflict_seconds
    )
    lossless_a = _is_lossless(file_a)
    lossless_b = _is_lossless(file_b)
    if lossless_a != lossless_b:
        # Hard boundary: lossless always wins over lossy.
        preferred = "a" if lossless_a else "b"
        reasons = reasons + ["lossless_vs_lossy_hard_boundary"]
        fidelity_a = _fidelity_score(file_a)
        fidelity_b = _fidelity_score(file_b)
    else:
        fidelity_a = _fidelity_score(file_a)
        fidelity_b = _fidelity_score(file_b)
        if abs(fidelity_a - fidelity_b) < 1e-9:
            preferred = "tie"
        elif fidelity_a > fidelity_b:
            preferred = "a"
        else:
            preferred = "b"

    return {
        "classification": classification,
        "duration_diff_seconds": duration_diff,
        "preferred_side": preferred,
        "fidelity_score_a": fidelity_a,
        "fidelity_score_b": fidelity_b,
        "reasons": reasons,
    }


def recommend_action_for_pair(duplicate_policy: Dict[str, Any]) -> str:
    classification = duplicate_policy.get("classification")
    preferred_side = duplicate_policy.get("preferred_side")

    if classification == "version_conflict":
        return "keep_both_versions"
    if classification == "duration_conflict":
        return "manual_review"
    if classification == "likely_duplicate":
        if preferred_side == "a":
            return "replace_in_b_with_a"
        return "keep_b"
    return "manual_review"


@dataclass
class FuzzyCandidate:
    score: float
    song_similarity: float
    artist_similarity: float
    duration_score: float
    duration_diff_seconds: Optional[float]
    duplicate_policy: Dict[str, Any]
    recommended_action: str
    file_a: ParsedAudioFile
    file_b: ParsedAudioFile

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "song_similarity": self.song_similarity,
            "artist_similarity": self.artist_similarity,
            "duration_score": self.duration_score,
            "duration_diff_seconds": self.duration_diff_seconds,
            "duplicate_policy": self.duplicate_policy,
            "recommended_action": self.recommended_action,
            "file_a": self.file_a.to_dict(),
            "file_b": self.file_b.to_dict(),
        }


def compare_collections(
    files_a: List[ParsedAudioFile],
    files_b: List[ParsedAudioFile],
    fuzzy_threshold: float = 0.75,
    close_duration_seconds: float = 1.0,
    duration_conflict_seconds: float = 5.0,
    min_song_similarity: float = 0.82,
    min_artist_similarity: float = 0.65,
    top_k: int = 3,
    max_rejections: int = 200,
) -> Dict[str, Any]:
    key_to_a: Dict[Tuple[Optional[str], Optional[str], Optional[str]], List[ParsedAudioFile]] = {}
    key_to_b: Dict[Tuple[Optional[str], Optional[str], Optional[str]], List[ParsedAudioFile]] = {}

    exact_matches = []
    action_counts = {
        "add_to_b": 0,
        "replace_in_b_with_a": 0,
        "keep_b": 0,
        "keep_both_versions": 0,
        "manual_review": 0,
    }
    duplicate_policy_counts = {
        "likely_duplicate": 0,
        "version_conflict": 0,
        "duration_conflict": 0,
    }
    only_in_a = []
    only_in_b = []
    unmatched_a: List[ParsedAudioFile] = []
    unmatched_b: List[ParsedAudioFile] = []

    for item in files_a:
        key = canonical_key(item)
        if _has_complete_key(key):
            key_to_a.setdefault(key, []).append(item)
        else:
            unmatched_a.append(item)
            action_counts["add_to_b"] += 1
            only_in_a.append(
                {
                    "recommended_action": "add_to_b",
                    "file": item.to_dict(),
                }
            )
    for item in files_b:
        key = canonical_key(item)
        if _has_complete_key(key):
            key_to_b.setdefault(key, []).append(item)
        else:
            unmatched_b.append(item)
            action_counts["keep_b"] += 1
            only_in_b.append(
                {
                    "recommended_action": "keep_b",
                    "file": item.to_dict(),
                }
            )

    all_keys = set(key_to_a.keys()) | set(key_to_b.keys())
    for key in sorted(all_keys, key=_stable_key_sort_value):
        a_items = sorted(key_to_a.get(key, []), key=_stable_item_sort_key)
        b_items = sorted(key_to_b.get(key, []), key=_stable_item_sort_key)
        paired = min(len(a_items), len(b_items))
        for idx in range(paired):
            duplicate_policy = assess_duplicate_pair(
                a_items[idx], b_items[idx], duration_conflict_seconds=duration_conflict_seconds
            )
            classification = duplicate_policy["classification"]
            if classification in duplicate_policy_counts:
                duplicate_policy_counts[classification] += 1
            recommended_action = recommend_action_for_pair(duplicate_policy)
            if recommended_action in action_counts:
                action_counts[recommended_action] += 1
            exact_matches.append(
                {
                    "key": {"artist": key[0], "album": key[1], "song": key[2]},
                    "duplicate_policy": duplicate_policy,
                    "recommended_action": recommended_action,
                    "file_a": a_items[idx].to_dict(),
                    "file_b": b_items[idx].to_dict(),
                }
            )
        if len(a_items) > paired:
            extras = a_items[paired:]
            unmatched_a.extend(extras)
            for item in extras:
                action_counts["add_to_b"] += 1
                only_in_a.append(
                    {
                        "recommended_action": "add_to_b",
                        "file": item.to_dict(),
                    }
                )
        if len(b_items) > paired:
            extras = b_items[paired:]
            unmatched_b.extend(extras)
            for item in extras:
                action_counts["keep_b"] += 1
                only_in_b.append(
                    {
                        "recommended_action": "keep_b",
                        "file": item.to_dict(),
                    }
                )

    fuzzy_candidates: List[FuzzyCandidate] = []
    fuzzy_rejections = []
    for item_a in unmatched_a:
        song_a = _choose_field(
            item_a.normalized_tag_fields.song, item_a.normalized_path_fields.song
        )
        artist_a = _choose_field(
            item_a.normalized_tag_fields.artist, item_a.normalized_path_fields.artist
        )
        for item_b in unmatched_b:
            song_b = _choose_field(
                item_b.normalized_tag_fields.song, item_b.normalized_path_fields.song
            )
            artist_b = _choose_field(
                item_b.normalized_tag_fields.artist, item_b.normalized_path_fields.artist
            )
            song_sim = _text_similarity(song_a, song_b)
            artist_sim = _text_similarity(artist_a, artist_b)
            duration_sim, duration_diff = _duration_score(
                item_a.duration_seconds,
                item_b.duration_seconds,
                close_duration_seconds,
                duration_conflict_seconds,
            )
            rejection_reasons = []
            if song_sim < min_song_similarity:
                rejection_reasons.append("song_similarity_below_min")
            if artist_sim < min_artist_similarity:
                rejection_reasons.append("artist_similarity_below_min")
            if duration_diff is not None and duration_diff > duration_conflict_seconds:
                rejection_reasons.append("duration_conflict")

            score = (song_sim * 0.5) + (duration_sim * 0.3) + (artist_sim * 0.2)
            if score < fuzzy_threshold:
                rejection_reasons.append("score_below_threshold")

            if rejection_reasons:
                if len(fuzzy_rejections) < max_rejections:
                    fuzzy_rejections.append(
                        {
                            "file_a_relative_path": item_a.relative_path,
                            "file_b_relative_path": item_b.relative_path,
                            "song_similarity": song_sim,
                            "artist_similarity": artist_sim,
                            "duration_score": duration_sim,
                            "duration_diff_seconds": duration_diff,
                            "score": score,
                            "reasons": rejection_reasons,
                        }
                    )
                continue

            if score >= fuzzy_threshold:
                duplicate_policy = assess_duplicate_pair(
                    item_a, item_b, duration_conflict_seconds=duration_conflict_seconds
                )
                # Fuzzy matches should be reviewed unless confidence rules are extended.
                recommended_action = "manual_review"
                fuzzy_candidates.append(
                    FuzzyCandidate(
                        score=score,
                        song_similarity=song_sim,
                        artist_similarity=artist_sim,
                        duration_score=duration_sim,
                        duration_diff_seconds=duration_diff,
                        duplicate_policy=duplicate_policy,
                        recommended_action=recommended_action,
                        file_a=item_a,
                        file_b=item_b,
                    )
                )

    fuzzy_candidates.sort(key=lambda c: c.score, reverse=True)
    if top_k > 0:
        fuzzy_candidates = fuzzy_candidates[:top_k]
    else:
        fuzzy_candidates = []
    # Keep action counts consistent with final candidate payload after top_k truncation.
    action_counts["manual_review"] += len(fuzzy_candidates)

    return {
        "count_a": len(files_a),
        "count_b": len(files_b),
        "exact_match_count": len(exact_matches),
        "only_in_a_count": len(only_in_a),
        "only_in_b_count": len(only_in_b),
        "fuzzy_candidate_count": len(fuzzy_candidates),
        "fuzzy_rejection_count": len(fuzzy_rejections),
        "duplicate_policy_counts": duplicate_policy_counts,
        "action_counts": action_counts,
        "exact_matches": exact_matches,
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "fuzzy_candidates": [candidate.to_dict() for candidate in fuzzy_candidates],
        "fuzzy_rejections": fuzzy_rejections,
    }

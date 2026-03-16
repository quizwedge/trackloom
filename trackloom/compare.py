# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rapidfuzz.fuzz import ratio as rapidfuzz_ratio

from .parser import ParsedAudioFile


def _choose_field(tag_value: str | None, path_value: str | None) -> str | None:
    return tag_value or path_value


def canonical_key(
    item: ParsedAudioFile,
) -> tuple[str | None, str | None, str | None]:
    artist = _choose_field(
        item.normalized_tag_fields.artist, item.normalized_path_fields.artist
    )
    album = _choose_field(
        item.normalized_tag_fields.album, item.normalized_path_fields.album
    )
    song = _choose_field(
        item.normalized_tag_fields.song, item.normalized_path_fields.song
    )
    return (artist, album, song)


def _has_complete_key(key: tuple[str | None, str | None, str | None]) -> bool:
    return all(part is not None for part in key)


def _stable_item_sort_key(item: ParsedAudioFile) -> str:
    return (item.relative_path or "").casefold()


def _stable_key_sort_value(
    key: tuple[str | None, str | None, str | None],
) -> tuple[str, str, str]:
    return (
        (key[0] or "").casefold(),
        (key[1] or "").casefold(),
        (key[2] or "").casefold(),
    )


def _text_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return rapidfuzz_ratio(a, b) / 100.0


BLOCK_ARTICLES = {"the", "a", "an"}


def _block_char(value: str | None) -> str:
    if not value:
        return ""
    tokens = value.split()
    if tokens and tokens[0] in BLOCK_ARTICLES and len(tokens) > 1:
        value = " ".join(tokens[1:])
    digit = ""
    for ch in value:
        if ch.isalpha():
            return ch
        if not digit and ch.isdigit():
            digit = ch
    return digit


def _blocking_keys(artist: str | None, song: str | None) -> list[tuple[str, str]]:
    artist_key = _block_char(artist)
    song_key = _block_char(song)
    keys: list[tuple[str, str]] = []
    if artist_key and song_key:
        keys.append((artist_key, song_key))
    if artist_key:
        keys.append((artist_key, ""))
    if song_key:
        keys.append(("", song_key))
    if not keys:
        keys.append(("", ""))
    return keys


def _version_signature(item: ParsedAudioFile) -> tuple[str, ...]:
    return tuple(item.version_hints or [])


def _pair_by_duration(
    a_items: list[ParsedAudioFile],
    b_items: list[ParsedAudioFile],
) -> tuple[
    list[tuple[ParsedAudioFile, ParsedAudioFile]],
    list[ParsedAudioFile],
    list[ParsedAudioFile],
]:
    pairs: list[tuple[ParsedAudioFile, ParsedAudioFile]] = []
    remaining_b = sorted(b_items, key=_stable_item_sort_key)
    remaining_a = sorted(a_items, key=_stable_item_sort_key)
    leftover_a: list[ParsedAudioFile] = []

    for item_a in remaining_a:
        if not remaining_b:
            leftover_a.append(item_a)
            continue
        best_idx = None
        best_key = None
        for idx, item_b in enumerate(remaining_b):
            if item_a.duration_seconds is None or item_b.duration_seconds is None:
                metric = float("inf")
            else:
                metric = abs(item_a.duration_seconds - item_b.duration_seconds)
            key = (metric, _stable_item_sort_key(item_b))
            if best_key is None or key < best_key:
                best_key = key
                best_idx = idx
        if best_idx is None:
            leftover_a.append(item_a)
            continue
        pairs.append((item_a, remaining_b.pop(best_idx)))

    return pairs, leftover_a, remaining_b


def _pair_exact_candidates(
    a_items: list[ParsedAudioFile],
    b_items: list[ParsedAudioFile],
) -> tuple[
    list[tuple[ParsedAudioFile, ParsedAudioFile]],
    list[ParsedAudioFile],
    list[ParsedAudioFile],
]:
    pairs: list[tuple[ParsedAudioFile, ParsedAudioFile]] = []
    remaining_a: list[ParsedAudioFile] = []
    remaining_b: list[ParsedAudioFile] = []

    a_groups: dict[tuple[str, ...], list[ParsedAudioFile]] = {}
    b_groups: dict[tuple[str, ...], list[ParsedAudioFile]] = {}
    for item in a_items:
        a_groups.setdefault(_version_signature(item), []).append(item)
    for item in b_items:
        b_groups.setdefault(_version_signature(item), []).append(item)

    shared_signatures = sorted(set(a_groups.keys()) & set(b_groups.keys()))
    for signature in shared_signatures:
        group_a = sorted(a_groups[signature], key=_stable_item_sort_key)
        group_b = sorted(b_groups[signature], key=_stable_item_sort_key)
        paired = min(len(group_a), len(group_b))
        for idx in range(paired):
            pairs.append((group_a[idx], group_b[idx]))
        if len(group_a) > paired:
            remaining_a.extend(group_a[paired:])
        if len(group_b) > paired:
            remaining_b.extend(group_b[paired:])

    for signature in sorted(set(a_groups.keys()) - set(shared_signatures)):
        remaining_a.extend(sorted(a_groups[signature], key=_stable_item_sort_key))
    for signature in sorted(set(b_groups.keys()) - set(shared_signatures)):
        remaining_b.extend(sorted(b_groups[signature], key=_stable_item_sort_key))

    duration_pairs, leftover_a, leftover_b = _pair_by_duration(remaining_a, remaining_b)
    pairs.extend(duration_pairs)
    return pairs, leftover_a, leftover_b


def _duration_score(
    duration_a: float | None,
    duration_b: float | None,
    close_duration_seconds: float,
    duration_conflict_seconds: float,
) -> tuple[float, float | None]:
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
) -> tuple[str, float | None, list[str]]:
    reasons = []
    hints_a: set[str] = set(file_a.version_hints)
    hints_b: set[str] = set(file_b.version_hints)
    duration_diff: float | None = None
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
    file_a: ParsedAudioFile,
    file_b: ParsedAudioFile,
    duration_conflict_seconds: float = 5.0,
) -> dict[str, Any]:
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


def recommend_action_for_pair(duplicate_policy: dict[str, Any]) -> str:
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
    duration_diff_seconds: float | None
    duplicate_policy: dict[str, Any]
    recommended_action: str
    file_a: ParsedAudioFile
    file_b: ParsedAudioFile

    def to_dict(self) -> dict[str, Any]:
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
    files_a: list[ParsedAudioFile],
    files_b: list[ParsedAudioFile],
    fuzzy_threshold: float = 0.75,
    close_duration_seconds: float = 1.0,
    duration_conflict_seconds: float = 5.0,
    min_song_similarity: float = 0.82,
    min_artist_similarity: float = 0.65,
    top_k: int = 3,
    max_rejections: int = 200,
) -> dict[str, Any]:
    key_to_a: dict[
        tuple[str | None, str | None, str | None], list[ParsedAudioFile]
    ] = {}
    key_to_b: dict[
        tuple[str | None, str | None, str | None], list[ParsedAudioFile]
    ] = {}

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
    unmatched_a: list[ParsedAudioFile] = []
    unmatched_b: list[ParsedAudioFile] = []

    for item in files_a:
        key = canonical_key(item)
        if _has_complete_key(key):
            key_to_a.setdefault(key, []).append(item)
        else:
            unmatched_a.append(item)
    for item in files_b:
        key = canonical_key(item)
        if _has_complete_key(key):
            key_to_b.setdefault(key, []).append(item)
        else:
            unmatched_b.append(item)

    all_keys = set(key_to_a.keys()) | set(key_to_b.keys())
    for key in sorted(all_keys, key=_stable_key_sort_value):
        a_items = sorted(key_to_a.get(key, []), key=_stable_item_sort_key)
        b_items = sorted(key_to_b.get(key, []), key=_stable_item_sort_key)
        pairs, extras_a, extras_b = _pair_exact_candidates(a_items, b_items)
        for item_a, item_b in pairs:
            duplicate_policy = assess_duplicate_pair(
                item_a, item_b, duration_conflict_seconds=duration_conflict_seconds
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
                    "file_a": item_a.to_dict(),
                    "file_b": item_b.to_dict(),
                }
            )
        if extras_a:
            unmatched_a.extend(extras_a)
        if extras_b:
            unmatched_b.extend(extras_b)

    fuzzy_candidates_all: list[FuzzyCandidate] = []
    fuzzy_rejections = []
    block_index: dict[tuple[str, str], list[ParsedAudioFile]] = {}
    for item_b in unmatched_b:
        song_b = _choose_field(
            item_b.normalized_tag_fields.song, item_b.normalized_path_fields.song
        )
        artist_b = _choose_field(
            item_b.normalized_tag_fields.artist, item_b.normalized_path_fields.artist
        )
        for key in _blocking_keys(artist_b, song_b):
            block_index.setdefault(key, []).append(item_b)

    for item_a in unmatched_a:
        song_a = _choose_field(
            item_a.normalized_tag_fields.song, item_a.normalized_path_fields.song
        )
        artist_a = _choose_field(
            item_a.normalized_tag_fields.artist, item_a.normalized_path_fields.artist
        )
        keys = _blocking_keys(artist_a, song_a)
        if keys == [("", "")]:
            candidates = unmatched_b
        else:
            seen: set[str] = set()
            candidates = []
            for key in keys:
                for item_b in block_index.get(key, []):
                    if item_b.absolute_path in seen:
                        continue
                    seen.add(item_b.absolute_path)
                    candidates.append(item_b)

        for item_b in candidates:
            song_b = _choose_field(
                item_b.normalized_tag_fields.song, item_b.normalized_path_fields.song
            )
            artist_b = _choose_field(
                item_b.normalized_tag_fields.artist,
                item_b.normalized_path_fields.artist,
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
                fuzzy_candidates_all.append(
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

    fuzzy_candidates_all.sort(key=lambda c: c.score, reverse=True)
    fuzzy_candidates = fuzzy_candidates_all[:top_k] if top_k > 0 else []
    fuzzy_dropped_count = max(0, len(fuzzy_candidates_all) - len(fuzzy_candidates))

    fuzzy_a_ids = {candidate.file_a.absolute_path for candidate in fuzzy_candidates_all}
    fuzzy_b_ids = {candidate.file_b.absolute_path for candidate in fuzzy_candidates_all}

    for item in unmatched_a:
        if item.absolute_path in fuzzy_a_ids:
            continue
        only_in_a.append(
            {
                "recommended_action": "add_to_b",
                "file": item.to_dict(),
            }
        )
        action_counts["add_to_b"] += 1

    for item in unmatched_b:
        if item.absolute_path in fuzzy_b_ids:
            continue
        only_in_b.append(
            {
                "recommended_action": "keep_b",
                "file": item.to_dict(),
            }
        )
        action_counts["keep_b"] += 1

    # Keep action counts consistent with final candidate payload after top_k truncation.
    action_counts["manual_review"] += len(fuzzy_candidates)

    return {
        "count_a": len(files_a),
        "count_b": len(files_b),
        "exact_match_count": len(exact_matches),
        "only_in_a_count": len(only_in_a),
        "only_in_b_count": len(only_in_b),
        "fuzzy_candidate_count": len(fuzzy_candidates),
        "fuzzy_dropped_count": fuzzy_dropped_count,
        "fuzzy_rejection_count": len(fuzzy_rejections),
        "duplicate_policy_counts": duplicate_policy_counts,
        "action_counts": action_counts,
        "exact_matches": exact_matches,
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "fuzzy_candidates": [candidate.to_dict() for candidate in fuzzy_candidates],
        "fuzzy_rejections": fuzzy_rejections,
    }

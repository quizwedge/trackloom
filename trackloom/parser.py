# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Dan Getz, Jr.
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from mutagen import File as MutagenFile
except ImportError:  # pragma: no cover - runtime fallback for missing optional dep
    MutagenFile = None


SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac"}

TRACK_PREFIX_RE = re.compile(
    r"^\s*(?:cd\s*\d+\s*[-_. ]\s*)?(?:track\s*)?0*(\d{1,3})\s*[-_. )]+\s*(.+)$",
    re.IGNORECASE,
)
AMPERSAND_RE = re.compile(r"&")
SEPARATOR_RE = re.compile(r"[_\-]+")
PUNCTUATION_RE = re.compile(r"[^\w\s]+", re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")
REMASTER_YEAR_AFTER_RE = re.compile(r"remaster(?:ed)?[^\d]{0,6}(\d{4})", re.IGNORECASE)
REMASTER_YEAR_BEFORE_RE = re.compile(r"(\d{4})[^\w]{0,3}remaster(?:ed)?", re.IGNORECASE)


@dataclass
class ParsedFields:
    artist: str | None
    album: str | None
    song: str | None


@dataclass
class ParsedAudioFile:
    root: str
    absolute_path: str
    relative_path: str
    extension: str
    duration_seconds: float | None
    bitrate_kbps: int | None
    sample_rate_hz: int | None
    bit_depth: int | None
    channels: int | None
    codec: str | None
    path_fields: ParsedFields
    tag_fields: ParsedFields
    normalized_path_fields: ParsedFields
    normalized_tag_fields: ParsedFields
    version_hints: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_song_from_stem(stem: str) -> str | None:
    value = _clean(stem)
    if value is None:
        return None

    match = TRACK_PREFIX_RE.match(value)
    if match:
        value = match.group(2).strip()

    return _clean(value)


def normalize_for_match(value: str | None) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    cleaned = AMPERSAND_RE.sub(" and ", cleaned)
    cleaned = cleaned.casefold()
    cleaned = PUNCTUATION_RE.sub(" ", cleaned)
    cleaned = SEPARATOR_RE.sub(" ", cleaned)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned or None


def normalize_fields_for_match(fields: ParsedFields) -> ParsedFields:
    return ParsedFields(
        artist=normalize_for_match(fields.artist),
        album=normalize_for_match(fields.album),
        song=normalize_for_match(fields.song),
    )


def parse_fields_from_path(file_path: Path, root_dir: Path) -> ParsedFields:
    rel = file_path.relative_to(root_dir)
    parts = list(rel.parts)
    if not parts:
        return ParsedFields(None, None, None)

    song = normalize_song_from_stem(file_path.stem)
    artist = None
    album = None

    # Common shape: Artist/Album/Track.ext
    if len(parts) >= 3:
        artist = parts[-3]
        album = parts[-2]
    elif len(parts) == 2:
        album = parts[-2]

    return ParsedFields(_clean(artist), _clean(album), _clean(song))


def parse_fields_from_tags(file_path: Path) -> ParsedFields:
    audio = _load_audio(file_path)
    return _parse_fields_from_audio(audio)


def _load_audio(file_path: Path) -> Any:
    if MutagenFile is None:
        return None

    try:
        return MutagenFile(file_path)
    except Exception:
        return None


def _parse_fields_from_audio(audio: Any) -> ParsedFields:
    if audio is None:
        return ParsedFields(None, None, None)

    tags = getattr(audio, "tags", None)
    if not tags:
        return ParsedFields(None, None, None)

    # Try common key families across ID3, MP4, Vorbis.
    artist = (
        tags.get("artist")
        or tags.get("TPE1")
        or tags.get("\xa9ART")
        or tags.get("albumartist")
        or tags.get("TPE2")
    )
    album = tags.get("album") or tags.get("TALB") or tags.get("\xa9alb")
    song = tags.get("title") or tags.get("TIT2") or tags.get("\xa9nam")

    return ParsedFields(_clean(artist), _clean(album), _clean(song))


def parse_duration_seconds(file_path: Path) -> float | None:
    audio = _load_audio(file_path)
    return _parse_duration_from_audio(audio)


def _parse_duration_from_audio(audio: Any) -> float | None:
    if audio is None:
        return None
    info = getattr(audio, "info", None)
    if info is None:
        return None
    length = getattr(info, "length", None)
    if length is None:
        return None
    try:
        return float(length)
    except (TypeError, ValueError):
        return None


def parse_audio_quality(file_path: Path) -> dict[str, Any | None]:
    audio = _load_audio(file_path)
    return _parse_quality_from_audio(audio)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_quality_from_audio(audio: Any) -> dict[str, Any | None]:
    if audio is None:
        return {
            "bitrate_kbps": None,
            "sample_rate_hz": None,
            "bit_depth": None,
            "channels": None,
            "codec": None,
        }
    info = getattr(audio, "info", None)
    if info is None:
        return {
            "bitrate_kbps": None,
            "sample_rate_hz": None,
            "bit_depth": None,
            "channels": None,
            "codec": None,
        }

    bitrate = _to_int(getattr(info, "bitrate", None))
    bitrate_kbps = int(round(bitrate / 1000)) if bitrate else None
    sample_rate_hz = _to_int(getattr(info, "sample_rate", None))
    bit_depth = _to_int(getattr(info, "bits_per_sample", None))
    channels = _to_int(getattr(info, "channels", None))

    codec = None
    codec_attr = getattr(info, "codec", None)
    if codec_attr:
        codec = _clean(codec_attr)
    else:
        codec = _clean(getattr(info, "codec_description", None))

    return {
        "bitrate_kbps": bitrate_kbps,
        "sample_rate_hz": sample_rate_hz,
        "bit_depth": bit_depth,
        "channels": channels,
        "codec": codec,
    }


def classify_version_hints(
    song_from_path: str | None, song_from_tag: str | None
) -> list[str]:
    text_parts = [part for part in [song_from_tag, song_from_path] if part]
    if not text_parts:
        return []
    text = " ".join(text_parts).lower()

    hints: list[str] = []

    if "live" in text:
        hints.append("live")
    if "remaster" in text or "remastered" in text:
        hints.append("remaster")
        years = set(REMASTER_YEAR_AFTER_RE.findall(text)) | set(
            REMASTER_YEAR_BEFORE_RE.findall(text)
        )
        for year in sorted(years):
            hints.append("remaster_year_" + year)
    if "radio edit" in text or text.endswith(" edit") or "(edit)" in text:
        hints.append("radio_edit")
    if "acoustic" in text:
        hints.append("acoustic")
    if "instrumental" in text:
        hints.append("instrumental")
    if "karaoke" in text:
        hints.append("karaoke")
    if "mono" in text:
        hints.append("mono")
    if "stereo" in text:
        hints.append("stereo")
    if "clean" in text:
        hints.append("clean")
    if "explicit" in text:
        hints.append("explicit")

    # De-duplicate while keeping stable order.
    seen = set()
    ordered = []
    for hint in hints:
        if hint in seen:
            continue
        seen.add(hint)
        ordered.append(hint)
    return ordered


def is_audio_file(path: Path, extensions: set[str] | None = None) -> bool:
    allowed = extensions if extensions is not None else SUPPORTED_EXTENSIONS
    return path.is_file() and path.suffix.lower() in allowed


def collect_audio_metadata(
    root_dir: Path,
    extensions: set[str] | None = None,
    progress_callback: Callable[[int, int, Path], None] | None = None,
) -> list[ParsedAudioFile]:
    if not root_dir.exists():
        raise FileNotFoundError(f"Directory does not exist: {root_dir}")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {root_dir}")

    allowed = {ext.lower() for ext in (extensions or SUPPORTED_EXTENSIONS)}
    # Performance optimization for large trees: filter by extension during os.walk
    # instead of creating Path objects for every filesystem entry.
    candidates: list[Path] = []
    for dirpath, _, filenames in os.walk(root_dir):
        base = Path(dirpath)
        for name in filenames:
            if Path(name).suffix.lower() not in allowed:
                continue
            candidates.append(base / name)
    total = len(candidates)
    files: list[ParsedAudioFile] = []
    for idx, path in enumerate(candidates, start=1):
        path_fields = parse_fields_from_path(path, root_dir)
        audio = _load_audio(path)
        tag_fields = _parse_fields_from_audio(audio)
        duration_seconds = _parse_duration_from_audio(audio)
        quality = _parse_quality_from_audio(audio)
        version_hints = classify_version_hints(
            song_from_path=path_fields.song, song_from_tag=tag_fields.song
        )
        files.append(
            ParsedAudioFile(
                root=str(root_dir),
                absolute_path=str(path.resolve()),
                relative_path=str(path.relative_to(root_dir)),
                extension=path.suffix.lower(),
                duration_seconds=duration_seconds,
                bitrate_kbps=quality["bitrate_kbps"],
                sample_rate_hz=quality["sample_rate_hz"],
                bit_depth=quality["bit_depth"],
                channels=quality["channels"],
                codec=quality["codec"],
                path_fields=path_fields,
                tag_fields=tag_fields,
                normalized_path_fields=normalize_fields_for_match(path_fields),
                normalized_tag_fields=normalize_fields_for_match(tag_fields),
                version_hints=version_hints,
            )
        )
        if progress_callback is not None:
            progress_callback(idx, total, path)
    return files

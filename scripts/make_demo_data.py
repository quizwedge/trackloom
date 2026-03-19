#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Built by Dan Getz, Jr.
from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import wave
from pathlib import Path

try:
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, TALB, TIT2, TPE1
    from mutagen.mp4 import MP4
except Exception:  # pragma: no cover
    FLAC = None
    ID3 = None
    TIT2 = None
    TALB = None
    TPE1 = None
    MP4 = None


def _write_tone_wav(path: Path, duration_s: float, freq_hz: float = 440.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    amplitude = 12000
    n_samples = max(1, int(duration_s * sample_rate))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            value = int(amplitude * math.sin(2.0 * math.pi * freq_hz * t))
            # stereo: L, R
            frames.extend(value.to_bytes(2, byteorder="little", signed=True))
            frames.extend(value.to_bytes(2, byteorder="little", signed=True))
        w.writeframes(bytes(frames))


def _write_dummy(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _run(cmd: list[str]) -> bool:
    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        return False


def _convert_with_ffmpeg(src_wav: Path, dst_audio: Path) -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    dst_audio.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(src_wav)]
    suffix = dst_audio.suffix.lower()
    if suffix == ".mp3":
        cmd += ["-codec:a", "libmp3lame", "-b:a", "192k"]
    elif suffix == ".m4a":
        cmd += ["-codec:a", "aac", "-b:a", "192k"]
    elif suffix == ".flac":
        cmd += ["-codec:a", "flac"]
    else:
        return False
    cmd += [str(dst_audio)]
    return _run(cmd)


def _tag_mp3(path: Path, artist: str, album: str, title: str) -> bool:
    if ID3 is None or TIT2 is None or TALB is None or TPE1 is None:
        return False
    try:
        tags = ID3(path)
    except Exception:
        tags = ID3()
    tags.delall("TPE1")
    tags.delall("TALB")
    tags.delall("TIT2")
    tags.add(TPE1(encoding=3, text=artist))
    tags.add(TALB(encoding=3, text=album))
    tags.add(TIT2(encoding=3, text=title))
    tags.save(path, v2_version=3)
    return True


def _tag_m4a(path: Path, artist: str, album: str, title: str) -> bool:
    if MP4 is None:
        return False
    try:
        audio = MP4(path)
        audio["\xa9ART"] = [artist]
        audio["\xa9alb"] = [album]
        audio["\xa9nam"] = [title]
        audio.save()
        return True
    except Exception:
        return False


def _tag_flac(path: Path, artist: str, album: str, title: str) -> bool:
    if FLAC is None:
        return False
    try:
        audio = FLAC(path)
        audio["artist"] = [artist]
        audio["album"] = [album]
        audio["title"] = [title]
        audio.save()
        return True
    except Exception:
        return False


def _make_tagged_fixture(
    root: Path,
    relative_audio_path: str,
    title: str,
    album: str,
    artist: str,
    source_wav: Path,
) -> tuple[bool, str]:
    out = root / relative_audio_path
    out.parent.mkdir(parents=True, exist_ok=True)
    if not _convert_with_ffmpeg(source_wav, out):
        return False, f"skip: encoder unavailable for {out.suffix} (install ffmpeg)"

    suffix = out.suffix.lower()
    tagged = False
    if suffix == ".mp3":
        tagged = _tag_mp3(out, artist=artist, album=album, title=title)
    elif suffix == ".m4a":
        tagged = _tag_m4a(out, artist=artist, album=album, title=title)
    elif suffix == ".flac":
        tagged = _tag_flac(out, artist=artist, album=album, title=title)

    if not tagged:
        return False, f"skip: could not tag {out.name}"
    return True, f"ok: tagged {out.name}"


def build_demo_tree(base: Path, force: bool) -> None:
    if base.exists():
        if not force:
            raise FileExistsError(
                f"Refusing to overwrite existing demo directory: {base}. "
                "Use --force to replace it."
            )
        shutil.rmtree(base)

    a = base / "A"
    b = base / "B"

    # Exact path-based match after normalization / track-prefix stripping.
    _write_tone_wav(
        a / "The_Artist" / "First Album" / "01 - Summer-Night.wav", duration_s=2.00
    )
    _write_tone_wav(
        b / "The Artist" / "First Album" / "Summer Night.wav", duration_s=2.00
    )

    # Version conflict candidate (live vs studio naming hint).
    _write_tone_wav(
        a / "The Artist" / "Live Cuts" / "03 - Sky Song (Live).wav", duration_s=2.20
    )
    _write_tone_wav(b / "The Artist" / "Studio Cuts" / "Sky Song.wav", duration_s=2.20)

    # Replace preference candidate (A higher sample rate/bit depth than B).
    _write_tone_wav(a / "Duo" / "Numbers" / "02 - Counting Stars.wav", duration_s=2.10)
    _write_tone_wav(b / "Duo" / "Numbers" / "Counting Stars.wav", duration_s=2.35)

    # Track present only in A -> add_to_b.
    _write_tone_wav(a / "Newcomer" / "Debut" / "01 - Fresh Start.wav", duration_s=1.80)

    # Protected file for Plex-mode skip demo.
    _write_dummy(
        a / "Protected Artist" / "Locked Album" / "01 - Locked Song.m4p",
        b"demo protected file placeholder",
    )

    # Tagged format fixtures for tag parsing behavior.
    tagged_source_wav = base / "_sources" / "tagged_source.wav"
    _write_tone_wav(tagged_source_wav, duration_s=2.40, freq_hz=523.25)
    tagged_results: list[str] = []

    fixtures = [
        (
            a,
            "TagPath Artist/TagPath Album/01 - Path Name Only.mp3",
            "Tag Title MP3",
            "Tag Album",
            "Tag Artist",
        ),
        (
            a,
            "TagPath Artist/TagPath Album/02 - Path Name Only.m4a",
            "Tag Title M4A",
            "Tag Album",
            "Tag Artist",
        ),
        (
            a,
            "TagPath Artist/TagPath Album/03 - Path Name Only.flac",
            "Tag Title FLAC",
            "Tag Album",
            "Tag Artist",
        ),
    ]
    for root, rel, title, album, artist in fixtures:
        ok, msg = _make_tagged_fixture(
            root=root,
            relative_audio_path=rel,
            title=title,
            album=album,
            artist=artist,
            source_wav=tagged_source_wav,
        )
        tagged_results.append(msg)

    shutil.rmtree(base / "_sources", ignore_errors=True)

    print(f"Demo libraries created at: {base}")
    print(f"  A: {a}")
    print(f"  B: {b}")
    if tagged_results:
        print("Tagged fixtures:")
        for line in tagged_results:
            print(f"  - {line}")
    print("Try:")
    print(f"  trackloom compare {a} {b} --json")
    print(f"  trackloom parse {a} --extensions .wav .mp3 .m4a .flac .m4p --json")
    print(
        "  trackloom plan "
        f"{a} {b} --mode plex --extensions .wav .mp3 .m4a .flac .m4p --json"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Trackloom demo libraries.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("demo_data"),
        help="Destination directory for demo trees (default: ./demo_data)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output directory if it exists.",
    )
    args = parser.parse_args()
    build_demo_tree(args.output, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

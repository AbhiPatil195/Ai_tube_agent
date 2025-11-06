from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .transcribe import Transcript, Segment
from .paths import TRANSCRIPTS


def _fmt_timestamp_srt(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_timestamp_vtt(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def save_srt(t: Transcript, video_stem: str, output_dir: Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else TRANSCRIPTS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{video_stem}.srt"
    lines = []
    for i, seg in enumerate(t.segments, 1):
        start = _fmt_timestamp_srt(seg.start)
        end = _fmt_timestamp_srt(seg.end)
        text = seg.text.strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def save_vtt(t: Transcript, video_stem: str, output_dir: Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else TRANSCRIPTS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{video_stem}.vtt"
    lines = ["WEBVTT", ""]
    for seg in t.segments:
        start = _fmt_timestamp_vtt(seg.start)
        end = _fmt_timestamp_vtt(seg.end)
        text = seg.text.strip()
        if not text:
            continue
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


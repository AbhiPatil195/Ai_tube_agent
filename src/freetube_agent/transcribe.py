from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from faster_whisper import WhisperModel

from .paths import TRANSCRIPTS


@dataclass
class Word:
    start: float
    end: float
    word: str


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] | None = None


@dataclass
class Transcript:
    text: str
    segments: List[Segment]
    path: Path | None = None


def transcribe(
    audio_path: str | Path,
    model_size: str = "base",
    device: Optional[str] = None,
    compute_type: Optional[str] = None,
    beam_size: int = 1,
    language: Optional[str] = "en",
    vad_filter: bool = False,
    word_timestamps: bool = False,
    condition_on_previous_text: bool = False,
    temperature: float = 0.0,
    cpu_threads: Optional[int] = 0,
    num_workers: int = 1,
    model_path: Optional[str | Path] = None,
) -> Transcript:
    """Transcribe audio using Faster-Whisper with CPU-friendly defaults.

    Tips for speed on CPU:
    - use compute_type="int8" (quantized)
    - set beam_size=1
    - prefer smaller models ("tiny" or "base")
    - optionally enable vad_filter on long audios with lots of silence
    """
    apath = Path(audio_path)
    device_ = device or ("cuda" if _has_cuda() else "cpu")
    # Choose compute_type default based on device
    ct = compute_type
    if ct is None:
        ct = "float16" if device_ == "cuda" else "int8"

    # Ensure integer for cpu_threads; None is invalid for ctranslate2
    cpu_threads_int = int(cpu_threads) if cpu_threads is not None else 0

    model_arg = str(model_path) if model_path else model_size
    model = WhisperModel(
        model_arg,
        device=device_,
        compute_type=ct,
        cpu_threads=cpu_threads_int,
        num_workers=num_workers,
    )

    segments, info = model.transcribe(
        str(apath),
        language=language,
        task="transcribe",
        vad_filter=vad_filter,
        beam_size=beam_size,
        best_of=max(1, beam_size),
        word_timestamps=word_timestamps,
        condition_on_previous_text=condition_on_previous_text,
        temperature=temperature,
    )
    segs: List[Segment] = []
    lines: List[str] = []
    for s in segments:
        ws = None
        try:
            if getattr(s, "words", None):
                ws = [Word(start=w.start, end=w.end, word=w.word) for w in s.words if getattr(w, "word", "").strip()]
        except Exception:
            ws = None
        text = s.text.strip()
        segs.append(Segment(start=s.start, end=s.end, text=text, words=ws))
        if text:
            lines.append(text)
    full = "\n".join(lines).strip()
    return Transcript(text=full, segments=segs)


def save_transcript(t: Transcript, video_stem: str, output_dir: Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else TRANSCRIPTS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{video_stem}.txt"
    path.write_text(t.text, encoding="utf-8")
    t.path = path
    return path


def _has_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False

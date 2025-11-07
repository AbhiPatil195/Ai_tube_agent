from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from faster_whisper import WhisperModel

from .paths import TRANSCRIPTS
from .logger import logger, error_tracker, perf_logger


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
    import time
    start_time = time.time()
    
    apath = Path(audio_path)
    logger.info(f"Starting transcription: {apath.name} (model={model_size}, device={device or 'auto'})")
    
    device_ = device or ("cuda" if _has_cuda() else "cpu")
    # Choose compute_type default based on device
    ct = compute_type
    if ct is None:
        ct = "float16" if device_ == "cuda" else "int8"
    
    logger.debug(f"Using device={device_}, compute_type={ct}, beam_size={beam_size}")

    # Ensure integer for cpu_threads; None is invalid for ctranslate2
    cpu_threads_int = int(cpu_threads) if cpu_threads is not None else 0

    model_arg = str(model_path) if model_path else model_size
    
    try:
        logger.debug(f"Loading Whisper model: {model_arg}")
        model = WhisperModel(
            model_arg,
            device=device_,
            compute_type=ct,
            cpu_threads=cpu_threads_int,
            num_workers=num_workers,
        )
        logger.info("Whisper model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        error_tracker.log_error(e, context=f"Loading model {model_arg}", module="transcribe", function="transcribe")
        raise

    try:
        logger.info("Starting transcription process...")
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
        logger.debug(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        error_tracker.log_error(e, context="Whisper transcription", module="transcribe", function="transcribe")
        raise
    segs: List[Segment] = []
    lines: List[str] = []
    segment_count = 0
    
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
        segment_count += 1
    
    full = "\n".join(lines).strip()
    word_count = len(full.split())
    duration = time.time() - start_time
    
    logger.info(f"Transcription complete: {segment_count} segments, {word_count} words in {duration:.1f}s")
    perf_logger.log_metric("transcribe", duration, True, {"segments": segment_count, "words": word_count, "model": model_size})
    
    return Transcript(text=full, segments=segs)


def save_transcript(t: Transcript, video_stem: str, output_dir: Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir else TRANSCRIPTS
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{video_stem}.txt"
    
    try:
        path.write_text(t.text, encoding="utf-8")
        t.path = path
        logger.info(f"Transcript saved: {path}")
        return path
    except Exception as e:
        logger.error(f"Failed to save transcript: {e}")
        error_tracker.log_error(e, context=f"Saving transcript to {path}", module="transcribe", function="save_transcript")
        raise


def _has_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False

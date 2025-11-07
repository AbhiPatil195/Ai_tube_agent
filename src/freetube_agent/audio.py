from pathlib import Path
import os
import subprocess
import shutil
import time
import ffmpeg

from .paths import AUDIO
from .logger import logger, error_tracker, retry, perf_logger


@retry(max_attempts=2, delay=1.0)
def extract_audio(video_path: str | Path, output_path: str | Path | None = None) -> Path:
    """
    Extract audio as WAV (16kHz mono) from a video.
    Prefers ffmpeg-python with system ffmpeg; falls back to imageio-ffmpeg binary.
    """
    start_time = time.time()
    
    vpath = Path(video_path)
    logger.info(f"Extracting audio from: {vpath.name}")
    
    if output_path is None:
        out = AUDIO / (vpath.stem + ".wav")
    else:
        out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if _has_ffmpeg_on_path():
        try:
            logger.debug("Using system ffmpeg for audio extraction")
            (
                ffmpeg
                .input(str(vpath))
                .output(str(out), acodec="pcm_s16le", ac=1, ar="16000")
                .overwrite_output()
                .run(quiet=True)
            )
            duration = time.time() - start_time
            logger.info(f"Audio extracted successfully (ffmpeg): {out.name} in {duration:.1f}s")
            perf_logger.log_metric("extract_audio", duration, True, {"method": "system_ffmpeg"})
            return out
        except Exception as e:
            logger.warning(f"System ffmpeg failed: {e}, trying bundled ffmpeg")
            error_tracker.log_error(e, context="System ffmpeg extraction", module="audio", function="extract_audio")

    # Fallback: use bundled imageio-ffmpeg executable
    try:
        logger.debug("Using bundled imageio-ffmpeg for audio extraction")
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        logger.error("FFmpeg not available. Install system FFmpeg or imageio-ffmpeg.")
        error_tracker.log_error(e, context="FFmpeg not available", module="audio", function="extract_audio")
        raise RuntimeError("FFmpeg not available. Install system FFmpeg or imageio-ffmpeg.") from e

    try:
        cmd = [
            exe,
            "-y",
            "-i",
            str(vpath),
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(out),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        duration = time.time() - start_time
        logger.info(f"Audio extracted successfully (bundled): {out.name} in {duration:.1f}s")
        perf_logger.log_metric("extract_audio", duration, True, {"method": "bundled_ffmpeg"})
        return out
    except Exception as e:
        logger.error(f"Audio extraction failed: {e}")
        error_tracker.log_error(e, context="Bundled ffmpeg extraction", module="audio", function="extract_audio")
        raise


def _has_ffmpeg_on_path() -> bool:
    return shutil.which("ffmpeg") is not None

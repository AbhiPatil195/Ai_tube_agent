from pathlib import Path
import os
import subprocess
import shutil
import ffmpeg

from .paths import AUDIO


def extract_audio(video_path: str | Path, output_path: str | Path | None = None) -> Path:
    """
    Extract audio as WAV (16kHz mono) from a video.
    Prefers ffmpeg-python with system ffmpeg; falls back to imageio-ffmpeg binary.
    """
    vpath = Path(video_path)
    if output_path is None:
        out = AUDIO / (vpath.stem + ".wav")
    else:
        out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if _has_ffmpeg_on_path():
        (
            ffmpeg
            .input(str(vpath))
            .output(str(out), acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(quiet=True)
        )
        return out

    # Fallback: use bundled imageio-ffmpeg executable
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("FFmpeg not available. Install system FFmpeg or imageio-ffmpeg.") from e

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
    return out


def _has_ffmpeg_on_path() -> bool:
    return shutil.which("ffmpeg") is not None

from pathlib import Path
from urllib.parse import urlparse, parse_qs
import shutil
from typing import Optional, Callable, Dict, Any

from pytube import YouTube

from .paths import VIDEOS
from .logger import logger, error_tracker, retry


def normalize_yt_url(url: str) -> str:
    """Normalize YouTube URLs: handle shorts and youtu.be to watch?v=.."""
    u = url.strip()
    if not u:
        return u
    # Convert youtu.be/<id> to watch?v=<id>
    if "youtu.be/" in u:
        vid = u.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    # Convert shorts to watch
    if "/shorts/" in u:
        vid = u.split("/shorts/")[-1].split("?")[0].split("&")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    # Strip playlist params; keep only v
    try:
        parts = urlparse(u)
        if parts.netloc.endswith("youtube.com") and parts.path == "/watch":
            qs = parse_qs(parts.query)
            v = (qs.get("v") or [None])[0]
            if v:
                return f"https://www.youtube.com/watch?v={v}"
    except Exception:
        pass
    return u


def _download_with_pytube(url: str, out_dir: Path, progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> Path | None:
    logger.info(f"Attempting download with pytube: {url}")
    try:
        yt = YouTube(url)
        # Prefer progressive mp4 streams which contain both audio+video
        stream = (
            yt.streams.filter(progressive=True, file_extension="mp4")
            .order_by("resolution")
            .desc()
            .first()
        )
        if stream is None:
            stream = (
                yt.streams.filter(file_extension="mp4")
                .order_by("filesize")
                .desc()
                .first()
            )
        if stream is None:
            logger.warning("No suitable stream found with pytube")
            return None
    except Exception as e:
        logger.warning(f"Pytube failed: {e}")
        return None
    if progress is not None:
        total = stream.filesize or 0

        def on_prog(s, chunk, bytes_remaining):
            try:
                tot = total or getattr(s, "filesize", 0) or 0
                downloaded = max(0, tot - int(bytes_remaining)) if tot else 0
                pct = (downloaded / tot * 100.0) if tot else None
                progress({
                    "source": "pytube",
                    "status": "downloading",
                    "percent": pct,
                    "downloaded": downloaded,
                    "total": tot,
                })
            except Exception:
                pass

        yt.register_on_progress_callback(on_prog)

    try:
        target = stream.download(output_path=str(out_dir))
        logger.info(f"Pytube download successful: {target}")
        return Path(target)
    except Exception as e:
        logger.error(f"Pytube download failed: {e}")
        error_tracker.log_error(e, context="Pytube download", module="download", function="_download_with_pytube")
        return None


def _get_ffmpeg_exe() -> Optional[str]:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


@retry(max_attempts=2, delay=2.0, exceptions=(RuntimeError, ConnectionError))
def _download_with_ytdlp(url: str, out_dir: Path, progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> Path:
    from yt_dlp import YoutubeDL

    logger.info(f"Downloading with yt-dlp: {url}")
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_exe = _get_ffmpeg_exe()
    # If ffmpeg is available, allow separate A/V merge into MP4; otherwise avoid merging.
    if ffmpeg_exe:
        ydl_opts = {
            "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "ffmpeg_location": ffmpeg_exe,
        }
    else:
        # No ffmpeg: select a single progressive stream to avoid merging.
        ydl_opts = {
            "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

    if progress is not None:
        def hook(d):
            try:
                if d.get('status') == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded = d.get('downloaded_bytes') or 0
                    pct = (downloaded / total * 100.0) if total else None
                    spd = d.get('speed')
                    eta = d.get('eta')
                    progress({
                        "source": "ytdlp",
                        "status": "downloading",
                        "percent": pct,
                        "downloaded": downloaded,
                        "total": total,
                        "speed": spd,
                        "eta": eta,
                    })
            except Exception:
                pass
        ydl_opts["progress_hooks"] = [hook]

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Try to determine the final downloaded file path robustly
            path_str = None
            rd = info.get("requested_downloads") if isinstance(info, dict) else None
            if rd and isinstance(rd, list) and rd and isinstance(rd[0], dict):
                path_str = rd[0].get("filepath") or rd[0].get("_filename")
            if not path_str:
                path_str = info.get("filepath") or info.get("_filename")
            if not path_str:
                path_str = ydl.prepare_filename(info)
            
            result_path = Path(path_str)
            logger.info(f"yt-dlp download successful: {result_path}")
            return result_path
    except Exception as e:
        logger.error(f"yt-dlp download failed: {e}")
        error_tracker.log_error(e, context="yt-dlp download", module="download", function="_download_with_ytdlp")
        raise


@retry(max_attempts=2, delay=2.0, exceptions=(RuntimeError, ConnectionError))
def download_youtube(url: str, output_dir: Path | None = None, progress: Optional[Callable[[Dict[str, Any]], None]] = None) -> Path:
    """
    Download a YouTube video as MP4 and return the file path.
    Tries pytube first; on failure falls back to yt-dlp (more robust).
    """
    logger.info(f"Starting download for URL: {url}")
    out_dir = Path(output_dir) if output_dir else VIDEOS
    out_dir.mkdir(parents=True, exist_ok=True)

    norm = normalize_yt_url(url)
    logger.debug(f"Normalized URL: {norm}")
    
    # Try pytube
    try:
        p = _download_with_pytube(norm, out_dir, progress)
        if p is not None and p.exists():
            logger.info(f"Download complete (pytube): {p}")
            return p
    except Exception as e:
        logger.debug(f"Pytube attempt failed, falling back to yt-dlp: {e}")

    # Fallback to yt-dlp
    try:
        result = _download_with_ytdlp(norm, out_dir, progress)
        logger.info(f"Download complete (yt-dlp): {result}")
        return result
    except Exception as e:
        error_msg = f"Failed to download video. Last error: {e}"
        logger.error(error_msg)
        error_tracker.log_error(e, context="Download failed with both pytube and yt-dlp", module="download", function="download_youtube")
        raise RuntimeError(error_msg)

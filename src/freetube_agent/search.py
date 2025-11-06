from typing import List, Dict, Any


def _search_with_ysp(query: str, limit: int) -> List[Dict[str, Any]]:
    # Try youtube-search-python first; fall back if it errors (version compatibility varies)
    try:
        from youtubesearchpython import VideosSearch  # type: ignore

        vs = VideosSearch(query, limit=limit)
        data = vs.result().get("result", [])
        results = []
        for item in data:
            title = item.get("title")
            duration = item.get("duration")
            channel = (item.get("channel") or {}).get("name")
            url = (item.get("link") or "").strip()
            thumbs = item.get("thumbnails") or []
            thumb = thumbs[0]["url"] if thumbs else None
            results.append({
                "title": title,
                "duration": duration,
                "channel": channel,
                "url": url,
                "thumbnail": thumb,
            })
        return results
    except Exception:
        return []


def _search_with_ytdlp(query: str, limit: int) -> List[Dict[str, Any]]:
    # Use yt-dlp to search without downloading
    from yt_dlp import YoutubeDL

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
    }
    expr = f"ytsearch{limit}:{query}"
    out: List[Dict[str, Any]] = []
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(expr, download=False)
        entries = info.get("entries") or []
        for e in entries:
            title = e.get("title")
            duration = e.get("duration_string") or e.get("duration")
            channel = e.get("uploader") or e.get("channel")
            url = e.get("url")
            if url and not str(url).startswith("http"):
                vid = e.get("id") or url
                url = f"https://www.youtube.com/watch?v={vid}"
            thumb = None
            thumbs = e.get("thumbnails") or []
            if thumbs:
                thumb = (thumbs[-1] or thumbs[0]).get("url")
            out.append({
                "title": title,
                "duration": duration,
                "channel": channel,
                "url": url,
                "thumbnail": thumb,
            })
    return out


def search_youtube(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Search YouTube with a robust fallback.

    Returns items with: title, duration, channel, url, thumbnail.
    """
    res = _search_with_ysp(query, limit)
    if res:
        return res
    return _search_with_ytdlp(query, limit)

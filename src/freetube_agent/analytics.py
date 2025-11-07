"""
Analytics & Insights Module
Generates statistics, visualizations, and insights from processed videos.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import json
from collections import Counter

from .paths import VIDEOS, AUDIO, TRANSCRIPTS


def get_library_stats() -> Dict[str, Any]:
    """
    Get comprehensive statistics about the library.
    
    Returns:
        Dictionary with library statistics
    """
    videos = list(VIDEOS.glob("*.mp4"))
    audios = list(AUDIO.glob("*.wav"))
    transcripts = list(TRANSCRIPTS.glob("*.txt"))
    
    # Calculate file sizes
    total_video_size = sum(v.stat().st_size for v in videos)
    total_audio_size = sum(a.stat().st_size for a in audios)
    total_transcript_size = sum(t.stat().st_size for t in transcripts)
    
    # Calculate total duration from transcripts (if they have segments)
    total_duration = 0
    total_words = 0
    
    for transcript in transcripts:
        try:
            content = transcript.read_text(encoding="utf-8")
            total_words += len(content.split())
        except Exception:
            pass
    
    return {
        "video_count": len(videos),
        "audio_count": len(audios),
        "transcript_count": len(transcripts),
        "total_video_size_mb": total_video_size / (1024 * 1024),
        "total_audio_size_mb": total_audio_size / (1024 * 1024),
        "total_transcript_size_kb": total_transcript_size / 1024,
        "total_size_mb": (total_video_size + total_audio_size + total_transcript_size) / (1024 * 1024),
        "total_words": total_words,
        "avg_words_per_transcript": total_words / len(transcripts) if transcripts else 0,
        "videos": [{"name": v.name, "size_mb": v.stat().st_size / (1024*1024)} for v in videos],
        "transcripts": [{"name": t.name, "size_kb": t.stat().st_size / 1024} for t in transcripts],
    }


def get_word_frequency(transcript_text: str, top_n: int = 50) -> List[tuple]:
    """
    Get word frequency from transcript.
    
    Args:
        transcript_text: Full transcript text
        top_n: Number of top words to return
    
    Returns:
        List of (word, count) tuples
    """
    # Common stop words to filter out
    stop_words = {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
        'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
        'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
        'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their',
        'is', 'was', 'are', 'been', 'has', 'had', 'were', 'can', 'said',
        'so', 'if', 'about', 'what', 'which', 'when', 'some', 'like', 'just',
        'into', 'out', 'up', 'them', 'him', 'than', 'who', 'very', 'its',
        'me', 'your', 'now', 'also', 'over', 'no', 'only', 'how', 'more',
        'these', 'then', 'could', 'other', 'because', 'much', 'get', 'go',
        'um', 'uh', 'yeah', 'okay', 'ok', 'gonna', 'wanna', 'gotta'
    }
    
    # Tokenize and clean
    words = transcript_text.lower().split()
    filtered_words = [
        word.strip('.,!?;:"()[]{}')
        for word in words
        if len(word.strip('.,!?;:"()[]{}')) > 3
        and word.strip('.,!?;:"()[]{}').lower() not in stop_words
        and word.strip('.,!?;:"()[]{}').isalpha()
    ]
    
    # Count frequency
    word_counts = Counter(filtered_words)
    return word_counts.most_common(top_n)


def analyze_transcript(transcript_text: str) -> Dict[str, Any]:
    """
    Analyze a single transcript for various metrics.
    
    Args:
        transcript_text: Full transcript text
    
    Returns:
        Dictionary with analysis results
    """
    words = transcript_text.split()
    sentences = transcript_text.split('.')
    
    # Basic stats
    word_count = len(words)
    char_count = len(transcript_text)
    sentence_count = len([s for s in sentences if s.strip()])
    
    # Word frequency
    top_words = get_word_frequency(transcript_text, 20)
    
    # Average metrics
    avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0
    avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
    
    # Unique words
    unique_words = len(set(word.lower().strip('.,!?;:"()[]{}') for word in words))
    vocabulary_richness = unique_words / word_count if word_count > 0 else 0
    
    return {
        "word_count": word_count,
        "character_count": char_count,
        "sentence_count": sentence_count,
        "unique_word_count": unique_words,
        "avg_word_length": round(avg_word_length, 2),
        "avg_sentence_length": round(avg_sentence_length, 2),
        "vocabulary_richness": round(vocabulary_richness, 3),
        "top_words": top_words,
    }


def generate_word_frequency_data(transcript_text: str, top_n: int = 30) -> Dict[str, Any]:
    """
    Generate data suitable for word frequency visualization.
    
    Args:
        transcript_text: Full transcript text
        top_n: Number of top words
    
    Returns:
        Dictionary with words and counts for plotting
    """
    word_freq = get_word_frequency(transcript_text, top_n)
    
    return {
        "words": [word for word, _ in word_freq],
        "counts": [count for _, count in word_freq],
        "total_unique": len(set(transcript_text.lower().split())),
    }


def get_processing_timeline() -> List[Dict[str, Any]]:
    """
    Get timeline of when files were processed based on modification time.
    
    Returns:
        List of file processing events
    """
    timeline = []
    
    for transcript in TRANSCRIPTS.glob("*.txt"):
        mod_time = datetime.fromtimestamp(transcript.stat().st_mtime)
        timeline.append({
            "name": transcript.stem,
            "type": "transcript",
            "timestamp": mod_time,
            "date_str": mod_time.strftime("%Y-%m-%d %H:%M"),
        })
    
    # Sort by time
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return timeline


def get_activity_summary(days: int = 30) -> Dict[str, Any]:
    """
    Get activity summary for the last N days.
    
    Args:
        days: Number of days to look back
    
    Returns:
        Dictionary with activity data
    """
    from datetime import timedelta
    
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    
    recent_transcripts = []
    for transcript in TRANSCRIPTS.glob("*.txt"):
        mod_time = datetime.fromtimestamp(transcript.stat().st_mtime)
        if mod_time >= cutoff:
            recent_transcripts.append({
                "name": transcript.stem,
                "date": mod_time.strftime("%Y-%m-%d"),
                "time": mod_time.strftime("%H:%M"),
            })
    
    # Group by date
    date_counts = Counter(t["date"] for t in recent_transcripts)
    
    return {
        "period_days": days,
        "total_processed": len(recent_transcripts),
        "daily_activity": dict(date_counts),
        "avg_per_day": len(recent_transcripts) / days if days > 0 else 0,
        "recent_items": sorted(recent_transcripts, key=lambda x: x["date"], reverse=True)[:10],
    }


def compare_transcripts(transcript_paths: List[Path]) -> Dict[str, Any]:
    """
    Compare multiple transcripts.
    
    Args:
        transcript_paths: List of paths to transcript files
    
    Returns:
        Dictionary with comparison data
    """
    comparisons = []
    
    for path in transcript_paths:
        try:
            content = path.read_text(encoding="utf-8")
            analysis = analyze_transcript(content)
            analysis["name"] = path.stem
            comparisons.append(analysis)
        except Exception:
            continue
    
    return {
        "count": len(comparisons),
        "transcripts": comparisons,
        "avg_word_count": sum(t["word_count"] for t in comparisons) / len(comparisons) if comparisons else 0,
        "total_words": sum(t["word_count"] for t in comparisons),
    }


def export_analytics_report(output_path: Optional[Path] = None) -> Path:
    """
    Export a comprehensive analytics report as JSON.
    
    Args:
        output_path: Optional custom output path
    
    Returns:
        Path to exported report
    """
    from .paths import DATA
    
    if output_path is None:
        output_path = DATA / f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "library_stats": get_library_stats(),
        "processing_timeline": [
            {**item, "timestamp": item["timestamp"].isoformat()}
            for item in get_processing_timeline()
        ],
        "activity_30d": get_activity_summary(30),
        "activity_7d": get_activity_summary(7),
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return output_path

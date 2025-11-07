"""
Video Player Utilities
Handles video playback, timestamp parsing, and transcript synchronization.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
import re


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds to HH:MM:SS or MM:SS format.
    
    Args:
        seconds: Time in seconds
    
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def parse_timestamp(timestamp_str: str) -> float:
    """
    Parse timestamp string to seconds.
    Supports formats: HH:MM:SS, MM:SS, SS
    
    Args:
        timestamp_str: Timestamp string
    
    Returns:
        Time in seconds
    """
    parts = timestamp_str.strip().split(':')
    
    try:
        if len(parts) == 3:  # HH:MM:SS
            h, m, s = map(float, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:  # MM:SS
            m, s = map(float, parts)
            return m * 60 + s
        elif len(parts) == 1:  # SS
            return float(parts[0])
        else:
            return 0.0
    except (ValueError, IndexError):
        return 0.0


def find_current_segment(current_time: float, segments: List[Dict[str, Any]]) -> Optional[int]:
    """
    Find the segment index that contains the current time.
    
    Args:
        current_time: Current playback time in seconds
        segments: List of segment dicts with 'start' and 'end' keys
    
    Returns:
        Index of current segment, or None if not found
    """
    for idx, seg in enumerate(segments):
        start = seg.get('start', 0.0)
        end = seg.get('end', 0.0)
        if start <= current_time <= end:
            return idx
    return None


def generate_video_html(video_path: str, width: str = "100%", autoplay: bool = False) -> str:
    """
    Generate HTML5 video player with custom controls.
    
    Args:
        video_path: Path to video file
        width: Width of video player
        autoplay: Whether to autoplay
    
    Returns:
        HTML string for video player
    """
    autoplay_attr = "autoplay" if autoplay else ""
    
    html = f"""
    <video id="video-player" width="{width}" controls {autoplay_attr}>
        <source src="{video_path}" type="video/mp4">
        Your browser does not support the video tag.
    </video>
    <script>
        const video = document.getElementById('video-player');
        
        // Function to jump to specific time
        window.seekTo = function(seconds) {{
            video.currentTime = seconds;
            video.play();
        }};
        
        // Function to get current time
        window.getCurrentTime = function() {{
            return video.currentTime;
        }};
        
        // Send time updates to Streamlit
        video.addEventListener('timeupdate', function() {{
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: video.currentTime
            }}, '*');
        }});
    </script>
    """
    return html


def create_clickable_transcript(
    segments: List[Dict[str, Any]], 
    current_segment_idx: Optional[int] = None,
    highlight_color: str = "#ffd700"
) -> str:
    """
    Create HTML transcript with clickable timestamps.
    
    Args:
        segments: List of segment dicts with 'start', 'end', 'text'
        current_segment_idx: Index of currently playing segment
        highlight_color: Color to highlight current segment
    
    Returns:
        HTML string for clickable transcript
    """
    html_parts = ['<div class="transcript-container" style="max-height: 600px; overflow-y: auto;">']
    
    for idx, seg in enumerate(segments):
        start = seg.get('start', 0.0)
        end = seg.get('end', 0.0)
        text = seg.get('text', '').strip()
        
        timestamp_str = format_timestamp(start)
        
        # Highlight current segment
        bg_color = highlight_color if idx == current_segment_idx else "transparent"
        
        html_parts.append(f"""
        <div class="transcript-segment" id="segment-{idx}" 
             style="padding: 10px; margin: 5px 0; background-color: {bg_color}; 
                    border-radius: 5px; cursor: pointer; transition: background-color 0.3s;"
             onmouseover="this.style.backgroundColor='#e8e8e8'"
             onmouseout="this.style.backgroundColor='{bg_color}'"
             onclick="window.parent.postMessage({{type: 'seekTo', time: {start}}}, '*')">
            <span style="color: #3ea6ff; font-weight: bold; font-family: monospace;">
                [{timestamp_str}]
            </span>
            <span style="margin-left: 10px;">
                {text}
            </span>
        </div>
        """)
    
    html_parts.append('</div>')
    
    # Add auto-scroll script
    if current_segment_idx is not None:
        html_parts.append(f"""
        <script>
            const currentSegment = document.getElementById('segment-{current_segment_idx}');
            if (currentSegment) {{
                currentSegment.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            }}
        </script>
        """)
    
    return '\n'.join(html_parts)


def extract_timestamps_from_text(text: str) -> List[Tuple[float, str]]:
    """
    Extract timestamps and associated text from a transcript string.
    
    Args:
        text: Transcript text with timestamps like [00:15] or [1:23:45]
    
    Returns:
        List of (timestamp_seconds, text) tuples
    """
    # Pattern to match timestamps: [HH:MM:SS], [MM:SS], or [SS]
    pattern = r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]'
    
    results = []
    parts = re.split(pattern, text)
    
    # parts will be: [text_before_first_timestamp, timestamp1, text1, timestamp2, text2, ...]
    for i in range(1, len(parts), 2):
        if i < len(parts):
            timestamp_str = parts[i]
            text_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            
            if text_content:
                seconds = parse_timestamp(timestamp_str)
                results.append((seconds, text_content))
    
    return results


def create_segment_navigation(segments: List[Dict[str, Any]], current_idx: Optional[int] = None) -> str:
    """
    Create navigation buttons for segments.
    
    Args:
        segments: List of segments
        current_idx: Current segment index
    
    Returns:
        HTML string for navigation
    """
    if not segments:
        return ""
    
    prev_disabled = "disabled" if current_idx is None or current_idx <= 0 else ""
    next_disabled = "disabled" if current_idx is None or current_idx >= len(segments) - 1 else ""
    
    prev_idx = max(0, current_idx - 1) if current_idx is not None else 0
    next_idx = min(len(segments) - 1, current_idx + 1) if current_idx is not None else 0
    
    html = f"""
    <div style="display: flex; gap: 10px; margin: 10px 0; align-items: center;">
        <button onclick="window.parent.postMessage({{type: 'seekTo', time: {segments[prev_idx]['start']}}}, '*')"
                style="padding: 8px 16px; background: #3ea6ff; color: white; border: none; 
                       border-radius: 5px; cursor: pointer;" {prev_disabled}>
            ⏮️ Previous
        </button>
        <span style="color: #888; font-size: 14px;">
            Segment {(current_idx or 0) + 1} / {len(segments)}
        </span>
        <button onclick="window.parent.postMessage({{type: 'seekTo', time: {segments[next_idx]['start']}}}, '*')"
                style="padding: 8px 16px; background: #3ea6ff; color: white; border: none; 
                       border-radius: 5px; cursor: pointer;" {next_disabled}>
            Next ⏭️
        </button>
    </div>
    """
    return html

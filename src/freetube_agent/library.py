"""
Library Management Module
Handles search, filtering, sorting, and organization of video library.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

from .paths import VIDEOS, AUDIO, TRANSCRIPTS, DATA


class LibraryItem:
    """Represents a video item in the library"""
    
    def __init__(self, stem: str):
        self.stem = stem
        self.video_path = VIDEOS / f"{stem}.mp4"
        self.audio_path = AUDIO / f"{stem}.wav"
        self.transcript_path = TRANSCRIPTS / f"{stem}.txt"
        self.metadata_path = DATA / "metadata" / f"{stem}.json"
        
        # Load metadata if exists
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from JSON file"""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save_metadata(self) -> bool:
        """Save metadata to JSON file"""
        try:
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    @property
    def has_video(self) -> bool:
        return self.video_path.exists()
    
    @property
    def has_audio(self) -> bool:
        return self.audio_path.exists()
    
    @property
    def has_transcript(self) -> bool:
        return self.transcript_path.exists()
    
    @property
    def is_complete(self) -> bool:
        return self.has_video and self.has_audio and self.has_transcript
    
    @property
    def video_size_mb(self) -> float:
        if self.has_video:
            return self.video_path.stat().st_size / (1024 * 1024)
        return 0.0
    
    @property
    def audio_size_mb(self) -> float:
        if self.has_audio:
            return self.audio_path.stat().st_size / (1024 * 1024)
        return 0.0
    
    @property
    def transcript_size_kb(self) -> float:
        if self.has_transcript:
            return self.transcript_path.stat().st_size / 1024
        return 0.0
    
    @property
    def total_size_mb(self) -> float:
        return self.video_size_mb + self.audio_size_mb + (self.transcript_size_kb / 1024)
    
    @property
    def created_date(self) -> Optional[datetime]:
        """Get creation date from the oldest file"""
        dates = []
        if self.has_video:
            dates.append(datetime.fromtimestamp(self.video_path.stat().st_ctime))
        if self.has_audio:
            dates.append(datetime.fromtimestamp(self.audio_path.stat().st_ctime))
        if self.has_transcript:
            dates.append(datetime.fromtimestamp(self.transcript_path.stat().st_ctime))
        return min(dates) if dates else None
    
    @property
    def modified_date(self) -> Optional[datetime]:
        """Get last modified date from the newest file"""
        dates = []
        if self.has_video:
            dates.append(datetime.fromtimestamp(self.video_path.stat().st_mtime))
        if self.has_audio:
            dates.append(datetime.fromtimestamp(self.audio_path.stat().st_mtime))
        if self.has_transcript:
            dates.append(datetime.fromtimestamp(self.transcript_path.stat().st_mtime))
        return max(dates) if dates else None
    
    @property
    def tags(self) -> List[str]:
        return self.metadata.get('tags', [])
    
    def add_tag(self, tag: str) -> bool:
        """Add a tag to this item"""
        if 'tags' not in self.metadata:
            self.metadata['tags'] = []
        if tag not in self.metadata['tags']:
            self.metadata['tags'].append(tag)
            return self.save_metadata()
        return False
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from this item"""
        if 'tags' in self.metadata and tag in self.metadata['tags']:
            self.metadata['tags'].remove(tag)
            return self.save_metadata()
        return False
    
    @property
    def notes(self) -> str:
        return self.metadata.get('notes', '')
    
    def set_notes(self, notes: str) -> bool:
        """Set notes for this item"""
        self.metadata['notes'] = notes
        return self.save_metadata()
    
    @property
    def rating(self) -> int:
        return self.metadata.get('rating', 0)
    
    def set_rating(self, rating: int) -> bool:
        """Set rating (0-5) for this item"""
        if 0 <= rating <= 5:
            self.metadata['rating'] = rating
            return self.save_metadata()
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display"""
        return {
            'stem': self.stem,
            'has_video': self.has_video,
            'has_audio': self.has_audio,
            'has_transcript': self.has_transcript,
            'is_complete': self.is_complete,
            'video_size_mb': self.video_size_mb,
            'total_size_mb': self.total_size_mb,
            'created_date': self.created_date,
            'modified_date': self.modified_date,
            'tags': self.tags,
            'notes': self.notes,
            'rating': self.rating
        }


def get_all_library_items() -> List[LibraryItem]:
    """Get all items in the library"""
    # Collect all unique stems from videos, audio, and transcripts
    stems = set()
    
    for video in VIDEOS.glob("*.mp4"):
        stems.add(video.stem)
    for audio in AUDIO.glob("*.wav"):
        stems.add(audio.stem)
    for transcript in TRANSCRIPTS.glob("*.txt"):
        stems.add(transcript.stem)
    
    return [LibraryItem(stem) for stem in sorted(stems)]


def search_library(query: str, items: Optional[List[LibraryItem]] = None) -> List[LibraryItem]:
    """
    Search library items by name, tags, or notes.
    
    Args:
        query: Search query
        items: Items to search (defaults to all items)
    
    Returns:
        Filtered list of items
    """
    if items is None:
        items = get_all_library_items()
    
    if not query:
        return items
    
    query_lower = query.lower()
    results = []
    
    for item in items:
        # Search in stem (filename)
        if query_lower in item.stem.lower():
            results.append(item)
            continue
        
        # Search in tags
        if any(query_lower in tag.lower() for tag in item.tags):
            results.append(item)
            continue
        
        # Search in notes
        if query_lower in item.notes.lower():
            results.append(item)
            continue
        
        # Search in transcript content
        if item.has_transcript:
            try:
                content = item.transcript_path.read_text(encoding='utf-8')
                if query_lower in content.lower():
                    results.append(item)
            except Exception:
                pass
    
    return results


def filter_library(
    items: Optional[List[LibraryItem]] = None,
    has_video: Optional[bool] = None,
    has_audio: Optional[bool] = None,
    has_transcript: Optional[bool] = None,
    is_complete: Optional[bool] = None,
    min_rating: Optional[int] = None,
    tags: Optional[List[str]] = None
) -> List[LibraryItem]:
    """
    Filter library items by various criteria.
    
    Args:
        items: Items to filter (defaults to all items)
        has_video: Filter by video presence
        has_audio: Filter by audio presence
        has_transcript: Filter by transcript presence
        is_complete: Filter by completion status
        min_rating: Minimum rating (0-5)
        tags: Tags to filter by (item must have at least one)
    
    Returns:
        Filtered list of items
    """
    if items is None:
        items = get_all_library_items()
    
    results = items
    
    if has_video is not None:
        results = [item for item in results if item.has_video == has_video]
    
    if has_audio is not None:
        results = [item for item in results if item.has_audio == has_audio]
    
    if has_transcript is not None:
        results = [item for item in results if item.has_transcript == has_transcript]
    
    if is_complete is not None:
        results = [item for item in results if item.is_complete == is_complete]
    
    if min_rating is not None:
        results = [item for item in results if item.rating >= min_rating]
    
    if tags:
        results = [item for item in results if any(tag in item.tags for tag in tags)]
    
    return results


def sort_library(
    items: List[LibraryItem],
    sort_by: str = "name",
    reverse: bool = False
) -> List[LibraryItem]:
    """
    Sort library items.
    
    Args:
        items: Items to sort
        sort_by: Sort key - "name", "date_created", "date_modified", "size", "rating"
        reverse: Sort in descending order
    
    Returns:
        Sorted list of items
    """
    if sort_by == "name":
        return sorted(items, key=lambda x: x.stem.lower(), reverse=reverse)
    elif sort_by == "date_created":
        return sorted(items, key=lambda x: x.created_date or datetime.min, reverse=reverse)
    elif sort_by == "date_modified":
        return sorted(items, key=lambda x: x.modified_date or datetime.min, reverse=reverse)
    elif sort_by == "size":
        return sorted(items, key=lambda x: x.total_size_mb, reverse=reverse)
    elif sort_by == "rating":
        return sorted(items, key=lambda x: x.rating, reverse=reverse)
    else:
        return items


def get_all_tags() -> List[str]:
    """Get all unique tags used in the library"""
    items = get_all_library_items()
    tags = set()
    for item in items:
        tags.update(item.tags)
    return sorted(tags)


def delete_library_item(item: LibraryItem, delete_video: bool = True, 
                       delete_audio: bool = True, delete_transcript: bool = True,
                       delete_metadata: bool = True) -> Dict[str, bool]:
    """
    Delete files associated with a library item.
    
    Args:
        item: Item to delete
        delete_video: Whether to delete video file
        delete_audio: Whether to delete audio file
        delete_transcript: Whether to delete transcript file
        delete_metadata: Whether to delete metadata file
    
    Returns:
        Dict with deletion results for each file type
    """
    results = {}
    
    if delete_video and item.has_video:
        try:
            item.video_path.unlink()
            results['video'] = True
        except Exception:
            results['video'] = False
    
    if delete_audio and item.has_audio:
        try:
            item.audio_path.unlink()
            results['audio'] = True
        except Exception:
            results['audio'] = False
    
    if delete_transcript and item.has_transcript:
        try:
            item.transcript_path.unlink()
            results['transcript'] = True
        except Exception:
            results['transcript'] = False
    
    if delete_metadata and item.metadata_path.exists():
        try:
            item.metadata_path.unlink()
            results['metadata'] = True
        except Exception:
            results['metadata'] = False
    
    return results

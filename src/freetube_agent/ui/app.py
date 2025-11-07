import streamlit as st
from pathlib import Path
from typing import List
import base64
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.freetube_agent.download import download_youtube
from src.freetube_agent.audio import extract_audio
from src.freetube_agent.transcribe import transcribe, save_transcript, Transcript, Segment
from src.freetube_agent.export import save_srt, save_vtt
from src.freetube_agent.paths import VIDEOS, AUDIO, TRANSCRIPTS, DATA
from src.freetube_agent.rag import (
    build_index, query_index, format_time, chunk_transcript,
    is_indexed, get_indexed_videos, delete_index, get_index_stats, 
    batch_index_all, retrieve_relevant_chunks
)
from src.freetube_agent.llm import run_ollama
from src.freetube_agent.search import search_youtube

# New modules for Quick Wins features
from src.freetube_agent.summarize import generate_full_analysis, generate_summary, extract_key_points, generate_tldr
from src.freetube_agent.export_advanced import export_to_pdf, export_to_word, export_to_markdown, export_to_json, export_blog_post
from src.freetube_agent.analytics import get_library_stats, analyze_transcript, generate_word_frequency_data, get_activity_summary, export_analytics_report
from src.freetube_agent.config import get_config_manager, get_config, save_config
from src.freetube_agent.player import (
    format_timestamp, parse_timestamp, find_current_segment,
    create_clickable_transcript, create_segment_navigation
)
from src.freetube_agent.library import (
    LibraryItem, get_all_library_items, search_library, filter_library,
    sort_library, get_all_tags, delete_library_item
)

# Try to import streamlit_player for enhanced video playback
try:
    from streamlit_player import st_player
    HAS_PLAYER = True
except ImportError:
    HAS_PLAYER = False


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="FreeTube-Agent",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================================
# LOAD CUSTOM CSS
# ============================================================================

def load_css():
    css_path = Path(__file__).parent / "styles" / "youtube.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

# Load configuration
config_manager = get_config_manager()
config = config_manager.config

# Initialize session state with config defaults
if "view" not in st.session_state:
    st.session_state.view = config.ui.default_view
if "search_query" not in st.session_state:
    st.session_state.search_query = ""
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "current_video" not in st.session_state:
    st.session_state.current_video = None
if "theme" not in st.session_state:
    st.session_state.theme = config.ui.theme

# Transcription settings
if "model_size" not in st.session_state:
    st.session_state.model_size = config.transcription.model_size
if "language" not in st.session_state:
    st.session_state.language = config.transcription.language
if "fast_mode" not in st.session_state:
    st.session_state.fast_mode = config.transcription.fast_mode
if "vad_filter" not in st.session_state:
    st.session_state.vad_filter = config.transcription.vad_filter

# Semantic search settings
if "auto_index_enabled" not in st.session_state:
    st.session_state.auto_index_enabled = config.semantic_search.auto_index_enabled
if "chunk_size" not in st.session_state:
    st.session_state.chunk_size = config.semantic_search.chunk_size
if "chunk_overlap" not in st.session_state:
    st.session_state.chunk_overlap = config.semantic_search.chunk_overlap

# LLM settings
if "ollama_path" not in st.session_state:
    st.session_state.ollama_path = config.llm.ollama_path
if "ollama_model" not in st.session_state:
    st.session_state.ollama_model = config.llm.default_model


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def render_video_card(video_data, index):
    """Render a YouTube-style video card"""
    with st.container():
        st.markdown(f"""
        <div class="video-card">
            <div class="video-thumbnail">
                <img src="{video_data.get('thumbnail', '')}" alt="{video_data.get('title', 'Video')}">
                <div class="duration-badge">{video_data.get('duration', 'N/A')}</div>
            </div>
            <div class="video-info">
                <div class="video-title">{video_data.get('title', 'Untitled')}</div>
                <div class="video-channel">{video_data.get('channel', 'Unknown Channel')}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("📥 Download", key=f"dl_{index}", use_container_width=True):
                st.session_state.current_video = video_data
                st.session_state.view = "video"
                st.rerun()
        with col2:
            if st.button("▶️ Process", key=f"proc_{index}", use_container_width=True):
                process_video_pipeline(video_data['url'])


def process_video_pipeline(url):
    """Process video: download -> extract -> transcribe"""
    with st.status("Processing video...", expanded=True) as status:
        try:
            # Download
            st.write("📥 Downloading video...")
            video_path = download_youtube(url, VIDEOS)
            st.session_state.video_path = str(video_path)
            st.write(f"✅ Downloaded: {video_path.name}")
            
            # Extract Audio
            st.write("🎵 Extracting audio...")
            audio_path = extract_audio(video_path)
            st.session_state.audio_path = str(audio_path)
            st.write(f"✅ Audio extracted: {audio_path.name}")
            
            # Transcribe
            st.write("📝 Transcribing (this may take a while)...")
            t = transcribe(
                audio_path,
                model_size=st.session_state.get("model_size", "base"),
                compute_type="int8",
                beam_size=1,
                language="en",
                vad_filter=False,
                word_timestamps=False,
            )
            save_path = save_transcript(t, video_stem=audio_path.stem)
            st.session_state.transcript_path = str(save_path)
            st.session_state.transcript_text = t.text
            st.session_state._segments = [(s.start, s.end, s.text) for s in t.segments]
            st.write(f"✅ Transcript saved: {save_path.name}")
            
            status.update(label="✅ Processing complete!", state="complete")
            st.success("Video processed successfully! View transcript below.")
            
        except Exception as e:
            status.update(label="❌ Processing failed", state="error")
            st.error(f"Error: {e}")


def render_transcript_sidebar():
    """Render transcript in a YouTube-style sidebar"""
    if "transcript_text" in st.session_state and st.session_state.transcript_text:
        st.markdown("### 📝 Transcript")
        segments = st.session_state.get("_segments", [])
        
        if segments:
            st.markdown('<div class="transcript-container">', unsafe_allow_html=True)
            for start, end, text in segments:
                st.markdown(f"""
                <div class="transcript-segment">
                    <div class="timestamp">{format_time(start)} - {format_time(end)}</div>
                    <div class="segment-text">{text}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.text_area("Full Transcript", st.session_state.transcript_text, height=400)
    else:
        st.info("No transcript available yet. Process a video first.")


# ============================================================================
# TOP NAVIGATION BAR
# ============================================================================

def render_top_nav():
    """Render YouTube-style top navigation"""
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        st.markdown("""
        <div class="logo">
            <span class="logo-icon">🎥</span>
            <span>FreeTube-Agent</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        search_query = st.text_input(
            "Search",
            placeholder="Search YouTube videos...",
            label_visibility="collapsed",
            key="main_search"
        )
        if search_query and search_query != st.session_state.search_query:
            st.session_state.search_query = search_query
            try:
                st.session_state.search_results = search_youtube(search_query, limit=12)
                st.session_state.view = "search"
            except Exception as e:
                st.error(f"Search failed: {e}")
    
    with col3:
        cols = st.columns([1, 1, 1, 1])
        with cols[0]:
            if st.button("🏠", help="Home", use_container_width=True):
                st.session_state.view = "home"
                st.rerun()
        with cols[1]:
            if st.button("📚", help="Library", use_container_width=True):
                st.session_state.view = "library"
                st.rerun()
        with cols[2]:
            if st.button("📊", help="Analytics", use_container_width=True):
                st.session_state.view = "analytics"
                st.rerun()
        with cols[3]:
            if st.button("⚙️", help="Settings", use_container_width=True):
                st.session_state.view = "settings"
                st.rerun()


# ============================================================================
# HOME VIEW
# ============================================================================

def render_home_view():
    """Render home page with welcome and quick actions"""
    st.markdown("## 🏠 Welcome to FreeTube-Agent")
    st.markdown("Your local, privacy-preserving video intelligence tool")
    
    st.markdown("---")
    
    # Quick Stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">Videos Processed</div>
        </div>
        """.format(len(list(VIDEOS.glob("*.mp4")))), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">Transcripts</div>
        </div>
        """.format(len(list(TRANSCRIPTS.glob("*.txt")))), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{}</div>
            <div class="metric-label">Audio Files</div>
        </div>
        """.format(len(list(AUDIO.glob("*.wav")))), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">100%</div>
            <div class="metric-label">Privacy</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Quick Actions
    st.markdown("### 🚀 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 🔍 Search & Download")
        st.write("Search YouTube and download videos for processing")
        url = st.text_input("Paste YouTube URL", placeholder="https://youtube.com/watch?v=...")
        if st.button("Download & Process", type="primary", use_container_width=True, disabled=not url):
            process_video_pipeline(url)
    
    with col2:
        st.markdown("#### 📝 View Transcripts")
        st.write("Browse and manage your saved transcripts")
        transcripts = list(TRANSCRIPTS.glob("*.txt"))
        if transcripts:
            selected = st.selectbox("Select transcript", [t.stem for t in transcripts])
            if st.button("View Transcript", use_container_width=True):
                st.session_state.view = "transcript"
                st.session_state.selected_transcript = selected
                st.rerun()
        else:
            st.info("No transcripts yet")
    
    with col3:
        st.markdown("#### 💬 Ask Questions")
        st.write("Use local AI to answer questions about your videos")
        if st.button("Go to Q&A", use_container_width=True):
            st.session_state.view = "qa"
            st.rerun()


# ============================================================================
# SEARCH RESULTS VIEW
# ============================================================================

def render_search_view():
    """Render search results in YouTube grid style"""
    st.markdown(f"## 🔍 Search Results for: *{st.session_state.search_query}*")
    
    results = st.session_state.search_results
    
    if not results:
        st.info("No results found. Try a different search query.")
        return
    
    st.markdown(f"Found **{len(results)}** videos")
    st.markdown("---")
    
    # Create grid layout (3 columns)
    for i in range(0, len(results), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            if i + j < len(results):
                with col:
                    render_video_card(results[i + j], i + j)


# ============================================================================
# VIDEO VIEW
# ============================================================================

def render_video_view():
    """Render single video processing view"""
    video = st.session_state.current_video
    
    if not video:
        st.warning("No video selected")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"## {video.get('title', 'Video')}")
        st.markdown(f"**Channel:** {video.get('channel', 'Unknown')}")
        st.markdown(f"**Duration:** {video.get('duration', 'N/A')}")
        
        st.markdown("---")
        
        # Video Player Section
        if "video_path" in st.session_state:
            vpath = Path(st.session_state.video_path)
            if vpath.exists():
                st.markdown("### 🎬 Video Player")
                try:
                    # Use native Streamlit video player
                    st.video(str(vpath))
                except Exception as e:
                    st.error(f"Error loading video: {e}")
                    # Fallback to thumbnail
                    if video.get('thumbnail'):
                        st.image(video['thumbnail'], use_container_width=True)
            else:
                # Video not found, show thumbnail
                if video.get('thumbnail'):
                    st.image(video['thumbnail'], use_container_width=True)
        else:
            # Video not downloaded yet, show thumbnail
            if video.get('thumbnail'):
                st.image(video['thumbnail'], use_container_width=True)
        
        st.markdown("---")
        
        # Processing controls
        st.markdown("### 🎬 Processing Pipeline")
        
        url = video.get('url', '')
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("📥 Download Video", type="primary", use_container_width=True):
                with st.spinner("Downloading..."):
                    try:
                        video_path = download_youtube(url, VIDEOS)
                        st.session_state.video_path = str(video_path)
                        st.success(f"Downloaded: {video_path.name}")
                    except Exception as e:
                        st.error(f"Download failed: {e}")
        
        with col_b:
            if st.button("🎵 Extract Audio", use_container_width=True, 
                        disabled="video_path" not in st.session_state):
                with st.spinner("Extracting audio..."):
                    try:
                        vpath = Path(st.session_state.video_path)
                        audio_path = extract_audio(vpath)
                        st.session_state.audio_path = str(audio_path)
                        st.success(f"Audio: {audio_path.name}")
                    except Exception as e:
                        st.error(f"Audio extraction failed: {e}")
        
        with col_c:
            if st.button("📝 Transcribe", use_container_width=True,
                        disabled="audio_path" not in st.session_state):
                with st.spinner("Transcribing..."):
                    try:
                        apath = Path(st.session_state.audio_path)
                        t = transcribe(
                            apath,
                            model_size=st.session_state.get("model_size", "base"),
                            compute_type="int8",
                            beam_size=1,
                            language="en",
                        )
                        save_path = save_transcript(t, video_stem=apath.stem)
                        st.session_state.transcript_path = str(save_path)
                        st.session_state.transcript_text = t.text
                        st.session_state._segments = [(s.start, s.end, s.text) for s in t.segments]
                        st.success(f"Transcript saved!")
                        
                        # Auto-index for semantic search (if enabled)
                        auto_index = st.session_state.get("auto_index_enabled", True)
                        if auto_index:
                            try:
                                with st.spinner("Building search index..."):
                                    chunk_count = build_index(apath.stem, t)
                                    st.success(f"✅ Search index built ({chunk_count} chunks)")
                            except Exception as idx_err:
                                st.warning(f"⚠️ Indexing failed (search may be limited): {idx_err}")
                    except Exception as e:
                        st.error(f"Transcription failed: {e}")
        
        # Status indicators
        st.markdown("#### Status")
        status_cols = st.columns(3)
        with status_cols[0]:
            if "video_path" in st.session_state:
                st.markdown('<span class="status-badge success">✅ Video Downloaded</span>', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge">⏳ Pending</span>', 
                           unsafe_allow_html=True)
        
        with status_cols[1]:
            if "audio_path" in st.session_state:
                st.markdown('<span class="status-badge success">✅ Audio Extracted</span>', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge">⏳ Pending</span>', 
                           unsafe_allow_html=True)
        
        with status_cols[2]:
            if "transcript_path" in st.session_state:
                st.markdown('<span class="status-badge success">✅ Transcribed</span>', 
                           unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge">⏳ Pending</span>', 
                           unsafe_allow_html=True)
    
    with col2:
        render_transcript_sidebar()


# ============================================================================
# LIBRARY VIEW HELPERS
# ============================================================================

def render_library_list(items: List[LibraryItem]):
    """Render library items in list view"""
    for item in items:
        with st.container():
            # Create card-like container
            col1, col2, col3, col4, col5, col6 = st.columns([3, 1, 1, 1, 1, 1])
            
            with col1:
                # Name and status
                st.markdown(f"### {item.stem}")
                status_icons = []
                if item.has_video:
                    status_icons.append("🎬")
                if item.has_audio:
                    status_icons.append("🎵")
                if item.has_transcript:
                    status_icons.append("📝")
                st.markdown(f"{''.join(status_icons)} | {item.total_size_mb:.1f} MB")
                
                # Tags
                if item.tags:
                    tags_html = " ".join([f'<span style="background: #3ea6ff; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; margin-right: 5px;">{tag}</span>' for tag in item.tags])
                    st.markdown(tags_html, unsafe_allow_html=True)
                
                # Rating
                if item.rating > 0:
                    st.markdown(f"⭐ {'★' * item.rating}{'☆' * (5 - item.rating)}")
            
            with col2:
                # View button
                if item.has_transcript:
                    if st.button("👁️ View", key=f"view_{item.stem}", use_container_width=True):
                        st.session_state.selected_transcript = item.stem
                        st.session_state.view = "transcript"
                        st.rerun()
            
            with col3:
                # Play video button
                if item.has_video:
                    if st.button("▶️ Play", key=f"play_{item.stem}", use_container_width=True):
                        st.session_state.selected_transcript = item.stem
                        st.session_state.view = "transcript"
                        st.rerun()
            
            with col4:
                # Tag management
                if st.button("🏷️ Tags", key=f"tags_{item.stem}", use_container_width=True):
                    st.session_state[f"show_tags_{item.stem}"] = not st.session_state.get(f"show_tags_{item.stem}", False)
                    st.rerun()
            
            with col5:
                # Rating
                if st.button("⭐ Rate", key=f"rate_{item.stem}", use_container_width=True):
                    st.session_state[f"show_rating_{item.stem}"] = not st.session_state.get(f"show_rating_{item.stem}", False)
                    st.rerun()
            
            with col6:
                # Delete button
                if st.button("🗑️", key=f"del_{item.stem}", use_container_width=True, help="Delete"):
                    st.session_state[f"confirm_delete_{item.stem}"] = True
                    st.rerun()
            
            # Show tag input if requested
            if st.session_state.get(f"show_tags_{item.stem}", False):
                tag_col1, tag_col2 = st.columns([3, 1])
                with tag_col1:
                    new_tag = st.text_input("Add tag", key=f"new_tag_{item.stem}", placeholder="Enter tag name")
                with tag_col2:
                    if st.button("Add", key=f"add_tag_{item.stem}"):
                        if new_tag:
                            item.add_tag(new_tag)
                            st.session_state[f"show_tags_{item.stem}"] = False
                            st.rerun()
                
                if item.tags:
                    st.write("Current tags:")
                    tag_cols = st.columns(len(item.tags))
                    for idx, tag in enumerate(item.tags):
                        with tag_cols[idx]:
                            if st.button(f"❌ {tag}", key=f"remove_{item.stem}_{tag}"):
                                item.remove_tag(tag)
                                st.rerun()
            
            # Show rating input if requested
            if st.session_state.get(f"show_rating_{item.stem}", False):
                rating = st.slider("Rating", 0, 5, item.rating, key=f"rating_slider_{item.stem}")
                if st.button("Save Rating", key=f"save_rating_{item.stem}"):
                    item.set_rating(rating)
                    st.session_state[f"show_rating_{item.stem}"] = False
                    st.rerun()
            
            # Confirm delete
            if st.session_state.get(f"confirm_delete_{item.stem}", False):
                st.warning(f"⚠️ Delete {item.stem}? This cannot be undone.")
                del_col1, del_col2 = st.columns(2)
                with del_col1:
                    if st.button("✅ Yes, Delete", key=f"confirm_yes_{item.stem}", type="primary"):
                        delete_library_item(item)
                        st.session_state[f"confirm_delete_{item.stem}"] = False
                        st.rerun()
                with del_col2:
                    if st.button("❌ Cancel", key=f"confirm_no_{item.stem}"):
                        st.session_state[f"confirm_delete_{item.stem}"] = False
                        st.rerun()
            
            st.markdown("---")


def render_library_grid(items: List[LibraryItem]):
    """Render library items in grid view"""
    # Show 3 items per row
    num_cols = 3
    rows = [items[i:i+num_cols] for i in range(0, len(items), num_cols)]
    
    for row in rows:
        cols = st.columns(num_cols)
        for idx, item in enumerate(row):
            with cols[idx]:
                # Card container
                st.markdown(f"""
                <div style="border: 1px solid #e0e0e0; border-radius: 10px; padding: 15px; height: 280px;">
                    <h4 style="margin-bottom: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        {item.stem}
                    </h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Status icons
                status = []
                if item.has_video:
                    status.append("🎬")
                if item.has_audio:
                    status.append("🎵")
                if item.has_transcript:
                    status.append("📝")
                st.markdown(f"**Status**: {''.join(status)}")
                
                # Size and rating
                st.markdown(f"**Size**: {item.total_size_mb:.1f} MB")
                if item.rating > 0:
                    st.markdown(f"**Rating**: {'★' * item.rating}")
                
                # Tags
                if item.tags:
                    st.markdown(f"**Tags**: {', '.join(item.tags[:2])}")
                
                # Action buttons
                if item.has_transcript:
                    if st.button("👁️ View", key=f"grid_view_{item.stem}", use_container_width=True):
                        st.session_state.selected_transcript = item.stem
                        st.session_state.view = "transcript"
                        st.rerun()
                
                if st.button("⚙️ Manage", key=f"grid_manage_{item.stem}", use_container_width=True):
                    # Switch to list view for management
                    st.session_state[f"show_tags_{item.stem}"] = True
                    st.rerun()


# ============================================================================
# LIBRARY VIEW
# ============================================================================

def render_library_view():
    """Render enhanced library with search, filter, and sorting"""
    st.markdown("## 📚 Your Library")
    
    # Get all library items
    all_items = get_all_library_items()
    
    if not all_items:
        st.info("Your library is empty. Process a video to get started!")
        return
    
    # Search and Filter UI
    st.markdown("### 🔍 Search & Filter")
    
    col_search, col_sort, col_view = st.columns([3, 2, 1])
    
    with col_search:
        search_query = st.text_input("🔎 Search", 
                                     placeholder="Search by name, tags, or content...",
                                     key="library_search")
    
    with col_sort:
        sort_options = {
            "Name (A-Z)": ("name", False),
            "Name (Z-A)": ("name", True),
            "Newest First": ("date_modified", True),
            "Oldest First": ("date_modified", False),
            "Largest First": ("size", True),
            "Smallest First": ("size", False),
            "Highest Rated": ("rating", True),
            "Lowest Rated": ("rating", False)
        }
        sort_choice = st.selectbox("📊 Sort by", list(sort_options.keys()))
        sort_by, sort_reverse = sort_options[sort_choice]
    
    with col_view:
        view_mode = st.selectbox("👁️ View", ["List", "Grid"], label_visibility="collapsed")
    
    # Advanced filters in expander
    with st.expander("🎛️ Advanced Filters"):
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            filter_complete = st.checkbox("✅ Complete only", value=False)
            filter_has_video = st.checkbox("🎬 Has video", value=False)
        
        with filter_col2:
            filter_has_audio = st.checkbox("🎵 Has audio", value=False)
            filter_has_transcript = st.checkbox("📝 Has transcript", value=False)
        
        with filter_col3:
            min_rating = st.slider("⭐ Min rating", 0, 5, 0)
            
        # Tag filter
        all_tags = get_all_tags()
        if all_tags:
            selected_tags = st.multiselect("🏷️ Filter by tags", all_tags)
        else:
            selected_tags = []
    
    # Apply search
    if search_query:
        filtered_items = search_library(search_query, all_items)
    else:
        filtered_items = all_items
    
    # Apply filters
    filtered_items = filter_library(
        filtered_items,
        has_video=True if filter_has_video else None,
        has_audio=True if filter_has_audio else None,
        has_transcript=True if filter_has_transcript else None,
        is_complete=True if filter_complete else None,
        min_rating=min_rating if min_rating > 0 else None,
        tags=selected_tags if selected_tags else None
    )
    
    # Apply sorting
    filtered_items = sort_library(filtered_items, sort_by, sort_reverse)
    
    # Show results count
    st.markdown(f"**Showing {len(filtered_items)} of {len(all_items)} items**")
    
    tabs = st.tabs(["📚 All Items", "🎬 Videos", "📝 Transcripts", "🎵 Audio"])
    
    with tabs[0]:
        # All Items tab - enhanced view
        if not filtered_items:
            st.info("No items match your search/filter criteria")
        else:
            # Display items based on view mode
            if view_mode == "List":
                render_library_list(filtered_items)
            else:
                render_library_grid(filtered_items)
    
    with tabs[1]:
        # Videos tab - keep original functionality
        videos = list(VIDEOS.glob("*.mp4"))
        if videos:
            st.markdown(f"**{len(videos)}** videos in library")
            
            # Initialize selected video in session state if not present
            if "selected_library_video" not in st.session_state:
                st.session_state.selected_library_video = videos[0].name if videos else None
            
            # Video player section
            if st.session_state.selected_library_video:
                video_path = VIDEOS / st.session_state.selected_library_video
                if video_path.exists():
                    st.markdown("### 🎬 Now Playing")
                    st.markdown(f"**{st.session_state.selected_library_video}**")
                    try:
                        st.video(str(video_path))
                    except Exception as e:
                        st.error(f"Error playing video: {e}")
            
            st.markdown("---")
            st.markdown("### 📋 All Videos")
            
            for video in videos:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    with col1:
                        st.write(f"📹 {video.name}")
                    with col2:
                        st.write(f"{video.stat().st_size / (1024*1024):.1f} MB")
                    with col3:
                        if st.button("▶️", key=f"play_v_{video.name}", help="Play this video"):
                            st.session_state.selected_library_video = video.name
                            st.rerun()
                    with col4:
                        if st.button("🗑️", key=f"del_v_{video.name}", help="Delete this video"):
                            video.unlink()
                            st.rerun()
        else:
            st.info("No videos in library")
    
    with tabs[1]:
        transcripts = list(TRANSCRIPTS.glob("*.txt"))
        if transcripts:
            col_header1, col_header2 = st.columns([3, 1])
            with col_header1:
                st.markdown(f"**{len(transcripts)}** transcripts in library")
            with col_header2:
                if st.button("🔄 Batch Index All", help="Index all transcripts for semantic search"):
                    with st.spinner("Indexing all transcripts..."):
                        results = batch_index_all()
                        st.success(f"✅ Indexed: {results['indexed']}, Skipped: {results['skipped']}, Failed: {results['failed']}")
                        if results['errors']:
                            with st.expander("⚠️ Errors"):
                                for err in results['errors']:
                                    st.error(err)
                        st.rerun()
            
            st.markdown("---")
            
            for transcript in transcripts:
                # Check index status
                indexed = is_indexed(transcript.stem)
                
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                    with col1:
                        st.write(f"📝 {transcript.name}")
                        if indexed:
                            st.markdown('<span style="color: #48bb78; font-size: 0.8em;">● Indexed</span>', 
                                       unsafe_allow_html=True)
                        else:
                            st.markdown('<span style="color: #ed8936; font-size: 0.8em;">○ Not indexed</span>', 
                                       unsafe_allow_html=True)
                    with col2:
                        if st.button("👁️", key=f"view_t_{transcript.name}", help="View transcript"):
                            st.session_state.selected_transcript = transcript.stem
                            st.session_state.view = "transcript"
                            st.rerun()
                    with col3:
                        if not indexed:
                            if st.button("🔍", key=f"idx_t_{transcript.name}", help="Index for search"):
                                try:
                                    content = transcript.read_text(encoding="utf-8")
                                    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                                    segments = []
                                    current_time = 0.0
                                    for para in paragraphs:
                                        sentences = para.count(".") + para.count("!") + para.count("?")
                                        duration = max(2.0, sentences * 2.0)
                                        segments.append(Segment(start=current_time, end=current_time + duration, text=para))
                                        current_time += duration
                                    if not segments:
                                        segments = [Segment(start=0.0, end=0.0, text=content)]
                                    t = Transcript(text=content, segments=segments)
                                    build_index(transcript.stem, t)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Indexing failed: {e}")
                    with col4:
                        content = transcript.read_text(encoding="utf-8")
                        st.download_button("📥", content, transcript.name, 
                                         key=f"dl_t_{transcript.name}", help="Download transcript")
                    with col5:
                        if st.button("🗑️", key=f"del_t_{transcript.name}", help="Delete transcript"):
                            transcript.unlink()
                            # Also delete index if exists
                            if indexed:
                                delete_index(transcript.stem)
                            st.rerun()
        else:
            st.info("No transcripts in library")
    
    with tabs[2]:
        audios = list(AUDIO.glob("*.wav"))
        if audios:
            st.markdown(f"**{len(audios)}** audio files in library")
            
            # Initialize selected audio in session state if not present
            if "selected_library_audio" not in st.session_state:
                st.session_state.selected_library_audio = audios[0].name if audios else None
            
            # Audio player section
            if st.session_state.selected_library_audio:
                audio_path = AUDIO / st.session_state.selected_library_audio
                if audio_path.exists():
                    st.markdown("### 🎵 Now Playing")
                    st.markdown(f"**{st.session_state.selected_library_audio}**")
                    try:
                        st.audio(str(audio_path))
                    except Exception as e:
                        st.error(f"Error playing audio: {e}")
            
            st.markdown("---")
            st.markdown("### 📋 All Audio Files")
            
            for audio in audios:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    with col1:
                        st.write(f"🎵 {audio.name}")
                    with col2:
                        st.write(f"{audio.stat().st_size / (1024*1024):.1f} MB")
                    with col3:
                        if st.button("▶️", key=f"play_a_{audio.name}", help="Play this audio"):
                            st.session_state.selected_library_audio = audio.name
                            st.rerun()
                    with col4:
                        if st.button("🗑️", key=f"del_a_{audio.name}", help="Delete this audio"):
                            audio.unlink()
                            st.rerun()
        else:
            st.info("No audio files in library")


# ============================================================================
# TRANSCRIPT VIEW
# ============================================================================

def render_transcript_view():
    """Render transcript detail view with summarization and advanced export"""
    selected = st.session_state.get("selected_transcript")
    if not selected:
        st.warning("No transcript selected")
        return
    
    transcript_path = TRANSCRIPTS / f"{selected}.txt"
    if not transcript_path.exists():
        st.error("Transcript not found")
        return
    
    st.markdown(f"## 📝 Transcript: {selected}")
    
    # Check if video exists for player tab
    video_path = VIDEOS / f"{selected}.mp4"
    has_video = video_path.exists()
    
    # Tabs for different views
    tab_names = ["🎬 Player" if has_video else "📄 Transcript", "📄 Full Text", "🤖 AI Summary", "📤 Export"]
    tabs = st.tabs(tab_names)
    
    content = transcript_path.read_text(encoding="utf-8")
    
    # Reconstruct transcript object
    if "_segments" in st.session_state:
        segs = st.session_state._segments
        segments = [Segment(start=s, end=e, text=txt) for s, e, txt in segs]
    else:
        segments = [Segment(start=0.0, end=0.0, text=content)]
    transcript_obj = Transcript(text=content, segments=segments)
    
    with tabs[0]:
        # Video Player with synchronized transcript
        if has_video:
            st.markdown("### 🎬 Video Player")
            
            col_video, col_transcript = st.columns([1, 1])
            
            with col_video:
                # Video player
                try:
                    st.video(str(video_path))
                except Exception as e:
                    st.error(f"Error loading video: {e}")
                
                # Playback controls info
                st.info("💡 Click on any timestamp in the transcript to jump to that moment")
            
            with col_transcript:
                st.markdown("### 📄 Interactive Transcript")
                
                # Initialize current time in session state
                if f"current_time_{selected}" not in st.session_state:
                    st.session_state[f"current_time_{selected}"] = 0.0
                
                # Manual time jump
                col_jump1, col_jump2 = st.columns([3, 1])
                with col_jump1:
                    time_input = st.text_input(
                        "Jump to time",
                        placeholder="00:00 or 1:23",
                        key=f"time_jump_{selected}"
                    )
                with col_jump2:
                    if st.button("⏩ Go", key=f"go_time_{selected}"):
                        if time_input:
                            jump_time = parse_timestamp(time_input)
                            st.session_state[f"current_time_{selected}"] = jump_time
                            st.info(f"⏩ Jump to {format_timestamp(jump_time)}")
                
                # Prepare segments for display
                seg_dicts = [
                    {"start": seg.start, "end": seg.end, "text": seg.text}
                    for seg in transcript_obj.segments
                ]
                
                # Find current segment
                current_time = st.session_state.get(f"current_time_{selected}", 0.0)
                current_seg_idx = find_current_segment(current_time, seg_dicts)
                
                # Segment navigation
                if len(seg_dicts) > 1:
                    st.markdown("**Navigation:**")
                    nav_col1, nav_col2, nav_col3 = st.columns(3)
                    
                    with nav_col1:
                        if current_seg_idx is not None and current_seg_idx > 0:
                            if st.button("⏮️ Previous Segment", use_container_width=True):
                                st.session_state[f"current_time_{selected}"] = seg_dicts[current_seg_idx - 1]["start"]
                                st.rerun()
                    
                    with nav_col2:
                        if current_seg_idx is not None:
                            st.markdown(f"<center>Segment {current_seg_idx + 1} / {len(seg_dicts)}</center>", 
                                       unsafe_allow_html=True)
                    
                    with nav_col3:
                        if current_seg_idx is not None and current_seg_idx < len(seg_dicts) - 1:
                            if st.button("Next Segment ⏭️", use_container_width=True):
                                st.session_state[f"current_time_{selected}"] = seg_dicts[current_seg_idx + 1]["start"]
                                st.rerun()
                
                st.markdown("---")
                
                # Display clickable transcript
                st.markdown("**Click on any segment to jump:**")
                
                # Create scrollable transcript container
                transcript_container = st.container()
                with transcript_container:
                    for idx, seg in enumerate(seg_dicts):
                        # Highlight current segment
                        is_current = idx == current_seg_idx
                        bg_color = "#ffd700" if is_current else "#f8f9fa"
                        border = "2px solid #3ea6ff" if is_current else "1px solid #e0e0e0"
                        
                        timestamp_str = format_timestamp(seg["start"])
                        
                        # Create clickable segment
                        segment_html = f"""
                        <div style="padding: 12px; margin: 8px 0; background-color: {bg_color}; 
                                    border: {border}; border-radius: 8px; cursor: pointer; 
                                    transition: all 0.3s;">
                            <span style="color: #3ea6ff; font-weight: bold; font-family: monospace; font-size: 14px;">
                                [{timestamp_str}]
                            </span>
                            <span style="margin-left: 10px; color: #333; line-height: 1.6;">
                                {seg["text"]}
                            </span>
                        </div>
                        """
                        
                        st.markdown(segment_html, unsafe_allow_html=True)
                        
                        # Make it clickable with a button (hidden visually, takes click)
                        if st.button(f"Jump to {timestamp_str}", 
                                    key=f"seg_{selected}_{idx}",
                                    help=f"Jump to {timestamp_str}",
                                    use_container_width=True):
                            st.session_state[f"current_time_{selected}"] = seg["start"]
                            st.rerun()
        else:
            # Fallback to simple transcript view
            st.info("Video file not found. Showing transcript only.")
            st.text_area("Transcript Content", content, height=600)
    
    with tabs[1]:
        # Full transcript view (text area)
        st.text_area("Transcript Content", content, height=600)
    
    with tabs[2]:
        # AI Summary section
        st.markdown("### 🤖 Generate AI Summary")
        
        col_a, col_b = st.columns([2, 1])
        
        with col_a:
            summary_style = st.selectbox(
                "Summary Style",
                ["comprehensive", "brief", "academic", "casual"],
                help="Choose the type of summary you want"
            )
        
        with col_b:
            ollama_model = st.text_input("Ollama Model", value="llama3.2")
        
        if st.button("✨ Generate Summary", type="primary", use_container_width=True):
            with st.spinner("Analyzing transcript with AI... This may take a minute..."):
                try:
                    # Generate full analysis
                    analysis = generate_full_analysis(
                        transcript_obj,
                        model=ollama_model,
                        style=summary_style
                    )
                    
                    # Store in session state
                    st.session_state[f"summary_{selected}"] = analysis
                    
                    st.success("✅ Summary generated!")
                    st.rerun()
                
                except Exception as e:
                    st.error(f"Summary generation failed: {e}")
                    st.info("Make sure Ollama is running and the model is available")
        
        # Display stored summary if available
        if f"summary_{selected}" in st.session_state:
            analysis = st.session_state[f"summary_{selected}"]
            
            # TL;DR
            if analysis["tldr"].get("success"):
                st.markdown("### ⚡ TL;DR")
                st.info(analysis["tldr"]["tldr"])
            
            # Key Points
            if analysis["key_points"].get("success"):
                st.markdown("### 🎯 Key Points")
                for i, point in enumerate(analysis["key_points"]["key_points"], 1):
                    st.markdown(f"{i}. {point}")
            
            # Topics
            if analysis["topics"].get("success"):
                st.markdown("### 📚 Topics Covered")
                for topic in analysis["topics"]["topics"]:
                    st.markdown(f"**{topic['name']}**: {topic['description']}")
            
            # Full Summary
            if analysis["summary"].get("success"):
                st.markdown("### 📝 Detailed Summary")
                st.write(analysis["summary"]["summary"])
    
    with tabs[3]:
        # Advanced export options
        st.markdown("### 📤 Export Options")
        
        # Get summary if available
        summary_data = st.session_state.get(f"summary_{selected}")
        
        include_summary = st.checkbox("Include AI Summary in exports", 
                                     value=summary_data is not None,
                                     disabled=summary_data is None)
        
        st.markdown("#### 📄 Document Formats")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📕 PDF", use_container_width=True):
                with st.spinner("Generating PDF..."):
                    try:
                        sum_data = summary_data if include_summary else None
                        pdf_path = export_to_pdf(transcript_obj, selected, sum_data)
                        st.success(f"✅ PDF saved: {pdf_path.name}")
                        
                        # Offer download
                        with open(pdf_path, 'rb') as f:
                            st.download_button(
                                "⬇️ Download PDF",
                                f.read(),
                                file_name=pdf_path.name,
                                mime="application/pdf",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"PDF export failed: {e}")
        
        with col2:
            if st.button("📘 Word (DOCX)", use_container_width=True):
                with st.spinner("Generating Word document..."):
                    try:
                        sum_data = summary_data if include_summary else None
                        docx_path = export_to_word(transcript_obj, selected, sum_data)
                        st.success(f"✅ DOCX saved: {docx_path.name}")
                        
                        with open(docx_path, 'rb') as f:
                            st.download_button(
                                "⬇️ Download DOCX",
                                f.read(),
                                file_name=docx_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"Word export failed: {e}")
        
        with col3:
            if st.button("📗 Markdown", use_container_width=True):
                with st.spinner("Generating Markdown..."):
                    try:
                        sum_data = summary_data if include_summary else None
                        md_path = export_to_markdown(transcript_obj, selected, sum_data)
                        st.success(f"✅ Markdown saved: {md_path.name}")
                        
                        md_content = md_path.read_text(encoding="utf-8")
                        st.download_button(
                            "⬇️ Download MD",
                            md_content,
                            file_name=md_path.name,
                            mime="text/markdown",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Markdown export failed: {e}")
        
        st.markdown("#### 📊 Data Formats")
        
        col4, col5 = st.columns(2)
        
        with col4:
            if st.button("📋 JSON", use_container_width=True):
                with st.spinner("Generating JSON..."):
                    try:
                        sum_data = summary_data if include_summary else None
                        json_path = export_to_json(transcript_obj, selected, sum_data)
                        st.success(f"✅ JSON saved: {json_path.name}")
                        
                        json_content = json_path.read_text(encoding="utf-8")
                        st.download_button(
                            "⬇️ Download JSON",
                            json_content,
                            file_name=json_path.name,
                            mime="application/json",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"JSON export failed: {e}")
        
        with col5:
            if st.button("🌐 Blog HTML", use_container_width=True):
                with st.spinner("Generating blog post..."):
                    try:
                        sum_data = summary_data if include_summary else None
                        html_path = export_blog_post(transcript_obj, selected, sum_data)
                        st.success(f"✅ Blog post saved: {html_path.name}")
                        
                        html_content = html_path.read_text(encoding="utf-8")
                        st.download_button(
                            "⬇️ Download HTML",
                            html_content,
                            file_name=html_path.name,
                            mime="text/html",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Blog export failed: {e}")
        
        st.markdown("#### 📺 Subtitle Formats")
        
        col6, col7 = st.columns(2)
        
        with col6:
            if st.button("📄 SRT", use_container_width=True):
                try:
                    srt_path = save_srt(transcript_obj, video_stem=selected)
                    st.success(f"✅ SRT saved: {srt_path.name}")
                    
                    srt_content = srt_path.read_text(encoding="utf-8")
                    st.download_button(
                        "⬇️ Download SRT",
                        srt_content,
                        file_name=srt_path.name,
                        mime="text/plain",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"SRT export failed: {e}")
        
        with col7:
            if st.button("📄 VTT", use_container_width=True):
                try:
                    vtt_path = save_vtt(transcript_obj, video_stem=selected)
                    st.success(f"✅ VTT saved: {vtt_path.name}")
                    
                    vtt_content = vtt_path.read_text(encoding="utf-8")
                    st.download_button(
                        "⬇️ Download VTT",
                        vtt_content,
                        file_name=vtt_path.name,
                        mime="text/vtt",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"VTT export failed: {e}")


# ============================================================================
# Q&A VIEW
# ============================================================================

def render_qa_view():
    """Render Q&A interface with chat-like UI"""
    st.markdown("## 💬 Ask Questions About Your Videos")
    
    # Select video
    transcripts = list(TRANSCRIPTS.glob("*.txt"))
    if not transcripts:
        st.info("No transcripts available. Process a video first.")
        return
    
    # Show indexed vs non-indexed
    indexed_videos = get_indexed_videos()
    indexed_count = len(indexed_videos)
    total_count = len(transcripts)
    
    st.markdown(f"**Semantic Search Status**: {indexed_count}/{total_count} videos indexed")
    
    # Video selection with index indicator
    video_options = []
    for t in transcripts:
        stem = t.stem
        if stem in indexed_videos:
            video_options.append(f"✅ {stem}")
        else:
            video_options.append(f"○ {stem}")
    
    selected_display = st.selectbox("Select video", video_options)
    selected_video = selected_display.replace("✅ ", "").replace("○ ", "")
    
    # Check if selected video is indexed
    video_indexed = is_indexed(selected_video)
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Build index button
        if not video_indexed:
            if st.button("🔍 Index This Video", use_container_width=True, type="primary"):
                try:
                    with st.spinner("Building search index..."):
                        # Load transcript
                        transcript_path = TRANSCRIPTS / f"{selected_video}.txt"
                        content = transcript_path.read_text(encoding="utf-8")
                        
                        # Create proper segments
                        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                        segments = []
                        current_time = 0.0
                        for para in paragraphs:
                            sentences = para.count(".") + para.count("!") + para.count("?")
                            duration = max(2.0, sentences * 2.0)
                            segments.append(Segment(start=current_time, end=current_time + duration, text=para))
                            current_time += duration
                        if not segments:
                            segments = [Segment(start=0.0, end=0.0, text=content)]
                        
                        t = Transcript(text=content, segments=segments)
                        n = build_index(selected_video, t)
                        st.success(f"✅ Indexed {n} chunks")
                        st.rerun()
                except Exception as e:
                    st.error(f"Indexing failed: {e}")
        else:
            # Show index stats
            stats = get_index_stats(selected_video)
            st.info(f"✅ Indexed: {stats.get('chunk_count', 0)} chunks | Semantic search enabled")
            if st.button("🔄 Rebuild Index", use_container_width=True):
                try:
                    with st.spinner("Rebuilding index..."):
                        transcript_path = TRANSCRIPTS / f"{selected_video}.txt"
                        content = transcript_path.read_text(encoding="utf-8")
                        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                        segments = []
                        current_time = 0.0
                        for para in paragraphs:
                            sentences = para.count(".") + para.count("!") + para.count("?")
                            duration = max(2.0, sentences * 2.0)
                            segments.append(Segment(start=current_time, end=current_time + duration, text=para))
                            current_time += duration
                        if not segments:
                            segments = [Segment(start=0.0, end=0.0, text=content)]
                        t = Transcript(text=content, segments=segments)
                        n = build_index(selected_video, t)
                        st.success(f"✅ Rebuilt index ({n} chunks)")
                        st.rerun()
                except Exception as e:
                    st.error(f"Rebuild failed: {e}")
    
    with col2:
        if st.button("🔄 Index All Videos", use_container_width=True):
            with st.spinner("Indexing all transcripts..."):
                results = batch_index_all()
                st.success(f"✅ Indexed: {results['indexed']}, Skipped: {results['skipped']}, Failed: {results['failed']}")
                if results['errors']:
                    with st.expander("⚠️ Errors"):
                        for err in results['errors']:
                            st.error(err)
                st.rerun()
    
    with col3:
        model = st.text_input("Model", value="llama3.2", placeholder="llama3.2")
    
    st.markdown("---")
    
    # Chat interface
    st.markdown("### 💭 Chat")
    
    question = st.text_input("Ask a question about the video", 
                            placeholder="What is this video about?")
    
    if st.button("Send", type="primary", disabled=not question):
        try:
            with st.spinner("Thinking..."):
                # Query index
                hits = query_index(selected_video, question, top_k=4)
                
                if not hits:
                    st.warning("No relevant content found")
                else:
                    # Build context
                    ctx = []
                    for i, h in enumerate(hits, 1):
                        ctx.append(f"[{i}] {h['text']}")
                    ctx_str = "\n\n".join(ctx)
                    
                    # Build prompt
                    prompt = f"""You are a helpful assistant. Answer this question based on the video transcript context below.

Question: {question}

Context:
{ctx_str}

Provide a concise, accurate answer."""
                    
                    # Get answer
                    answer = run_ollama(model=model, prompt=prompt)
                    
                    # Display chat
                    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
                    st.markdown(f'<div class="chat-message user">{question}</div>', 
                               unsafe_allow_html=True)
                    st.markdown(f'<div class="chat-message assistant">{answer}</div>', 
                               unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Show sources
                    with st.expander("📚 Sources"):
                        for i, h in enumerate(hits, 1):
                            st.write(f"**[{i}]** {h['text'][:200]}...")
        
        except Exception as e:
            st.error(f"Q&A failed: {e}")


# ============================================================================
# SETTINGS VIEW
# ============================================================================

def render_settings_view():
    """Render settings page"""
    st.markdown("## ⚙️ Settings")
    
    # Load current config
    config_mgr = get_config_manager()
    
    st.markdown("### 🎤 Transcription Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_idx = ["tiny", "base", "small", "medium", "large-v3"].index(
            st.session_state.get("model_size", "base")
        )
        model_size = st.selectbox(
            "Whisper Model",
            ["tiny", "base", "small", "medium", "large-v3"],
            index=current_idx
        )
        if model_size != st.session_state.model_size:
            st.session_state.model_size = model_size
            config_mgr.update_transcription(model_size=model_size)
        
        language = st.text_input("Language Code", 
                                value=st.session_state.get("language", "en"), 
                                help="ISO language code or 'auto'")
        if language != st.session_state.language:
            st.session_state.language = language
            config_mgr.update_transcription(language=language)
    
    with col2:
        fast_mode = st.checkbox("Fast Mode (CPU optimized)", 
                               value=st.session_state.get("fast_mode", True))
        if fast_mode != st.session_state.fast_mode:
            st.session_state.fast_mode = fast_mode
            config_mgr.update_transcription(fast_mode=fast_mode)
        
        vad_filter = st.checkbox("VAD Filter (skip silence)", 
                                value=st.session_state.get("vad_filter", False))
        if vad_filter != st.session_state.vad_filter:
            st.session_state.vad_filter = vad_filter
            config_mgr.update_transcription(vad_filter=vad_filter)
    
    st.markdown("---")
    
    st.markdown("### 🔍 Semantic Search Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        auto_index = st.checkbox("Auto-index after transcription", 
                                value=st.session_state.get("auto_index_enabled", True),
                                help="Automatically build search index when transcription completes")
        if auto_index != st.session_state.auto_index_enabled:
            st.session_state.auto_index_enabled = auto_index
            config_mgr.update_semantic_search(auto_index_enabled=auto_index)
        
        # Show index status
        indexed_videos = get_indexed_videos()
        transcripts = list(TRANSCRIPTS.glob("*.txt"))
        st.info(f"**Index Status**: {len(indexed_videos)}/{len(transcripts)} videos indexed")
    
    with col2:
        chunk_size = st.number_input("Chunk Size (words)", 
                                    min_value=50, max_value=500, 
                                    value=st.session_state.get("chunk_size", 200),
                                    help="Number of words per chunk for semantic search")
        if chunk_size != st.session_state.chunk_size:
            st.session_state.chunk_size = chunk_size
            config_mgr.update_semantic_search(chunk_size=chunk_size)
        
        overlap = st.number_input("Chunk Overlap (words)", 
                                 min_value=0, max_value=100, 
                                 value=st.session_state.get("chunk_overlap", 40),
                                 help="Word overlap between chunks for context preservation")
        if overlap != st.session_state.chunk_overlap:
            st.session_state.chunk_overlap = overlap
            config_mgr.update_semantic_search(chunk_overlap=overlap)
    
    # Batch operations
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 Rebuild All Indexes", use_container_width=True):
            with st.spinner("Rebuilding all indexes..."):
                results = batch_index_all(force_reindex=True)
                st.success(f"✅ Rebuilt: {results['indexed']}, Failed: {results['failed']}")
                if results['errors']:
                    with st.expander("⚠️ Errors"):
                        for err in results['errors']:
                            st.error(err)
    
    with col_b:
        if st.button("🗑️ Clear All Indexes", use_container_width=True):
            if st.session_state.get("confirm_clear_indexes", False):
                try:
                    import shutil
                    chroma_dir = DATA / "chroma"
                    if chroma_dir.exists():
                        shutil.rmtree(chroma_dir)
                        st.success("✅ All indexes cleared")
                        st.session_state.confirm_clear_indexes = False
                        st.rerun()
                except Exception as e:
                    st.error(f"Failed to clear indexes: {e}")
            else:
                st.session_state.confirm_clear_indexes = True
                st.warning("Click again to confirm deletion")
    
    st.markdown("---")
    
    st.markdown("### 🤖 LLM Settings")
    
    ollama_path = st.text_input("Ollama Path (optional)", 
                               value=st.session_state.get("ollama_path", "") or "",
                               placeholder="Leave empty for auto-detect")
    ollama_path_value = ollama_path if ollama_path.strip() else None
    if ollama_path_value != st.session_state.ollama_path:
        st.session_state.ollama_path = ollama_path_value
        config_mgr.update_llm(ollama_path=ollama_path_value)
    
    ollama_model = st.text_input("Default Ollama Model", 
                                value=st.session_state.get("ollama_model", "llama3.2"),
                                help="Model to use for summaries and Q&A")
    if ollama_model != st.session_state.ollama_model:
        st.session_state.ollama_model = ollama_model
        config_mgr.update_llm(default_model=ollama_model)
    
    st.markdown("---")
    
    st.markdown("### 📁 Data Directories")
    st.write(f"**Videos:** `{VIDEOS}`")
    st.write(f"**Audio:** `{AUDIO}`")
    st.write(f"**Transcripts:** `{TRANSCRIPTS}`")
    st.write(f"**ChromaDB:** `{DATA / 'chroma'}`")
    st.write(f"**Config:** `{DATA / 'config.json'}`")
    
    if st.button("📂 Open Data Folder"):
        import subprocess
        subprocess.Popen(f'explorer "{VIDEOS.parent}"')
    
    st.markdown("---")
    
    st.markdown("### 📊 Logs & Error Tracking")
    
    # Import logger and error tracker
    from ..logger import error_tracker, LOG_DIR, MAIN_LOG, ERROR_LOG, PERFORMANCE_LOG
    
    # Tabs for different log views
    log_tabs = st.tabs(["📋 Recent Errors", "📈 Performance Metrics", "🔧 All Logs"])
    
    with log_tabs[0]:
        st.markdown("#### Recent Errors")
        recent_errors = error_tracker.get_recent_errors(10)
        
        if not recent_errors:
            st.success("✅ No errors logged yet!")
        else:
            error_summary = error_tracker.get_error_summary()
            st.metric("Total Errors", error_summary['total'])
            
            # Show recent errors
            for idx, err in enumerate(reversed(recent_errors), 1):
                with st.expander(f"❌ {err['type']} - {err['timestamp'][:19]}", expanded=(idx==1)):
                    st.write(f"**Module:** `{err.get('module', 'Unknown')}`")
                    st.write(f"**Function:** `{err.get('function', 'Unknown')}`")
                    st.write(f"**Context:** {err.get('context', 'N/A')}")
                    st.write(f"**Message:** {err.get('message', 'N/A')}")
                    if err.get('user_message'):
                        st.info(f"**User Message:** {err['user_message']}")
                    if err.get('traceback'):
                        with st.expander("🔍 View Traceback"):
                            st.code(err['traceback'], language='python')
    
    with log_tabs[1]:
        st.markdown("#### Performance Metrics")
        if PERFORMANCE_LOG.exists():
            try:
                # Read last 20 performance entries
                with open(PERFORMANCE_LOG, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-20:]
                
                if lines:
                    import json
                    metrics = []
                    for line in lines:
                        try:
                            metrics.append(json.loads(line))
                        except:
                            continue
                    
                    if metrics:
                        # Group by operation
                        ops = {}
                        for m in metrics:
                            op = m.get('operation', 'unknown')
                            if op not in ops:
                                ops[op] = []
                            ops[op].append(m)
                        
                        # Show metrics per operation
                        for op, entries in ops.items():
                            durations = [e['duration_seconds'] for e in entries]
                            successes = sum(1 for e in entries if e.get('success', True))
                            
                            col1, col2, col3 = st.columns(3)
                            col1.metric(f"**{op}**", f"{len(entries)} calls")
                            col2.metric("Avg Duration", f"{sum(durations)/len(durations):.2f}s")
                            col3.metric("Success Rate", f"{successes}/{len(entries)}")
                        
                        # Show recent entries
                        with st.expander("📊 Recent Performance Entries"):
                            for m in reversed(metrics[-10:]):
                                status = "✅" if m.get('success', True) else "❌"
                                st.text(f"{status} {m['operation']}: {m['duration_seconds']:.2f}s - {m['timestamp'][:19]}")
                    else:
                        st.info("No performance metrics available yet")
                else:
                    st.info("No performance metrics logged yet")
            except Exception as e:
                st.error(f"Failed to read performance log: {e}")
        else:
            st.info("Performance log not created yet")
    
    with log_tabs[2]:
        st.markdown("#### Application Logs")
        
        col1, col2 = st.columns(2)
        
        with col1:
            log_type = st.selectbox("Select Log File", ["Main Log", "Error Log", "Performance Log"])
        
        with col2:
            num_lines = st.number_input("Lines to show", min_value=10, max_value=500, value=50, step=10)
        
        # Map selection to file
        log_files = {
            "Main Log": MAIN_LOG,
            "Error Log": ERROR_LOG,
            "Performance Log": PERFORMANCE_LOG
        }
        
        selected_log = log_files[log_type]
        
        if selected_log.exists():
            try:
                with open(selected_log, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-num_lines:]
                
                if lines:
                    st.text_area("Log Content", "".join(lines), height=400)
                    
                    # Download button
                    log_content = "".join(lines)
                    st.download_button(
                        f"⬇️ Download {log_type}",
                        data=log_content,
                        file_name=selected_log.name,
                        mime="text/plain"
                    )
                else:
                    st.info("Log file is empty")
            except Exception as e:
                st.error(f"Failed to read log file: {e}")
        else:
            st.warning(f"Log file not created yet: `{selected_log}`")
        
        # Clear logs button
        if st.button("🗑️ Clear All Logs"):
            if st.session_state.get("confirm_clear_logs", False):
                try:
                    from ..logger import clear_old_logs
                    # Delete all logs
                    for log_file in LOG_DIR.glob("*.log"):
                        log_file.unlink()
                    for log_file in LOG_DIR.glob("*.json"):
                        log_file.unlink()
                    st.success("✅ All logs cleared")
                    st.session_state.confirm_clear_logs = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to clear logs: {e}")
            else:
                st.session_state.confirm_clear_logs = True
                st.warning("⚠️ Click again to confirm deletion of all logs")
    
    st.info(f"**Logs Directory:** `{LOG_DIR}`")
    
    st.markdown("---")
    
    st.markdown("### 💾 Configuration Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📤 Export Config", use_container_width=True):
            try:
                export_path = DATA / f"config_backup_{Path(__file__).stem}.json"
                if config_mgr.export_config(export_path):
                    with open(export_path, 'r') as f:
                        config_data = f.read()
                    st.download_button(
                        "⬇️ Download Config",
                        data=config_data,
                        file_name="freetube_config.json",
                        mime="application/json"
                    )
            except Exception as e:
                st.error(f"Export failed: {e}")
    
    with col2:
        uploaded_file = st.file_uploader("📥 Import Config", type=['json'], key="import_config")
        if uploaded_file is not None:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = Path(tmp.name)
                if config_mgr.import_config(tmp_path):
                    st.success("✅ Config imported successfully")
                    st.rerun()
                else:
                    st.error("Failed to import config")
                tmp_path.unlink()
            except Exception as e:
                st.error(f"Import failed: {e}")
    
    with col3:
        if st.button("🔄 Reset to Defaults", use_container_width=True):
            if st.session_state.get("confirm_reset_config", False):
                config_mgr.reset_to_defaults()
                st.success("✅ Settings reset to defaults")
                st.session_state.confirm_reset_config = False
                st.rerun()
            else:
                st.session_state.confirm_reset_config = True
                st.warning("Click again to confirm reset")
    
    # Show config file location
    st.info(f"**Settings are automatically saved to**: `{config_mgr.config_path}`")


# ============================================================================
# ANALYTICS VIEW
# ============================================================================

def render_analytics_view():
    """Render analytics dashboard with insights and charts"""
    st.markdown("## 📊 Analytics & Insights")
    
    try:
        # Get library stats
        stats = get_library_stats()
        
        # Top metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Videos", stats["video_count"])
            st.metric("Storage (Videos)", f"{stats['total_video_size_mb']:.1f} MB")
        
        with col2:
            st.metric("Transcripts", stats["transcript_count"])
            st.metric("Total Words", f"{stats['total_words']:,}")
        
        with col3:
            st.metric("Audio Files", stats["audio_count"])
            st.metric("Avg Words/Trans", f"{stats['avg_words_per_transcript']:.0f}")
        
        with col4:
            st.metric("Total Storage", f"{stats['total_size_mb']:.1f} MB")
            
        st.markdown("---")
        
        # Activity tabs
        tabs = st.tabs(["📈 Activity", "🔤 Word Analysis", "📋 File Details"])
        
        with tabs[0]:
            st.markdown("### 📅 Recent Activity")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                activity_7d = get_activity_summary(7)
                st.markdown("#### Last 7 Days")
                st.metric("Videos Processed", activity_7d["total_processed"])
                st.metric("Avg per Day", f"{activity_7d['avg_per_day']:.1f}")
                
                if activity_7d["recent_items"]:
                    st.markdown("**Recent:**")
                    for item in activity_7d["recent_items"][:5]:
                        st.write(f"• {item['name']} ({item['date']})")
            
            with col_b:
                activity_30d = get_activity_summary(30)
                st.markdown("#### Last 30 Days")
                st.metric("Videos Processed", activity_30d["total_processed"])
                st.metric("Avg per Day", f"{activity_30d['avg_per_day']:.1f}")
                
                # Daily activity chart
                if activity_30d["daily_activity"]:
                    import pandas as pd
                    import plotly.express as px
                    
                    df = pd.DataFrame(list(activity_30d["daily_activity"].items()), 
                                     columns=["Date", "Count"])
                    fig = px.bar(df, x="Date", y="Count", title="Daily Processing Activity")
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
        
        with tabs[1]:
            st.markdown("### 🔤 Word Frequency Analysis")
            
            # Select transcript for analysis
            transcripts = list(TRANSCRIPTS.glob("*.txt"))
            if transcripts:
                selected = st.selectbox("Select transcript to analyze", 
                                       [t.stem for t in transcripts])
                
                if selected:
                    transcript_path = TRANSCRIPTS / f"{selected}.txt"
                    content = transcript_path.read_text(encoding="utf-8")
                    
                    # Analyze
                    analysis = analyze_transcript(content)
                    
                    # Metrics
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Words", f"{analysis['word_count']:,}")
                    col2.metric("Unique Words", f"{analysis['unique_word_count']:,}")
                    col3.metric("Sentences", analysis['sentence_count'])
                    col4.metric("Vocab Richness", f"{analysis['vocabulary_richness']:.2%}")
                    
                    st.markdown("---")
                    
                    # Word frequency chart
                    freq_data = generate_word_frequency_data(content, 30)
                    
                    import pandas as pd
                    import plotly.express as px
                    
                    df = pd.DataFrame({
                        "Word": freq_data["words"],
                        "Count": freq_data["counts"]
                    })
                    
                    fig = px.bar(df, x="Count", y="Word", orientation='h',
                                title=f"Top 30 Words in {selected}",
                                labels={"Count": "Frequency", "Word": ""})
                    fig.update_layout(height=600, yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Try word cloud if available
                    try:
                        from wordcloud import WordCloud
                        import matplotlib.pyplot as plt
                        
                        st.markdown("### ☁️ Word Cloud")
                        wordcloud = WordCloud(width=800, height=400, 
                                            background_color='#0f0f0f',
                                            colormap='RdYlBu').generate(content)
                        
                        fig, ax = plt.subplots(figsize=(10, 5))
                        ax.imshow(wordcloud, interpolation='bilinear')
                        ax.axis('off')
                        st.pyplot(fig)
                        
                    except ImportError:
                        st.info("Install wordcloud for visual word clouds: pip install wordcloud")
            else:
                st.info("No transcripts available for analysis")
        
        with tabs[2]:
            st.markdown("### 📋 File Details")
            
            # Video files
            if stats["videos"]:
                st.markdown("#### Videos")
                import pandas as pd
                df = pd.DataFrame(stats["videos"])
                df = df.sort_values("size_mb", ascending=False)
                st.dataframe(df, use_container_width=True)
                
                # Size distribution
                import plotly.express as px
                fig = px.pie(df, values="size_mb", names="name", 
                           title="Video Storage Distribution")
                st.plotly_chart(fig, use_container_width=True)
            
            # Transcript files
            if stats["transcripts"]:
                st.markdown("#### Transcripts")
                df_t = pd.DataFrame(stats["transcripts"])
                df_t = df_t.sort_values("size_kb", ascending=False)
                st.dataframe(df_t, use_container_width=True)
        
        st.markdown("---")
        
        # Export analytics report
        if st.button("📥 Export Analytics Report (JSON)", use_container_width=True):
            try:
                report_path = export_analytics_report()
                st.success(f"Report exported: {report_path.name}")
                
                # Offer download
                with open(report_path, 'r') as f:
                    st.download_button(
                        "Download Report",
                        f.read(),
                        file_name=report_path.name,
                        mime="application/json"
                    )
            except Exception as e:
                st.error(f"Export failed: {e}")
    
    except Exception as e:
        st.error(f"Analytics error: {e}")
        st.info("Make sure you have processed some videos first!")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application router"""
    
    # Render top navigation
    render_top_nav()
    
    st.markdown("---")
    
    # Route to appropriate view
    view = st.session_state.view
    
    if view == "home":
        render_home_view()
    elif view == "search":
        render_search_view()
    elif view == "video":
        render_video_view()
    elif view == "library":
        render_library_view()
    elif view == "transcript":
        render_transcript_view()
    elif view == "qa":
        render_qa_view()
    elif view == "analytics":
        render_analytics_view()
    elif view == "settings":
        render_settings_view()
    else:
        render_home_view()


if __name__ == "__main__":
    main()

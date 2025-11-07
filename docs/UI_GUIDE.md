# FreeTube-Agent UI Guide

## YouTube-Inspired Interface

The FreeTube-Agent now features a modern, YouTube-inspired user interface designed for an intuitive and familiar experience.

## Key Features

### 🎨 **Design**
- **Dark Theme**: YouTube-style dark color scheme (customizable)
- **Clean Layout**: Minimalist design with focus on content
- **Responsive Grid**: Video cards display in a 3-column grid
- **Modern Typography**: Clear, readable fonts matching YouTube's style
- **Smooth Animations**: Hover effects and transitions for better UX

### 🧭 **Navigation**

#### Top Navigation Bar
- **Logo**: FreeTube-Agent branding (🎥)
- **Search Bar**: Center-aligned YouTube-style search
- **Quick Actions**: Home (🏠), Library (📚), Settings (⚙️)

### 📱 **Views**

#### 1. **Home View** (`🏠`)
The landing page with:
- **Quick Stats**: Dashboard showing processed videos, transcripts, audio files
- **Quick Actions**: 
  - Search & Download videos
  - View saved transcripts
  - Access Q&A interface
- **Recent Activity**: Track your processing history

#### 2. **Search Results** (`🔍`)
YouTube-style video grid displaying:
- **Video Cards** with:
  - Thumbnail image
  - Video title (2-line truncation)
  - Channel name
  - Duration badge
  - Download and Process buttons
- **Grid Layout**: 3 columns, responsive
- **Hover Effects**: Cards lift on hover

#### 3. **Video Processing View** (`🎬`)
Split-screen layout:
- **Left Panel**:
  - Video title and metadata
  - Thumbnail preview
  - Processing pipeline controls (Download → Extract → Transcribe)
  - Status indicators for each step
- **Right Panel**:
  - Live transcript display
  - Segment-based timeline
  - Clickable timestamps

#### 4. **Library View** (`📚`)
Manage your content with tabs:
- **Videos Tab**: Browse downloaded videos with file sizes
- **Transcripts Tab**: View, download, or delete transcripts
- **Audio Tab**: Manage extracted audio files
- **Quick Actions**: View, download, or delete files

#### 5. **Transcript Detail View** (`📝`)
Focused transcript reading:
- **Full Text Display**: Large text area for comfortable reading
- **Export Options**:
  - SRT format (SubRip subtitles)
  - VTT format (WebVTT)
  - TXT download
- **Search Within**: Find specific content (planned)

#### 6. **Q&A View** (`💬`)
Chat-like interface for video Q&A:
- **Video Selection**: Choose from processed videos
- **Index Builder**: Create/refresh semantic index
- **Chat Interface**: YouTube-comment-style Q&A
- **Source Citations**: View relevant transcript chunks
- **Ollama Integration**: Local LLM powered responses

#### 7. **Settings View** (`⚙️`)
Configure your experience:
- **Transcription Settings**:
  - Whisper model selection (tiny → large-v3)
  - Language code
  - Fast mode toggle
  - VAD filter
- **LLM Settings**:
  - Ollama path configuration
  - Model selection
- **Data Paths**: View storage locations

## 🎯 **UI Components**

### Video Cards
```
┌─────────────────────────┐
│     [Thumbnail]         │
│     Duration: 10:30     │
├─────────────────────────┤
│ Video Title (2 lines)   │
│ Channel Name            │
│ [Download] [Process]    │
└─────────────────────────┘
```

### Status Badges
- **✅ Success**: Green background
- **⏳ Pending**: Gray background
- **❌ Error**: Red background
- **🔄 Processing**: Blue background

### Transcript Segments
```
┌─────────────────────────┐
│ 00:15 - 00:23          │
│ Segment text content    │
└─────────────────────────┘
```

### Chat Messages
```
User: [Your question]
Assistant: [AI response with citations]
```

## 🎨 **Color Scheme**

Based on YouTube's design language:
- **Primary Red**: `#FF0000` (YouTube red)
- **Dark Background**: `#0f0f0f`
- **Card Background**: `#1f1f1f`
- **Hover Background**: `#272727`
- **Primary Text**: `#f1f1f1`
- **Secondary Text**: `#aaaaaa`
- **Accent Blue**: `#3ea6ff`
- **Border**: `#303030`

## 🚀 **Usage Flow**

### Typical Workflow:

1. **Search for Video**
   - Enter query in top search bar
   - Browse results in grid view
   - Click "Download" or "Process"

2. **Process Video**
   - Automatic: Download → Extract → Transcribe
   - Or manual step-by-step control
   - View real-time status updates

3. **Review Transcript**
   - Read in sidebar or dedicated view
   - Export in multiple formats
   - Navigate with timestamps

4. **Ask Questions**
   - Build semantic index
   - Ask natural language questions
   - Get AI-powered answers with citations

5. **Manage Library**
   - Browse processed content
   - Delete old files
   - Download transcripts

## 📋 **Keyboard Shortcuts** (Planned)
- `Ctrl+K`: Focus search bar
- `Ctrl+H`: Go to home
- `Ctrl+L`: Open library
- `Escape`: Clear selection

## 🔄 **State Management**

The app uses Streamlit's session state to track:
- **Current view**: Which page is displayed
- **Search results**: Cached video data
- **Current video**: Selected video details
- **Processing status**: Pipeline progress
- **Transcript data**: Segments and text
- **Settings**: User preferences

## 🎬 **Animations & Transitions**

- **Hover Effects**: 
  - Cards lift 4px on hover
  - Buttons show subtle shadow
- **Progress Bars**: 
  - YouTube-red color
  - Smooth transitions
- **Status Updates**: 
  - Toast notifications
  - Status badge changes

## 🔧 **Customization**

The UI can be customized by editing:
- `styles/youtube.css`: All visual styling
- CSS variables in `:root` for theme colors
- Component functions for layout changes

## 📱 **Responsive Design**

- **Desktop**: Full 3-column grid
- **Tablet**: 2-column grid (automatic)
- **Mobile**: Single column (automatic)

Note: Streamlit has limited mobile support, but the grid adapts automatically.

## 🐛 **Troubleshooting**

### CSS Not Loading
- Ensure `styles/youtube.css` exists
- Check file path in `app.py` load_css()
- Clear browser cache

### Layout Issues
- Try different browser (Chrome recommended)
- Check Streamlit version (1.38.0)
- Disable browser extensions

### Search Not Working
- Check internet connection
- Verify YouTube search dependencies
- Check error messages in logs

## 🎯 **Future Enhancements**

Planned UI improvements:
- ✅ Dark mode (implemented)
- 🔄 Light mode toggle
- 🔄 Timeline scrubber for video navigation
- 🔄 Inline video player
- 🔄 Drag-and-drop URL input
- 🔄 Batch processing queue
- 🔄 Advanced search filters
- 🔄 Custom color themes
- 🔄 Keyboard shortcuts
- 🔄 Accessibility improvements

## 📖 **Related Documentation**

- [Architecture Guide](architecture.md) - System overview
- [README](../README.md) - Setup and installation
- [API Reference](architecture.md#module-api-reference) - Module details

---

**Enjoy your YouTube-inspired FreeTube-Agent experience!** 🎥✨

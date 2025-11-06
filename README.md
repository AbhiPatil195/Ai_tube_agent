FreeTube-Agent (Local, Free Video Intelligence)

Fully local, free video analysis tool built with Python + Streamlit. It downloads videos, extracts audio, transcribes with Faster‑Whisper, and prepares for vision, OCR, semantic search, and local LLM reasoning (Ollama).

Features (initial)
- YouTube download via `pytube`.
- Robust fallback via `yt-dlp` when `pytube` fails.
- Audio extraction via `ffmpeg-python` (requires FFmpeg binary installed on PATH).
- Local transcription via `faster-whisper` (CPU or GPU).
- Simple Streamlit UI to run the pipeline.
- In‑app YouTube search tab and transcript export (SRT/VTT).
 - Q&A (local RAG): ChromaDB index + Ollama model answers with citations.

Planned (free-only)
- Frame captions (BLIP2/CLIP) via `transformers`.
- OCR via `easyocr`.
- ChromaDB semantic search over transcript.
- Local LLM (Ollama) for Q&A and summaries.

Requirements
- Windows with Python 3.10+ (recommended).
- FFmpeg installed and available on PATH.
- Optional GPU (CUDA) accelerates transcription and vision models.
- Ollama installed (for local LLM); run `ollama pull llama3.2` once.

If downloads fail with YouTube URL variations (shorts/youtu.be/playlist), the app normalizes links and falls back to `yt-dlp` automatically.

Setup (Offline-Friendly)
1) Create venv
   powershell
   py -3.10 -m venv .venv
   .venv\\Scripts\\Activate.ps1

2) Install dependencies (pinned for compatibility)
   pip install -r requirements.txt

3) FFmpeg
   - Not strictly required: the app bundles a user-space FFmpeg via `imageio-ffmpeg`.
   - Optional system install improves merges and performance:
     - Chocolatey (admin): `choco install ffmpeg`
     - Manual: download FFmpeg zip, extract, and add `bin/` to PATH

4) (Optional) Prepare Ollama
   - Install from https://ollama.ai
   - In a new terminal: `ollama pull llama3.2`

Run the Streamlit App
   streamlit run src/freetube_agent/ui/app.py

Data Paths
- Videos: `data/videos/`
- Audio: `data/audio/`
- Transcripts: `data/transcripts/`

Usage Tips
- Use the Search tab to find a video and send its URL to the Pipeline.
- In Pipeline, run Download → Extract → Transcribe.
- After transcription, use the Export tab to save SRT/VTT files.
 - Q&A tab: Build/Refresh Index, then ask questions. Set Ollama model (e.g., `llama3.2`) and optional Ollama path if not on PATH.

Ollama + RAG
- Install Ollama (https://ollama.ai) and pull a model (e.g., `ollama pull llama3.2`).
- For semantic search, the app uses ChromaDB + sentence-transformers (installed). First run may download an embedding model.

Notes
- Faster‑Whisper uses CTranslate2, not PyTorch, and runs fully local.
- Vision/OCR features are optional and load on demand.
- If `ollama` is not on PATH, add its installation folder to PATH or run via absolute path.

Architecture & Diagrams
- See `docs/architecture.md` for Mermaid component and sequence diagrams.

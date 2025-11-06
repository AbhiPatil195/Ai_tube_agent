import streamlit as st
from pathlib import Path

from freetube_agent.download import download_youtube
from freetube_agent.audio import extract_audio
from freetube_agent.transcribe import transcribe, save_transcript, Transcript
from freetube_agent.export import save_srt, save_vtt
from freetube_agent.paths import VIDEOS, AUDIO, TRANSCRIPTS
from freetube_agent.rag import build_index, query_index, format_time, chunk_transcript
from freetube_agent.llm import run_ollama
from freetube_agent.search import search_youtube


st.set_page_config(page_title="FreeTube-Agent", layout="wide")
st.title("FreeTube-Agent: Local Video Intelligence (Free)")

with st.sidebar:
    st.markdown("## Steps")
    model_size = st.selectbox("Whisper model", ["tiny", "base", "small", "medium", "large-v3"], index=1)
    st.markdown("### Speed/Quality")
    fast_mode = st.checkbox("Fast mode (CPU)", value=True)
    language = st.text_input("Language (ISO, blank=auto)", value="en")
    use_vad = st.checkbox("Skip silence (VAD)", value=False)
    word_ts = st.checkbox("Word timestamps", value=False)
    local_model_dir = st.text_input("Local Faster-Whisper model dir (optional)", value="", help="If set, use a local model folder to avoid network downloads (e.g., Systran/faster-whisper-base CTranslate2 files).")

tab_search, tab_pipeline, tab_timeline, tab_export, tab_qa = st.tabs(["Search", "Pipeline", "Timeline", "Export", "Q&A"]) 

with tab_search:
    st.subheader("Search YouTube")
    q = st.text_input("Query", placeholder="e.g., AI lecture 2024")
    if st.button("Search", disabled=not q):
        try:
            results = search_youtube(q, limit=8)
            if not results:
                st.info("No results.")
            for i, r in enumerate(results):
                with st.container(border=True):
                    st.write(f"{r['title']} — {r.get('channel','')} ({r.get('duration','?')})")
                    colA, colB = st.columns([3,1])
                    with colA:
                        st.write(r['url'])
                    with colB:
                        if st.button("Download", key=f"dl_{i}"):
                            st.session_state["pending_url"] = r['url']
                            with st.spinner("Downloading video..."):
                                try:
                                    vpath = download_youtube(r['url'], VIDEOS)
                                    st.session_state["video_path"] = str(vpath)
                                    st.success(f"Downloaded: {Path(vpath).name}")
                                    st.toast("Video ready. Proceed to Extract Audio in Pipeline tab.")
                                except Exception as e:
                                    st.error(f"Download failed: {e}")
        except Exception as e:
            st.error(f"Search failed: {e}")

with tab_pipeline:
    st.subheader("Pipeline")
    url_default = st.session_state.get("pending_url", "")
    url = st.text_input("YouTube URL", value=url_default, placeholder="https://www.youtube.com/watch?v=...")
    col1, col2, col3 = st.columns(3)
    if col1.button("Download Video", type="primary", disabled=not url):
        st.info("Downloading... progress will update below.")
        prog = st.progress(0)
        status = st.empty()
        def on_prog(d: dict):
            pct = d.get("percent")
            spd = d.get("speed")
            eta = d.get("eta")
            src = d.get("source")
            if pct is not None:
                try:
                    prog.progress(min(100, max(0, int(pct))))
                except Exception:
                    pass
            msg = f"{src}: {pct:.1f}%" if pct is not None else f"{src}: downloading"
            if spd:
                msg += f" | speed: {spd/1024/1024:.2f} MB/s" if isinstance(spd, (int,float)) else ""
            if eta:
                msg += f" | eta: {eta}s"
            status.write(msg)

        try:
            video_path = download_youtube(url, VIDEOS, progress=on_prog)
            prog.progress(100)
            status.write("Download complete")
            st.success(f"Downloaded: {video_path.name}")
            st.session_state["video_path"] = str(video_path)
        except Exception as e:
            st.error(f"Download failed: {e}")

    if col2.button("Extract Audio", disabled="video_path" not in st.session_state):
        with st.spinner("Extracting audio..."):
            try:
                vpath = Path(st.session_state["video_path"]) if "video_path" in st.session_state else None
                if not vpath or not vpath.exists():
                    st.error("No video available. Download first.")
                else:
                    audio_path = extract_audio(vpath)
                    st.success(f"Audio: {audio_path.name}")
                    st.session_state["audio_path"] = str(audio_path)
            except Exception as e:
                st.error(f"Audio extraction failed: {e}")

    if col3.button("Transcribe", disabled="audio_path" not in st.session_state):
        with st.spinner("Transcribing (local Faster-Whisper)... This can take minutes on CPU."):
            try:
                apath = Path(st.session_state["audio_path"]) if "audio_path" in st.session_state else None
                if not apath or not apath.exists():
                    st.error("No audio available. Extract first.")
                else:
                    t = transcribe(
                        apath,
                        model_size=model_size,
                        compute_type=("int8" if fast_mode else None),
                        beam_size=(1 if fast_mode else 5),
                        language=(language or None),
                        vad_filter=use_vad,
                        word_timestamps=word_ts,
                        cpu_threads=0,
                        num_workers=1,
                        model_path=(local_model_dir or None),
                    )
                    save_path = save_transcript(t, video_stem=apath.stem)
                    st.session_state["transcript_path"] = str(save_path)
                    st.session_state["transcript_text"] = t.text
                    # Keep transcript object lightly in session for export
                    st.session_state["_segments"] = [(s.start, s.end, s.text) for s in t.segments]
                    if word_ts:
                        words = []
                        for si, s in enumerate(t.segments):
                            if getattr(s, "words", None):
                                for w in s.words:
                                    words.append({"seg": si+1, "start": w.start, "end": w.end, "word": w.word})
                        st.session_state["_words"] = words
                    st.success(f"Transcript saved: {save_path.relative_to(Path.cwd())}")
            except Exception as e:
                st.error(f"Transcription failed: {e}")

    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.subheader("Video & Files")
        st.write("Videos dir:", str(VIDEOS))
        st.write("Audio dir:", str(AUDIO))
        st.write("Transcripts dir:", str(TRANSCRIPTS))
        if "video_path" in st.session_state:
            st.write("Video:", st.session_state["video_path"])
        if "audio_path" in st.session_state:
            st.write("Audio:", st.session_state["audio_path"])
        if "transcript_path" in st.session_state:
            st.write("Transcript:", st.session_state["transcript_path"])

    with right:
        st.subheader("Transcript")
        txt = st.session_state.get("transcript_text")
        if txt:
            st.text_area("Text", value=txt, height=400)
        else:
            st.info("No transcript yet. Run steps above.")

with tab_qa:
    st.subheader("Local Q&A (Ollama + ChromaDB)")
    apath = st.session_state.get("audio_path")
    ttext = st.session_state.get("transcript_text")
    segs = st.session_state.get("_segments")
    if not apath or not ttext or not segs:
        st.info("Transcribe first to enable Q&A.")
    else:
        vstem = Path(apath).stem
        col1, col2 = st.columns([1,1])
        with col1:
            if st.button("Build/Refresh Index"):
                try:
                    # Reconstruct a minimal Transcript to build index
                    from freetube_agent.transcribe import Transcript as T
                    segments = [type("S", (), {"start": s, "end": e, "text": txt}) for s, e, txt in segs]
                    t = T(text=ttext, segments=segments)
                    n = build_index(vstem, t)
                    st.success(f"Indexed {n} chunks for: {vstem}")
                except Exception as e:
                    st.error(f"Indexing failed: {e}")
        with col2:
            st.write("Collection:", vstem)

        st.markdown("---")
        q = st.text_input("Ask a question about the video")
        colA, colB, colC = st.columns([1,1,1])
        model = colA.text_input("Ollama model", value="llama3.2")
        topk = int(colB.number_input("Top-K", min_value=1, max_value=10, value=4))
        ollama_path = colC.text_input("Ollama path (optional)", value="")
        if st.button("Ask", disabled=not q):
            try:
                hits = query_index(vstem, q, top_k=topk)
                if not hits:
                    st.warning("No relevant chunks found.")
                ctx = []
                for i, h in enumerate(hits, 1):
                    ctx.append(f"[{i}] [{format_time(h['start'])}-{format_time(h['end'])}]\n{h['text']}")
                ctx_str = "\n\n".join(ctx)
                prompt = f"""
You are a helpful assistant answering questions about a video transcript. Use only the provided context.

Question:
{q}

Context chunks:
{ctx_str}

Instructions:
- Provide a concise answer.
- Cite the most relevant chunks by their bracketed numbers and timestamps, e.g., [1 02:13-02:45], [3 05:10-05:30].
- If unsure or missing context, state that clearly.
""".strip()
                ans = run_ollama(model=model, prompt=prompt, ollama_path=(ollama_path or None))
                st.markdown("**Answer**")
                st.write(ans)
                st.markdown("**Citations**")
                for i, h in enumerate(hits, 1):
                    st.write(f"[{i}] {format_time(h['start'])} - {format_time(h['end'])}")
            except Exception as e:
                st.error(f"Q&A failed: {e}")

with tab_export:
    st.subheader("Export Captions")
    seg_data = st.session_state.get("_segments")
    apath = st.session_state.get("audio_path")
    if not seg_data or not apath:
        st.info("Transcribe first to enable exports.")
    else:
        vstem = Path(apath).stem
        # Rehydrate a minimal Transcript for export
        segments = [type("S", (), {"start": s, "end": e, "text": txt}) for s, e, txt in seg_data]
        t = Transcript(text=st.session_state.get("transcript_text", ""), segments=segments)
        c1, c2 = st.columns(2)
        if c1.button("Save SRT"):
            try:
                p = save_srt(t, video_stem=vstem)
                st.success(f"Saved: {p.relative_to(Path.cwd())}")
            except Exception as e:
                st.error(f"SRT export failed: {e}")
        if c2.button("Save VTT"):
            try:
                p = save_vtt(t, video_stem=vstem)
                st.success(f"Saved: {p.relative_to(Path.cwd())}")
            except Exception as e:
                st.error(f"VTT export failed: {e}")

        st.markdown("---")
        c3, c4 = st.columns(2)
        # CSV exports
        import pandas as pd
        seg_df = pd.DataFrame({"start": [s for s,_,_ in seg_data], "end": [e for _,e,_ in seg_data], "text": [t for *_, t in seg_data]})
        c3.download_button("Download segments CSV", data=seg_df.to_csv(index=False).encode("utf-8"), file_name=f"{vstem}_segments.csv", mime="text/csv")
        if st.session_state.get("_words"):
            words_df = pd.DataFrame(st.session_state["_words"])  # seg,start,end,word
            c4.download_button("Download words CSV", data=words_df.to_csv(index=False).encode("utf-8"), file_name=f"{vstem}_words.csv", mime="text/csv")
with tab_timeline:
    st.subheader("Timeline")
    segs = st.session_state.get("_segments")
    if not segs:
        st.info("Transcribe first to view timeline.")
    else:
        try:
            import pandas as pd
            import plotly.express as px

            df = pd.DataFrame(
                {"Segment": list(range(1, len(segs)+1)),
                 "Start": [s[0] for s in segs],
                 "End": [s[1] for s in segs],
                 "Text": [s[2] for s in segs]}
            )
            df["Duration"] = df["End"] - df["Start"]
            fig = px.timeline(df, x_start="Start", x_end="End", y="Segment", hover_data=["Text", "Duration"])
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

            # Optional word density visualization
            if st.session_state.get("_words"):
                wd = pd.DataFrame(st.session_state["_words"])  # seg,start,end,word
                wd["mid"] = (wd["start"] + wd["end"]) / 2
                scatter = px.scatter(wd, x="mid", y="seg", hover_data=["word"], size_max=6)
                scatter.update_layout(height=300, title="Word positions (if enabled)")
                scatter.update_yaxes(title="Segment")
                st.plotly_chart(scatter, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to render timeline: {e}")

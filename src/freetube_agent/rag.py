from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .transcribe import Transcript, Segment
from .paths import DATA


def _words_count(s: str) -> int:
    return len(s.split())


def chunk_transcript(
    t: Transcript,
    max_words: int = 200,
    overlap_words: int = 40,
) -> List[Dict[str, Any]]:
    """Chunk transcript by grouping segments into word-bounded spans.

    Returns a list of dicts: {id, text, start, end}
    """
    chunks: List[Dict[str, Any]] = []
    buf: List[Segment] = []
    wsum = 0
    idx = 1
    for seg in t.segments:
        text = seg.text.strip()
        if not text:
            continue
        w = _words_count(text)
        if wsum + w > max_words and buf:
            start = buf[0].start
            end = buf[-1].end
            chunk_text = " ".join(s.text.strip() for s in buf if s.text.strip())
            chunks.append({"id": f"chunk-{idx}", "text": chunk_text, "start": start, "end": end})
            idx += 1
            # start new buffer with overlap from tail
            if overlap_words > 0:
                carry: List[Segment] = []
                carry_words = 0
                for s in reversed(buf):
                    st = s.text.strip()
                    cw = _words_count(st)
                    if carry_words + cw > overlap_words:
                        break
                    carry.append(s)
                    carry_words += cw
                buf = list(reversed(carry))
                wsum = sum(_words_count(s.text) for s in buf)
            else:
                buf = []
                wsum = 0
        buf.append(seg)
        wsum += w

    if buf:
        start = buf[0].start
        end = buf[-1].end
        chunk_text = " ".join(s.text.strip() for s in buf if s.text.strip())
        chunks.append({"id": f"chunk-{idx}", "text": chunk_text, "start": start, "end": end})

    return chunks


def _embedding_function():
    try:
        from chromadb.utils import embedding_functions

        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    except Exception:
        return None


def get_collection(name: str):
    import chromadb

    persist_dir = DATA / "chroma"
    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    ef = _embedding_function()
    if ef is None:
        # Will raise later on query; caller should handle missing embedding function
        return client.get_or_create_collection(name=name)
    return client.get_or_create_collection(name=name, embedding_function=ef)


def build_index(name: str, t: Transcript) -> int:
    col = get_collection(name)
    chunks = chunk_transcript(t)
    if not chunks:
        return 0
    ids = [c["id"] for c in chunks]
    docs = [c["text"] for c in chunks]
    metas = [
        {"start": c["start"], "end": c["end"], "name": name}
        for c in chunks
    ]
    # Upsert to allow rebuilds
    col.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def query_index(name: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    col = get_collection(name)
    try:
        res = col.query(query_texts=[query], n_results=top_k)
    except Exception as e:
        raise RuntimeError(
            "Query failed — ensure sentence-transformers/torch are installed for embeddings."
        ) from e
    out: List[Dict[str, Any]] = []
    if not res or not res.get("documents"):
        return out
    docs = res["documents"][0]
    metas = res.get("metadatas", [[]])[0]
    for d, m in zip(docs, metas):
        out.append({
            "text": d,
            "start": float(m.get("start", 0.0)) if isinstance(m, dict) else 0.0,
            "end": float(m.get("end", 0.0)) if isinstance(m, dict) else 0.0,
        })
    return out


def format_time(t: float) -> str:
    m = int(t // 60)
    s = int(t % 60)
    return f"{m:02d}:{s:02d}"


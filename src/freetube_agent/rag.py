from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from .transcribe import Transcript, Segment
from .paths import DATA
from .logger import logger, error_tracker, perf_logger


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
    import time
    start_time = time.time()
    logger.info(f"Building index for: {name}")
    
    try:
        col = get_collection(name)
        chunks = chunk_transcript(t)
        if not chunks:
            logger.warning(f"No chunks generated for {name}")
            return 0
        
        logger.debug(f"Generated {len(chunks)} chunks for indexing")
    except Exception as e:
        logger.error(f"Failed to prepare chunks for {name}: {e}")
        error_tracker.log_error(e, context=f"Building index for {name}", module="rag", function="build_index")
        raise
    try:
        ids = [ch["id"] for ch in chunks]
        docs = [ch["text"] for ch in chunks]
        metas = [{"start": ch["start"], "end": ch["end"]} for ch in chunks]
        col.upsert(ids=ids, documents=docs, metadatas=metas)
        
        duration = time.time() - start_time
        logger.info(f"Index built for {name}: {len(ids)} chunks in {duration:.1f}s")
        perf_logger.log_metric("build_index", duration, True, {"name": name, "chunks": len(ids)})
        return len(ids)
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed to upsert chunks for {name}: {e}")
        error_tracker.log_error(e, context=f"Upserting chunks for {name}", module="rag", function="build_index")
        perf_logger.log_metric("build_index", duration, False)
        raise


def query_index(name: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    import time
    start_time = time.time()
    logger.debug(f"Querying index {name} for: {query[:50]}...")
    
    try:
        col = get_collection(name)
        res = col.query(query_texts=[query], n_results=top_k)
    except Exception as e:
        logger.warning(f"Failed to query index {name}: {e}")
        error_tracker.log_error(e, context=f"Querying index {name}", module="rag", function="query_index")
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
    
    duration = time.time() - start_time
    logger.debug(f"Query complete: {len(out)} results in {duration:.3f}s")
    return out


def format_time(t: float) -> str:
    m = int(t // 60)
    s = int(t % 60)
    return f"{m:02d}:{s:02d}"


def is_indexed(name: str) -> bool:
    """Check if a transcript has been indexed in ChromaDB."""
    try:
        col = get_collection(name)
        count = col.count()
        return count > 0
    except Exception:
        return False


def get_indexed_videos() -> List[str]:
    """Get list of all indexed video names."""
    try:
        import chromadb
        persist_dir = DATA / "chroma"
        if not persist_dir.exists():
            return []
        client = chromadb.PersistentClient(path=str(persist_dir))
        collections = client.list_collections()
        return [c.name for c in collections]
    except Exception:
        return []


def delete_index(name: str) -> bool:
    """Delete the index for a specific video."""
    try:
        import chromadb
        persist_dir = DATA / "chroma"
        client = chromadb.PersistentClient(path=str(persist_dir))
        client.delete_collection(name)
        return True
    except Exception:
        return False


def get_index_stats(name: str) -> Dict[str, Any]:
    """Get statistics about an indexed video."""
    try:
        col = get_collection(name)
        count = col.count()
        if count == 0:
            return {"indexed": False, "chunk_count": 0}
        
        # Get sample to check metadata
        sample = col.get(limit=1)
        has_embeddings = len(sample.get("embeddings", [])) > 0
        
        return {
            "indexed": True,
            "chunk_count": count,
            "has_embeddings": has_embeddings
        }
    except Exception as e:
        return {"indexed": False, "error": str(e), "chunk_count": 0}


def retrieve_relevant_chunks(question: str, chunks: List[Dict], top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Simple keyword-based retrieval fallback.
    Used when ChromaDB is not available or for comparison.
    """
    # Simple scoring based on keyword overlap
    question_words = set(question.lower().split())
    scored = []
    
    for chunk in chunks:
        chunk_words = set(chunk["text"].lower().split())
        overlap = len(question_words & chunk_words)
        if overlap > 0:
            scored.append((overlap, chunk))
    
    # Sort by score and return top_k
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]


def batch_index_all(transcript_dir: Optional[Path] = None, force_reindex: bool = False) -> Dict[str, Any]:
    import time
    start_time = time.time()
    logger.info(f"Starting batch indexing (force_reindex={force_reindex})")
    """
    Index all transcripts in the library.
    
    Args:
        transcript_dir: Directory containing transcripts (defaults to paths.TRANSCRIPTS)
        force_reindex: Re-index even if already indexed
    
    Returns:
        Dict with results: {indexed: int, skipped: int, failed: int, errors: List[str]}
    """
    from .paths import TRANSCRIPTS
    if transcript_dir is None:
        transcript_dir = TRANSCRIPTS
    
    results = {
        "indexed": 0,
        "skipped": 0,
        "failed": 0,
        "errors": []
    }
    
    transcript_files = list(transcript_dir.glob("*.txt"))
    
    for transcript_path in transcript_files:
        name = transcript_path.stem
        
        try:
            # Skip if already indexed (unless force_reindex)
            if not force_reindex and is_indexed(name):
                results["skipped"] += 1
                continue
            
            # Load transcript
            content = transcript_path.read_text(encoding="utf-8")
            
            # Create transcript object with basic segments
            # We'll split by paragraphs or sentences for better chunking
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
            
            segments = []
            current_time = 0.0
            for para in paragraphs:
                # Estimate duration (roughly 2 seconds per sentence)
                sentences = para.count(".") + para.count("!") + para.count("?")
                duration = max(2.0, sentences * 2.0)
                segments.append(Segment(start=current_time, end=current_time + duration, text=para))
                current_time += duration
            
            if not segments:
                # Fallback: single segment
                segments = [Segment(start=0.0, end=0.0, text=content)]
            
            t = Transcript(text=content, segments=segments)
            
            # Build index
            chunk_count = build_index(name, t)
            
            if chunk_count > 0:
                results["indexed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{name}: No chunks created")
        
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{name}: {str(e)}")
    
    return results


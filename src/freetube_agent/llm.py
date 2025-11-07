from __future__ import annotations

import shutil
import subprocess
import time
from typing import Optional

from .logger import logger, error_tracker, perf_logger


def run_ollama(model: str, prompt: str, ollama_path: Optional[str] = None, timeout: int = 180) -> str:
    start_time = time.time()
    logger.info(f"Running Ollama model: {model} (timeout={timeout}s)")
    logger.debug(f"Prompt length: {len(prompt)} characters")
    
    exe = ollama_path or shutil.which("ollama") or "ollama"
    logger.debug(f"Using Ollama executable: {exe}")
    
    # Prefer passing prompt via stdin to avoid shell quoting issues
    try:
        cp = subprocess.run(
            [exe, "run", model],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        logger.error("Ollama executable not found. Add to PATH or provide full path.")
        error_tracker.log_error(e, context=f"Running Ollama model {model}", module="llm", function="run_ollama")
        raise RuntimeError("Ollama executable not found. Add to PATH or provide full path.") from e
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        logger.error(f"Ollama timed out after {timeout}s")
        error_tracker.log_error(e, context=f"Ollama timeout for model {model}", module="llm", function="run_ollama")
        perf_logger.log_metric("run_ollama", duration, False, {"model": model, "error": "timeout"})
        raise RuntimeError(f"Ollama timed out after {timeout}s") from e
    
    if cp.returncode != 0:
        err = (cp.stderr or "").strip()
        duration = time.time() - start_time
        logger.error(f"Ollama failed: {err}")
        error_tracker.log_error(Exception(err), context=f"Ollama model {model}", module="llm", function="run_ollama")
        perf_logger.log_metric("run_ollama", duration, False, {"model": model})
        raise RuntimeError(f"Ollama failed: {err}")
    
    result = (cp.stdout or "").strip()
    duration = time.time() - start_time
    logger.info(f"Ollama completed: {len(result)} characters in {duration:.1f}s")
    perf_logger.log_metric("run_ollama", duration, True, {"model": model, "output_chars": len(result)})
    return result


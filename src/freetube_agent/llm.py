from __future__ import annotations

import shutil
import subprocess
from typing import Optional


def run_ollama(model: str, prompt: str, ollama_path: Optional[str] = None, timeout: int = 180) -> str:
    exe = ollama_path or shutil.which("ollama") or "ollama"
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
        raise RuntimeError("Ollama executable not found. Add to PATH or provide full path.") from e
    if cp.returncode != 0:
        err = (cp.stderr or "").strip()
        raise RuntimeError(f"Ollama failed: {err}")
    return (cp.stdout or "").strip()


from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
VIDEOS = DATA / "videos"
AUDIO = DATA / "audio"
TRANSCRIPTS = DATA / "transcripts"

for p in (DATA, VIDEOS, AUDIO, TRANSCRIPTS):
    p.mkdir(parents=True, exist_ok=True)


import json
from pathlib import Path

import numpy as np

import config

from utils import OUTPUT_DIR

_CACHE_PATH = OUTPUT_DIR / "embeddings_cache.json"


def embed_text(text: str) -> list[float]:
    response = config.client.embeddings(model=config.EMBED_MODEL, prompt=text)
    return response.embedding


def load_cache() -> dict:
    if _CACHE_PATH.exists():
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def update_cache(files: list[str]) -> dict:
    cache = load_cache()
    changed = 0
    for path in files:
        mtime = Path(path).stat().st_mtime
        if path in cache and cache[path]["mtime"] == mtime:
            continue
        stem = Path(path).stem
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        cache[path] = {"mtime": mtime, "vector": embed_text(f"{stem}\n{content}")}
        changed += 1
    if changed:
        save_cache(cache)
        config.log(f"Embedded {changed} new/changed notes.")
    return cache


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
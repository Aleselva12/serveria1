from __future__ import annotations

import json
import os
import threading
import time
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.models import get_ollama_base_url


EMBEDDING_MODEL = os.getenv("CORA_EMBEDDING_MODEL", "nomic-embed-text").strip()
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("CORA_EMBEDDING_TIMEOUT_SECONDS", "30"))
_cache = OrderedDict()
_cache_lock = threading.Lock()


def embed_text(text: str, *, timeout: float | None = None, cached: bool = False) -> tuple[list[float] | None, str | None]:
    """Return a local Ollama embedding. Failure never destroys the source text."""
    normalized = text.strip()
    if not normalized or not EMBEDDING_MODEL:
        return None, None
    key = (get_ollama_base_url(), EMBEDDING_MODEL, normalized)
    if cached:
        with _cache_lock:
            entry = _cache.get(key)
            if entry and time.monotonic() - entry[0] < 60:
                _cache.move_to_end(key)
                return list(entry[1]), EMBEDDING_MODEL

    payload = json.dumps(
        {"model": EMBEDDING_MODEL, "input": normalized},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{get_ollama_base_url().rstrip('/')}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout if timeout is not None else EMBEDDING_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None, EMBEDDING_MODEL

    embeddings = data.get("embeddings")
    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
        vector = [float(value) for value in embeddings[0]]
        if cached:
            with _cache_lock:
                _cache[key] = (time.monotonic(), vector)
                while len(_cache) > 128:
                    _cache.popitem(last=False)
        return vector, EMBEDDING_MODEL
    return None, EMBEDDING_MODEL


def embed_batch(texts: list[str]) -> list[list[float] | None]:
    """One bounded idle request; invalid batches are marked failed, never misaligned."""
    if not texts or not EMBEDDING_MODEL: return [None] * len(texts)
    request = Request(f"{get_ollama_base_url().rstrip('/')}/api/embed",
        data=json.dumps({"model": EMBEDDING_MODEL, "input": texts}, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=EMBEDDING_TIMEOUT_SECONDS) as response:
            vectors = json.loads(response.read().decode())["embeddings"]
        if len(vectors) != len(texts): raise ValueError("Invalid batch size")
        return [[float(x) for x in vector] for vector in vectors]
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        return [None] * len(texts)

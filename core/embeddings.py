from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.models import get_ollama_base_url


EMBEDDING_MODEL = os.getenv("CORA_EMBEDDING_MODEL", "nomic-embed-text").strip()
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("CORA_EMBEDDING_TIMEOUT_SECONDS", "30"))


def embed_text(text: str) -> tuple[list[float] | None, str | None]:
    """Return a local Ollama embedding. Failure never destroys the source text."""
    normalized = text.strip()
    if not normalized or not EMBEDDING_MODEL:
        return None, None

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
        with urlopen(request, timeout=EMBEDDING_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None, EMBEDDING_MODEL

    embeddings = data.get("embeddings")
    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
        vector = [float(value) for value in embeddings[0]]
        return vector, EMBEDDING_MODEL
    return None, EMBEDDING_MODEL

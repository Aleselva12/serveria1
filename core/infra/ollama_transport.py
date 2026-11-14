"""One local endpoint and proxy-free transport for Ollama probes and embeddings."""
import os
from urllib.request import ProxyHandler, build_opener

DEFAULT_BASE_URL = "http://localhost:11434"


def get_ollama_base_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/")


def urlopen(request, *, timeout):
    return build_opener(ProxyHandler({})).open(request, timeout=timeout)

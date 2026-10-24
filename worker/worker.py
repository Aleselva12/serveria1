"""Cora worker HTTP bridge for Windows-host Ollama.

Only GET /health is public to the tailnet. Model inventory and inference require
a high-entropy secret known to the Cora backend. This container has no GPU,
Docker socket, shell endpoint, or host file mounts; Ollama runs on Windows.
"""
from __future__ import annotations

import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

PORT = int(os.getenv("CORA_WORKER_PORT", "8765"))
BASE = os.getenv("CORA_OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
TOKEN = os.getenv("CORA_WORKER_TOKEN", "")
MAX_BODY = 24_000
_inference_slot = threading.BoundedSemaphore(value=1)
# An explicit local host URL, never a URL supplied by remote callers.
if not (BASE.startswith("http://host.docker.internal:") or
        BASE.startswith("http://127.0.0.1:")):
    raise SystemExit("CORA_OLLAMA_BASE_URL deve usare host.docker.internal oppure localhost")


def ollama(path: str, payload: dict | None = None, timeout: int = 5) -> dict:
    url = BASE + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        raw = response.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Risposta Ollama troppo grande")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Risposta Ollama non valida")
    return value


def installed_models() -> list[dict]:
    raw = ollama("/api/tags", timeout=4)
    result = []
    for item in raw.get("models", [])[:100]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        size = item.get("size")
        if isinstance(name, str) and 0 < len(name) <= 180 and isinstance(size, int):
            result.append({"name": name, "size_bytes": size})
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "CoraWorker/2"
    def log_message(self, format, *args):
        # Avoid logging bearer credentials, model prompts and output.
        return

    def send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def allowed(self) -> bool:
        expected = TOKEN.encode()
        incoming = self.headers.get("X-Cora-Worker-Token", "").encode()
        return len(expected) >= 32 and hmac.compare_digest(expected, incoming)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ready", "protocol": "cora-worker-v1",
                 "capabilities": ["ollama-bridge"] if len(TOKEN) >= 32 else [],
                 "execution_enabled": False,
                 "inference_backend": "windows-ollama",
                 "authorization_configured": len(TOKEN) >= 32})
            return
        if not self.allowed():
            self.send_json(403, {"detail": "Worker non autorizzato o non configurato"})
            return
        if self.path == "/models":
            try:
                self.send_json(200, {"models": installed_models(), "backend": "windows-ollama",
                                    "reachable": True})
            except (OSError, TimeoutError, HTTPError, URLError, ValueError) as exc:
                self.send_json(503, {"models": [], "reachable": False,
                                     "detail": "Ollama Windows non raggiungibile dal container"})
            return
        self.send_json(404, {"detail": "Endpoint non disponibile"})

    def do_POST(self):
        if not self.allowed():
            self.send_json(403, {"detail": "Worker non autorizzato o non configurato"})
            return
        if self.path != "/generate":
            self.send_json(405, {"detail": "Nessun comando remoto supportato"})
            return
        if not _inference_slot.acquire(blocking=False):
            self.send_json(429, {"detail": "Worker occupato: una inferenza per volta"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BODY:
                self.send_json(413, {"detail": "Richiesta troppo grande"})
                return
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Corpo non valido")
            model, prompt = body.get("model"), body.get("prompt")
            if not (isinstance(model, str) and isinstance(prompt, str)
                    and 0 < len(model) <= 180 and 0 < len(prompt) <= 10_000):
                raise ValueError("Modello o testo non valido")
            # Reject model names other than those already downloaded.
            if model not in {m["name"] for m in installed_models()}:
                self.send_json(422, {"detail": "Il modello non è installato sul PC"})
                return
            reply = ollama("/api/generate", {
                "model": model, "prompt": prompt,
                "stream": False, "keep_alive": "1m",
                "options": {"num_ctx": 4096, "num_predict": 256},
            }, timeout=300)
            self.send_json(200, {"model": model,
                 "response": str(reply.get("response") or "")[:20_000],
                 "total_duration": reply.get("total_duration"),
                 "eval_count": reply.get("eval_count"),
                 "eval_duration": reply.get("eval_duration")})
        except (OSError, TimeoutError, HTTPError, URLError):
            self.send_json(503, {"detail": "Ollama non raggiungibile o modello non avviato"})
        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_json(422, {"detail": "Richiesta di inferenza non valida"})
        finally:
            _inference_slot.release()


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

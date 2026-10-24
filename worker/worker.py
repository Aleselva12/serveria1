"""Minimal, read-only Cora worker: no shell, Docker socket, file or model access."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/health", "/capabilities"):
            self.send_error(404)
            return
        body = json.dumps({
            "status": "ready",
            "protocol": "cora-worker-v1",
            "capabilities": [],
            "execution_enabled": False,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.send_error(405, "Execution is not enabled")

if __name__ == "__main__":
    port = int(os.getenv("CORA_WORKER_PORT", "8765"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

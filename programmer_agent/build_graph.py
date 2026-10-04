"""Optional Graphify CLI adapter: baseline code only, no model backend or generated execution."""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from core.runtime import checkpoint
from programmer_agent import workspace as ws
from programmer_agent.knowledge import import_graph


def build(identifier: str) -> dict:
    executable = shutil.which("graphify")
    if not executable:
        raise ValueError("Graphify non installato. Aggiungi requirements-programmer-graph.txt o importa un graph.json esistente.")
    # Baseline is immutable through Cora. A fresh output folder excludes old semantic caches.
    source = ws.directory(identifier) / "baseline"
    with ws.LOCK, tempfile.TemporaryDirectory(prefix="cora-graph-") as temporary, tempfile.TemporaryFile() as output:
        for path in source.rglob("*"):
            ws._no_links(path)
        process = subprocess.Popen([executable, "extract", str(source), "--code-only", "--no-cluster", "--out", temporary],
                                   stdout=output, stderr=subprocess.STDOUT, shell=False)
        try:
            from time import monotonic
            started = monotonic()
            while True:
                checkpoint()
                if monotonic() - started > 120:
                    raise TimeoutError("Indicizzazione Graphify scaduta.")
                try:
                    process.wait(timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    continue
            output.seek(0)
            if process.returncode:
                raise ValueError("Graphify non ha completato la mappa: " + output.read(1000).decode(errors="replace"))
            path = Path(temporary) / "graphify-out" / "graph.json"
            if not path.is_file() or path.stat().st_size > 8_000_000:
                raise ValueError("Grafo non disponibile o oltre 8 MB.")
            graph = json.loads(path.read_text(encoding="utf-8"))
            return import_graph(identifier, graph, ws.manifest(identifier)["source_digest"])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace_id")
    args = parser.parse_args()
    print(json.dumps(build(args.workspace_id), ensure_ascii=False, indent=2))

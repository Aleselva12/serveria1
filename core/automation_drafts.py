"""Persistent diagram drafts only. No execution, scheduling or agent assignment."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOCK = threading.RLock()
BASE = Path(__file__).resolve().parents[1]
KINDS = {"trigger", "tool", "condition", "output"}


def draft_root():
    return Path(os.getenv("CORA_AUTOMATION_ROOT", str(BASE / "data" / "automation_drafts"))).expanduser().resolve()


def validate_graph(data, tool_ids=None):
    if not isinstance(data, dict):
        raise ValueError("Bozza non valida.")
    title = data.get("title", "")
    description = data.get("description", "")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise ValueError("Il titolo deve contenere da 1 a 120 caratteri.")
    if not isinstance(description, str) or len(description) > 4000:
        raise ValueError("Descrizione troppo lunga.")
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 80 or not isinstance(edges, list) or len(edges) > 160:
        raise ValueError("Sono ammessi da 1 a 80 nodi e fino a 160 collegamenti.")
    ids, edge_ids = set(), set()
    clean_nodes, clean_edges, warnings = [], [], []
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Nodo non valido.")
        ident, kind, label = node.get("id"), node.get("kind"), node.get("label")
        if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in ids or kind not in KINDS:
            raise ValueError("Identità o tipo del nodo non valido.")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 160:
            raise ValueError("Ogni nodo deve avere un nome di massimo 160 caratteri.")
        for axis in ("x", "y"):
            val = node.get(axis)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not 0 <= val <= 10000:
                raise ValueError("Posizione del nodo non valida.")
        config = node.get("config", {})
        if not isinstance(config, dict) or len(json.dumps(config, allow_nan=False)) > 65536:
            raise ValueError("Configurazione del nodo non valida o troppo grande.")
        tool_id = node.get("tool_id")
        if kind == "tool":
            if tool_id and (not isinstance(tool_id, str) or len(tool_id) > 512 or tool_ids is not None and tool_id not in tool_ids):
                raise ValueError("Il tool associato non è disponibile nell’inventario.")
            if not tool_id:
                warnings.append(f"{label}: scegli un tool per completare il passaggio.")
        ids.add(ident)
        clean_nodes.append(dict(id=ident, kind=kind, label=label.strip(), x=node["x"], y=node["y"], config=config, tool_id=tool_id))
    by_id = {n["id"]: n for n in clean_nodes}
    adjacency = {ident: [] for ident in ids}
    incoming = {ident: [] for ident in ids}
    pairs = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Collegamento non valido.")
        source, target, label, ident = edge.get("source"), edge.get("target"), edge.get("label", ""), edge.get("id")
        if not isinstance(ident, str) or not ident or len(ident) > 80 or ident in edge_ids:
            raise ValueError("Identità del collegamento non valida.")
        if not isinstance(source, str) or not isinstance(target, str) or source not in ids or target not in ids or source == target or by_id[source]["kind"] == "output" or by_id[target]["kind"] == "trigger":
            raise ValueError("Collegamento fra nodi non valido.")
        if not isinstance(label, str) or len(label) > 80 or (source, target, label) in pairs:
            raise ValueError("Etichetta o duplicato del collegamento non valido.")
        pairs.add((source, target, label))
        edge_ids.add(ident)
        adjacency[source].append(target)
        incoming[target].append(source)
        clean_edges.append(dict(id=ident, source=source, target=target, label=label))
    visiting, visited = set(), set()
    def visit(ident):
        if ident in visiting:
            raise ValueError("I cicli non sono supportati nell’editor delle bozze.")
        if ident in visited:
            return
        visiting.add(ident)
        for target in adjacency[ident]:
            visit(target)
        visiting.remove(ident)
        visited.add(ident)
    for ident in ids:
        visit(ident)
    if not any(n["kind"] == "trigger" for n in clean_nodes):
        warnings.append("Aggiungi un ingresso al flusso.")
    if not any(n["kind"] == "output" for n in clean_nodes):
        warnings.append("Aggiungi un’uscita al flusso.")
    reachable = set()
    def mark(ident):
        if ident in reachable:
            return
        reachable.add(ident)
        for target in adjacency[ident]:
            mark(target)
    for node in clean_nodes:
        if node["kind"] == "trigger":
            mark(node["id"])
    for node in clean_nodes:
        if node["kind"] != "trigger" and node["id"] not in reachable:
            warnings.append(f"{node['label']}: non raggiungibile da un ingresso.")
        if node["kind"] != "output" and not adjacency[node["id"]]:
            warnings.append(f"{node['label']}: manca un collegamento in uscita.")
        if node["kind"] == "condition":
            labels = {e["label"] for e in clean_edges if e["source"] == node["id"]}
            if not {"sì", "no"} <= labels:
                warnings.append(f"{node['label']}: completa i rami sì e no.")
    return dict(title=title.strip(), description=description, nodes=clean_nodes, edges=clean_edges, warnings=warnings)


def _path(ident, root):
    try:
        parsed = str(uuid.UUID(ident))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Identificativo della bozza non valido.") from None
    return root / (parsed + ".json")


def get_draft(ident, root=None):
    path = _path(ident, root or draft_root())
    with LOCK:
        return json.loads(path.read_text(encoding="utf-8"))


def list_drafts(root=None):
    root = root or draft_root()
    rows = []
    with LOCK:
        for path in root.glob("*.json"):
            data = get_draft(path.stem, root)
            rows.append({key: data[key] for key in ("id", "title", "version", "updated_at", "status")})
    return sorted(rows, key=lambda row: row["updated_at"], reverse=True)


class VersionConflict(Exception):
    pass


def save_draft(data, ident=None, expected_version=None, root=None, tool_ids=None):
    record = validate_graph(data, tool_ids)
    root = root or draft_root()
    with LOCK:
        version = 1
        if ident:
            previous = get_draft(ident, root)
            if expected_version != previous["version"]:
                raise VersionConflict("La bozza è cambiata. Ricaricala prima di salvare.")
            version = previous["version"] + 1
        else:
            ident = str(uuid.uuid4())
        record.update(id=ident, version=version, updated_at=datetime.now(timezone.utc).isoformat(), status="draft")
        root.mkdir(parents=True, exist_ok=True)
        path = _path(ident, root)
        fd, temp = tempfile.mkstemp(prefix=".draft-", dir=root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return record

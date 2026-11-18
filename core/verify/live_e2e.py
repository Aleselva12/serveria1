"""Live E2E checks on the installed server, approved by the owner on 17/11/2026.

They exercise the real code path on real resources, with strict limits:
- Gmail: read-only, on the two linked accounts. Profile, one inbox id, nothing
  stored but the outcome. Messages are not opened as content nor marked as read.
- Files: a uniquely named folder in the "Dati Cora" resource (application data,
  not the owner's documents), always removed; the NAS is only listed.
- Word: a generated client document in the IA Library, the real proposal,
  approval, publication and backup through the audio API, then full cleanup.

Each returns (status, detail); details never carry message or document content.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from uuid import uuid4

FILES_ROOT = "cora"  # "Dati Cora": application data, not the owner's documents
NAS_ROOT = "drive"
PREFIX = "cora-collaudo-"


def gmail_read() -> tuple[str, str]:
    from google.auth.exceptions import RefreshError

    from core.domain import mail
    results, failed, linked = [], False, 0
    for key, email in mail.ACCOUNTS.items():
        name = email.split("@")[0]
        if not mail.token_path(key).is_file():
            results.append(name + ": non collegato")
            continue
        linked += 1
        try:
            service = mail.service(key)
            profile = service.users().getProfile(userId="me").execute()
            if str(profile.get("emailAddress", "")).lower() != email.lower():
                raise ValueError("autorizzazione di un altro account")
            listing = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=1).execute()
            ids = [m["id"] for m in listing.get("messages", [])]
            if ids:
                # "minimal": id and labels only; the message is not opened nor marked as read.
                if service.users().messages().get(userId="me", id=ids[0], format="minimal").execute().get("id") != ids[0]:
                    raise ValueError("messaggio non riletto")
            results.append(name + ": lettura riuscita")
        except RefreshError:
            failed = True
            results.append(name + ": autorizzazione revocata o scaduta, ricollegare dalla pagina Mail")
        except ValueError as error:
            failed = True
            results.append(name + ": " + str(error)[:80])
        except Exception as error:
            failed = True
            results.append(name + ": errore " + type(error).__name__)
    detail = "; ".join(results) + ". Sola lettura, nessun contenuto salvato"
    if failed:
        return "fail", detail[:240]
    if not linked:
        return "unknown", detail[:240]
    return ("warn" if linked < len(mail.ACCOUNTS) else "pass"), detail[:240]


@contextmanager
def _client(router):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(router)
    # Same process and code path as the API; the owner gate is the only bypass.
    for dependency in router.dependencies:
        app.dependency_overrides[dependency.dependency] = lambda: None
    with TestClient(app) as client:
        yield client


def files_live() -> tuple[str, str]:
    from core.domain import server_files
    roots = {root["id"]: root for root in server_files.roots()}
    root = roots.get(FILES_ROOT)
    if not root or not root["writable"]:
        return "unknown", "Risorsa Dati Cora non configurata o in sola lettura sul server"
    base = Path(root["path"])
    folder = PREFIX + uuid4().hex[:12]
    content = os.urandom(64 * 1024) + b"CORA collaudo\x00\xff"
    trashed = []
    router = server_files.make_router("/collaudo", "Collaudo", root_provider=server_files.roots)
    try:
        with _client(router) as client:
            def ok(response, expected=200):
                if response.status_code != expected:
                    raise AssertionError(f"{response.request.method} {response.request.url.path} → {response.status_code}")
                return response
            ok(client.post("/collaudo/folders", json={"root_id": FILES_ROOT, "path": folder}), 201)
            ok(client.post("/collaudo/upload", data={"root_id": FILES_ROOT, "path": folder},
                           files={"file": ("campione.bin", content)}), 201)
            ok(client.post("/collaudo/upload", data={"root_id": FILES_ROOT, "path": folder},
                           files={"file": ("campione.bin", b"altro")}), 409)
            if ok(client.get("/collaudo/download", params={"root_id": FILES_ROOT, "path": folder + "/campione.bin"})).content != content:
                return "fail", "File scaricato diverso da quello caricato sul disco del server"
            ok(client.post("/collaudo/transfer", json={"root_id": FILES_ROOT, "path": folder + "/campione.bin",
                                                       "destination": folder + "/copia.bin", "mode": "copy"}))
            ok(client.post("/collaudo/transfer", json={"root_id": FILES_ROOT, "path": folder + "/copia.bin",
                                                       "destination": folder + "/spostato.bin", "mode": "move"}))
            names = {item["name"] for item in ok(client.get("/collaudo/children", params={"root_id": FILES_ROOT, "path": folder})).json()["items"]}
            if names != {"campione.bin", "spostato.bin"}:
                return "fail", "Copia o spostamento non coerenti con il contenuto della cartella"
            item = ok(client.post("/collaudo/trash", json={"root_id": FILES_ROOT, "path": folder + "/spostato.bin"}), 201).json()
            trashed.append(item["id"])
            ok(client.post("/collaudo/restore", json={"root_id": FILES_ROOT, "id": item["id"]}))
            trashed.remove(item["id"])
            restored = (base / folder / "spostato.bin").read_bytes()
            if hashlib.sha256(restored).digest() != hashlib.sha256(content).digest():
                return "fail", "File ripristinato dal cestino non integro"
            nas = "NAS non configurato"
            if NAS_ROOT in roots:
                listing = client.get("/collaudo/children", params={"root_id": NAS_ROOT, "path": ""})
                if listing.status_code != 200:
                    return "fail", "Drive NAS non leggibile dal server (mount assente o non accessibile)"
                nas = f"NAS leggibile ({listing.json()['total']} elementi in radice, nessuna scrittura)"
    except AssertionError as error:
        return "fail", ("Operazione file non riuscita: " + str(error))[:240]
    finally:
        shutil.rmtree(base / folder, ignore_errors=True)
        for identifier in trashed:
            shutil.rmtree(base / ".cora-trash" / identifier, ignore_errors=True)
    return "pass", ("Dati Cora: cartella, upload, protezione duplicati, download integro, copia, spostamento, "
                    "cestino e ripristino sul disco reale; cartella rimossa. " + nas)[:240]


def _client_document(heading):
    from docx import Document
    document = Document()
    for line in (heading, "Referente collaudo", "17/11/2026", "Annotazione esistente da non toccare",
                 "---------------------------------------------------------"):
        document.add_paragraph(line)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def word_live() -> tuple[str, str]:
    from docx import Document

    from core.api.audio_api import router
    from core.infra.database import db_connection
    from core.infra.file_paths import library_workspace_root
    token = uuid4().hex[:12]
    # Client headings are upper-case words without digits: spell the token in letters.
    heading = "CLIENTE COLLAUDO " + "".join(chr(ord("A") + int(c, 16)) for c in token)
    root = library_workspace_root()
    folder = root / (PREFIX + token)
    audio_id = uuid4()
    original = _client_document(heading)
    proposal_ids = []
    try:
        folder.mkdir()
        target = folder / "cliente.docx"
        target.write_bytes(original)
        with db_connection() as conn:
            conn.execute("""INSERT INTO audio_records(id,title,name,source_path,transcript)
                VALUES (%s,'Collaudo Cora','collaudo.wav','collaudo','Collaudo automatico')""", (audio_id,))
        base = f"/api/v1/audio/{audio_id}/commercial"
        with _client(router) as client:
            found = client.get(base + "/customers", params={"query": heading})
            matches = [m for m in found.json().get("matches", []) if m["heading"] == heading] if found.status_code == 200 else []
            if len(matches) != 1:
                return "fail", "Ricerca cliente nella Libreria IA non riuscita sul documento di collaudo"
            def propose(note):
                return client.post(base + "/proposals", json={"expected_audio_version": 1, "selected": matches[0],
                                                              "date": "17/11/2026", "note": note})
            first = propose("Nota di collaudo da rifiutare")
            if first.status_code != 201:
                return "fail", f"Proposta non creata (HTTP {first.status_code})"
            proposal_ids.append(first.json()["id"])
            if client.post(base + f"/proposals/{first.json()['id']}/resolve", json={"approve": False}).json().get("status") != "rejected" \
                    or target.read_bytes() != original:
                return "fail", "Il rifiuto della proposta ha modificato il documento"
            second = propose("Nota di collaudo approvata")
            if second.status_code != 201:
                return "fail", f"Seconda proposta non creata dopo il rifiuto (HTTP {second.status_code})"
            proposal_ids.append(second.json()["id"])
            resolved = client.post(base + f"/proposals/{second.json()['id']}/resolve", json={"approve": True})
            if resolved.status_code != 200 or resolved.json().get("status") != "approved":
                return "fail", f"Approvazione non pubblicata (HTTP {resolved.status_code})"
        before = [p.text for p in Document(BytesIO(original)).paragraphs]
        after = [p.text for p in Document(target).paragraphs]
        if after[:4] != before[:4] or not any("Nota di collaudo approvata" in text for text in after):
            return "fail", "Nota non aggiunta sotto il cliente o testo esistente cambiato"
        if any("da rifiutare" in text for text in after):
            return "fail", "La nota rifiutata è finita nel documento"
        backup = root / ".cora-commercial-backups" / (second.json()["id"] + ".docx")
        if backup.read_bytes() != original:
            return "fail", "Backup dell'originale assente o diverso"
    except Exception as error:
        return "fail", "Collaudo Word interrotto: " + type(error).__name__
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        for identifier in proposal_ids:
            (root / ".cora-commercial-backups" / (identifier + ".docx")).unlink(missing_ok=True)
        try:
            with db_connection() as conn:
                conn.execute("DELETE FROM commercial_note_proposals WHERE audio_id=%s", (audio_id,))
                conn.execute("DELETE FROM audio_records WHERE id=%s AND source_path='collaudo'", (audio_id,))
        except Exception as error:
            from core.infra.logging import report_swallowed_error
            report_swallowed_error("word_live_cleanup", error, component="health_monitor")
    return "pass", ("Libreria IA reale: ricerca cliente, proposta rifiutata senza scrittura, proposta approvata "
                    "aggiunta sotto il cliente, testo esistente intatto, backup dell'originale; tutto rimosso")


LIVE = {"gmail_read_e2e": gmail_read, "files_live_e2e": files_live, "word_live_e2e": word_live}

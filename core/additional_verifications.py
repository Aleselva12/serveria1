"""Bounded checks with explicit scope. Synthetic checks never certify external apps."""
import base64
import json
import os
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch


def gmail_contract():
    from email_agent import email_connector as connector
    from email_agent import email_tools
    required = ("get_gmail_service", "search_messages", "get_message", "save_as_draft")
    if not all(callable(getattr(connector, key, None)) for key in required):
        return "fail", "Collegamento Gmail mancante"
    names = {tool.name for tool in email_tools.EMAIL_TOOLS}
    if not {"search_email_archive", "get_email_by_id", "save_email_draft"} <= names:
        return "fail", "Strumenti Gmail scollegati"
    return "pass", "Contratti lettura e bozza presenti; account e invio non collaudati"


def gmail_sample():
    from email import message_from_bytes

    from email_agent import email_connector as connector
    service = MagicMock()
    service.users.return_value.drafts.return_value.create.return_value.execute.return_value = {"id": "synthetic"}
    with patch.object(connector, "get_gmail_service", return_value=service):
        result = connector.save_as_draft("test@example.invalid", "Cora verification", "Synthetic body")
    payload = service.users.return_value.drafts.return_value.create.call_args.kwargs["body"]
    message = message_from_bytes(base64.urlsafe_b64decode(payload["message"]["raw"]))
    if result.get("id") != "synthetic" or message["To"] != "test@example.invalid" or message["Subject"] != "Cora verification":
        return "fail", "Serializzazione della bozza Gmail non riuscita"
    service.users.return_value.messages.return_value.send.assert_not_called()
    return "pass", "Bozza MIME generata con trasporto simulato; nessun account contattato o messaggio inviato"


def files_sample():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.domain.server_files import make_router
    token = "cora-synthetic-verification"
    with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"CORA_OWNER_TOKEN": token}):
        roots = [{"id": "test", "path": folder, "writable": True}]
        app = FastAPI()
        app.include_router(make_router("/test", "Test", root_provider=lambda: roots))
        content = b"CORA verification: exact bytes\x00\xff"
        with TestClient(app, headers={"Authorization": "Bearer " + token}) as client:
            uploaded = client.post("/test/upload", data={"root_id": "test", "path": ""}, files={"file": ("sample.bin", content)})
            downloaded = client.get("/test/download", params={"root_id": "test", "path": "sample.bin"})
            duplicate = client.post("/test/upload", data={"root_id": "test", "path": ""}, files={"file": ("sample.bin", b"different")})
            if uploaded.status_code != 201 or downloaded.content != content or duplicate.status_code != 409:
                return "fail", "Upload, download o protezione sovrascrittura non riusciti"
    return "pass", "HTTP upload/download, integrità e duplicati su cartella temporanea; NAS e browser reali esclusi"


def quote_sample():
    from pypdf import PdfReader

    from email_agent import email_tools
    with tempfile.TemporaryDirectory() as folder, patch.object(email_tools, "QUOTE_ROOT", Path(folder)), patch.object(email_tools, "_require_permission"):
        # The undecorated function only touches our generated temporary PDF.
        function = email_tools.generate_quote_pdf.func.__wrapped__
        result = json.loads(function(customer_name="CORA TEST", items_json=json.dumps([
            {"description": "Synthetic item", "quantity": 2, "unit_price": 10}]), filename="test.pdf"))
        if result.get("status") != "ok" or result.get("total") != 24.4:
            return "fail", "Totali del preventivo sintetico non corretti"
        path = Path(result["pdf_path"])
        if not path.is_relative_to(Path(folder)) or "CORA TEST" not in "".join(p.extract_text() for p in PdfReader(BytesIO(path.read_bytes())).pages):
            return "fail", "PDF sintetico non rileggibile"
    return "pass", "Generazione PDF, totali e rilettura su dati sintetici; nessun preventivo utente modificato"


def service_http(identifier):
    from urllib.request import HTTPRedirectHandler, Request, build_opener
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    url = os.getenv("CORA_SERVICE_" + identifier.upper() + "_URL", "").strip()
    if not url:
        return "unknown", "Endpoint di controllo del servizio non configurato"
    # Operator-configured endpoint, no URLs from browser requests, no writes.
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return "unknown", "Endpoint di controllo non valido"
    try:
        with build_opener(NoRedirect()).open(Request(url, headers={"Accept": "application/json"}), timeout=5) as response:
            if not 200 <= response.status < 300:
                return "fail", "Endpoint HTTP del servizio non pronto"
    except Exception:
        return "fail", "Endpoint HTTP del servizio non raggiungibile"
    return "pass", "Endpoint HTTP raggiungibile; caricamento, recupero e integrità dei dati non collaudati"


OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"


def _installed_packages():
    from importlib.metadata import distributions
    found = {}
    for dist in distributions():
        name = (dist.metadata.get("Name") or "").strip()
        if name and dist.version:
            found[name.lower().replace("_", "-")] = dist.version
    return sorted(found.items())


def _severity(vuln):
    """GHSA/PyPA label when present; unknown counts as moderate, never as safe."""
    label = str((vuln.get("database_specific") or {}).get("severity") or "").upper()
    return {"CRITICAL": "high", "HIGH": "high", "LOW": "low"}.get(label, "moderate")


def dependency_audit(packages=None, client=None):
    import httpx
    packages = packages if packages is not None else _installed_packages()
    if not packages:
        return "unknown", "Elenco dei pacchetti installati non disponibile"
    own = client is None
    client = client or httpx.Client(timeout=20)
    try:
        hits = {}
        for start in range(0, len(packages), 500):
            chunk = packages[start:start + 500]
            response = client.post(OSV_BATCH, json={"queries": [
                {"package": {"name": name, "ecosystem": "PyPI"}, "version": version} for name, version in chunk]})
            response.raise_for_status()
            for (name, version), item in zip(chunk, response.json().get("results", []), strict=False):
                ids = [vuln["id"] for vuln in item.get("vulns") or []]
                if ids:
                    hits[f"{name} {version}"] = ids
        # Per package: the worst severity among its first advisories decides.
        levels = {}
        for package, ids in hits.items():
            levels[package] = "low"
            for vuln_id in ids[:10]:
                detail = client.get(OSV_VULN + vuln_id)
                detail.raise_for_status()
                level = _severity(detail.json())
                if level == "high" or (level == "moderate" and levels[package] == "low"):
                    levels[package] = level
                if level == "high":
                    break
    except Exception:
        return "unknown", "Database vulnerabilità OSV non raggiungibile; nessun esito"
    finally:
        if own:
            client.close()
    if not hits:
        return "pass", f"{len(packages)} pacchetti Python controllati: nessuna vulnerabilità nota"
    high = sorted(p for p, level in levels.items() if level == "high")
    if high:
        return "fail", f"Vulnerabilità gravi in {len(high)} pacchetti: {', '.join(high)}"[:240]
    return "warn", f"Vulnerabilità medie/basse in {len(hits)} pacchetti: {', '.join(sorted(hits))}"[:240]


DIRECT = {"gmail_contract": gmail_contract, "gmail_e2e": gmail_sample,
          "files_e2e": files_sample, "preventivi_e2e": quote_sample,
          "immich_e2e": lambda: service_http("immich"),
          "nextcloud_e2e": lambda: service_http("nextcloud"),
          "dependency_audit": dependency_audit}

REGRESSIONS = {
    "chat_e2e": ("tests.test_component_boundaries.CatalogTests.test_chat_to_specialist_graph_exchange_with_mocked_agent", "tests.test_chat_tools"),
    "audio_e2e": ("tests.test_audio_deployment", "tests.test_commercial_word"),
    "magazzino_e2e": ("tests.test_managed_apps",),
    "backup_restore": ("tests.test_private_backups", "tests.test_deployment"),
    "updates_rollback": ("tests.test_updater",),
}

# Reuse reviewed fixture-based suites through the existing one-shot runner.
REGRESSIONS.update({'files_browse_regression': ('tests.test_server_files.ServerFilesTests.test_listing_filter_pagination_and_directories',), 'files_lifecycle_regression': ('tests.test_server_files.ServerFilesTests.test_create_move_copy_and_conflicts', 'tests.test_server_files.ServerFilesTests.test_trash_restore_and_conflicting_original', 'tests.test_file_editor.FileEditorTests.test_edit_backup_conflict_and_mode'), 'files_access_regression': ('tests.test_server_files.ServerFilesTests.test_access_requires_owner_token', 'tests.test_server_files.ServerFilesTests.test_readonly_rejects_all_mutations', 'tests.test_server_files.ServerFilesTests.test_same_prefix_sibling_and_all_public_path_inputs_are_confined'), 'word_document_regression': ('tests.test_word_files.WordFilesTests', 'tests.test_commercial_word.CommercialWordTests')})

from core.verify.tree_verification_suites import SUITES as TREE_SUITES

REGRESSIONS.update({key: item["tests"] for key, item in TREE_SUITES.items()})

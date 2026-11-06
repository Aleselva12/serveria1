"""Bounded checks with explicit scope. Synthetic checks never certify external apps."""
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch


def gmail_contract():
    from email_agent import email_connector as connector, email_tools
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
    from core.server_files import make_router
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
    from email_agent import email_tools
    from pypdf import PdfReader
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
    from urllib.request import Request, build_opener, HTTPRedirectHandler
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


DIRECT = {"gmail_contract": gmail_contract, "gmail_e2e": gmail_sample,
          "files_e2e": files_sample, "preventivi_e2e": quote_sample,
          "immich_e2e": lambda: service_http("immich"),
          "nextcloud_e2e": lambda: service_http("nextcloud")}

REGRESSIONS = {
    "chat_e2e": ("tests.test_component_boundaries.CatalogTests.test_chat_to_specialist_graph_exchange_with_mocked_agent", "tests.test_chat_tools"),
    "audio_e2e": ("tests.test_audio_deployment", "tests.test_commercial_word"),
    "magazzino_e2e": ("tests.test_managed_apps",),
    "backup_restore": ("tests.test_private_backups", "tests.test_deployment"),
    "updates_rollback": ("tests.test_updater",),
}

# Reuse reviewed fixture-based suites through the existing one-shot runner.
REGRESSIONS.update({'files_browse_regression': ('tests.test_server_files.ServerFilesTests.test_listing_filter_pagination_and_directories',), 'files_lifecycle_regression': ('tests.test_server_files.ServerFilesTests.test_create_move_copy_and_conflicts', 'tests.test_server_files.ServerFilesTests.test_trash_restore_and_conflicting_original', 'tests.test_file_editor.FileEditorTests.test_edit_backup_conflict_and_mode'), 'files_access_regression': ('tests.test_server_files.ServerFilesTests.test_access_requires_owner_token', 'tests.test_server_files.ServerFilesTests.test_readonly_rejects_all_mutations', 'tests.test_server_files.ServerFilesTests.test_same_prefix_sibling_and_all_public_path_inputs_are_confined'), 'word_document_regression': ('tests.test_word_files.WordFilesTests', 'tests.test_commercial_word.CommercialWordTests')})

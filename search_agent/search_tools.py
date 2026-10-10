import json
import hashlib
import io
import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from docx import Document
from core.governance import agent_tool
from pypdf import PdfReader

from core.permissions import require_permission
from core.file_paths import knowledge_root
from core.confined_paths import confined_path
from core.runtime_context import ensure_runtime_active, RunTimedOut
from core.run_lifecycle import RunCancelled


load_dotenv()

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = knowledge_root()

BLOCKED_PARTS = {".git", ".venv", "__pycache__", "node_modules", ".cora-trash", ".cora-staging"}
BLOCKED_NAMES = {".env", "credentials.json", "token.json"}

TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".py",
    ".yaml", ".yml", ".toml", ".html", ".css", ".js",
}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".docx", ".pdf"}
MAX_FILE_BYTES = int(os.getenv("CORA_MAX_DOCUMENT_BYTES", "5000000"))
MAX_TEXT_CHARS = int(os.getenv("CORA_MAX_DOCUMENT_CHARS", "120000"))
MAX_PDF_PAGES = int(os.getenv("CORA_MAX_PDF_PAGES", "100"))


def _require_permission(action: str) -> None:
    require_permission("local_research_agent", action)


def _safe_path(relative_path: str) -> Path:
    if Path(relative_path).is_absolute() or "\\" in relative_path or ".." in Path(relative_path).parts:
        raise ValueError("Usa un percorso relativo alla Libreria IA.")
    candidate = confined_path(KNOWLEDGE_ROOT, KNOWLEDGE_ROOT / relative_path)

    relative = candidate.relative_to(KNOWLEDGE_ROOT)
    if any(part in BLOCKED_PARTS for part in relative.parts):
        raise ValueError("Cartella protetta.")

    if candidate.name.lower() in BLOCKED_NAMES:
        raise ValueError("File protetto.")

    return candidate


def _iter_documents(directory: str = ".", recursive: bool = True) -> Iterable[Path]:
    base = _safe_path(directory)
    if not base.exists() or not base.is_dir():
        raise ValueError("Cartella della Libreria IA non disponibile.")

    def walk():
        visited = 0
        for folder, dirs, files in os.walk(base, followlinks=False):
            ensure_runtime_active()
            dirs[:] = sorted(d for d in dirs if d not in BLOCKED_PARTS and not (Path(folder)/d).is_symlink())
            for name in sorted(files):
                visited += 1
                if visited > 2000:
                    raise ValueError("Limite di scansione raggiunto: restringi la cartella.")
                path = Path(folder)/name
                if path.is_symlink() or name.lower() in BLOCKED_NAMES or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                yield _safe_path(path.relative_to(KNOWLEDGE_ROOT).as_posix())
            if not recursive:
                break
    return walk()


def _activity(action: str, *, path: str = ".", query: str = ""):
    # Content-bearing progress stays in the authenticated live stream, not diagnostics.
    from core.runtime import current_run
    from core.event_bus import bus
    run = current_run.get()
    if run:
        bus.publish("library.activity", "library", run_id=run.id, thread_id=run.thread_id,
                    payload={"action": action, "path": path[:500], "query": query[:300]})


def _read_docx(path: Path) -> str:
    document = Document(path)
    parts = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    for table_index, table in enumerate(document.tables, start=1):
        parts.append(f"\n[TABELLA {table_index}]")
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            parts.append(" | ".join(cells))

    return "\n".join(parts)


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as error:
            raise ValueError("PDF cifrato: impossibile leggerlo senza password.") from error

    parts = []
    for page_index, page in enumerate(reader.pages[:MAX_PDF_PAGES], start=1):
        ensure_runtime_active()
        text = (page.extract_text() or "").strip()
        if text:
            parts.append(f"[PAGINA {page_index}]\n{text}")

    if len(reader.pages) > MAX_PDF_PAGES:
        parts.append(
            f"[PDF TRONCATO: lette {MAX_PDF_PAGES} pagine su {len(reader.pages)}]"
        )

    return "\n\n".join(parts)


def _read_document(path: Path) -> str:
    path = _safe_path(path.relative_to(KNOWLEDGE_ROOT).as_posix())
    if not path.is_file():
        raise ValueError("Il percorso non è un file normale.")
    ensure_runtime_active()
    _activity("read", path=path.relative_to(KNOWLEDGE_ROOT).as_posix())
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(
            f"File troppo grande: limite {MAX_FILE_BYTES} byte."
        )

    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = _read_docx(path)
    elif suffix == ".pdf":
        text = _read_pdf(path)
    elif suffix in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError("Formato non supportato.")

    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "\n\n[TESTO TRONCATO PER LIMITE DI SICUREZZA]"

    return text


@agent_tool('local_research_agent', capability='list_local_documents', actions=('list_documents',), effect='read', retry='safe')
def list_local_documents(
    directory: str = ".",
    extension: str = "",
    recursive: bool = True,
) -> str:
    """Elenca i documenti locali accessibili al Local Research Agent."""
    try:
        _require_permission("list_documents")
        _safe_path(directory)
        _activity("list", path=directory)
        normalized_extension = extension.strip().lower()
        if normalized_extension and not normalized_extension.startswith("."):
            normalized_extension = "." + normalized_extension

        results = []
        for path in _iter_documents(directory, recursive):
            if normalized_extension and path.suffix.lower() != normalized_extension:
                continue

            stat = path.stat()
            results.append({
                "path": str(path.relative_to(KNOWLEDGE_ROOT)),
                "type": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_timestamp": stat.st_mtime,
            })

            if len(results) >= 200:
                break

        return json.dumps({
            "library": "Libreria IA",
            "count": len(results),
            "documents": results,
        }, ensure_ascii=False, indent=2)
    except (RunCancelled, RunTimedOut):
        raise
    except Exception as error:
        return json.dumps({"status":"error","error":f"Errore durante l'elenco dei documenti: {error}"}, ensure_ascii=False)


@agent_tool('local_research_agent', capability='read_local_document', actions=('read_document',), effect='read', retry='safe')
def read_local_document(relative_path: str) -> str:
    """Legge file testuali, Word .docx e PDF autorizzati."""
    try:
        _require_permission("read_document")
        path = _safe_path(relative_path)

        if not path.exists() or not path.is_file():
            return json.dumps({"status":"error","error":"Il documento richiesto non esiste."}, ensure_ascii=False)

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return json.dumps({"status":"error","error":"Formato non supportato. Formati disponibili: " + ", ".join(sorted(SUPPORTED_EXTENSIONS))},ensure_ascii=False)

        text = _read_document(path)
        return (
            f"SOURCE_PATH: {path.relative_to(KNOWLEDGE_ROOT)}\n"
            f"SOURCE_TYPE: {path.suffix.lower()}\n"
            f"SOURCE_SHA256: {hashlib.sha256(path.read_bytes()).hexdigest()}\n"
            f"--- DOCUMENT CONTENT ---\n{text}"
        )
    except (RunCancelled, RunTimedOut):
        raise
    except Exception as error:
        return json.dumps({"status":"error","error":f"Errore durante la lettura del documento: {error}"}, ensure_ascii=False)


@agent_tool('local_research_agent', capability='search_local_documents', actions=('search_documents',), effect='read', retry='safe')
def search_local_documents(
    query: str,
    directory: str = ".",
    max_results: int = 10,
) -> str:
    """
    Cerca parole nei nomi e nei contenuti della Libreria IA e restituisce estratti con il percorso
    della fonte. È una ricerca lessicale locale, non usa Internet.
    """
    try:
        _require_permission("search_documents")
        _safe_path(directory)
        _activity("search", path=directory, query=query)
        terms = [term.casefold() for term in query.split() if len(term.strip()) >= 2]
        if not terms:
            return json.dumps({"status":"error","error":"La query non contiene termini utili."}, ensure_ascii=False)

        matches = []
        skipped = 0
        scanned = 0
        for path in _iter_documents(directory, recursive=True):
            ensure_runtime_active()
            scanned += 1
            try:
                text = _read_document(path)
            except (RunCancelled, RunTimedOut):
                raise
            except Exception:
                skipped += 1
                text = ""

            folded = text.casefold()
            name = path.relative_to(KNOWLEDGE_ROOT).as_posix().casefold()
            score = sum(folded.count(term) + 5 * name.count(term) for term in terms)
            if score <= 0:
                continue

            positions = [folded.find(term) for term in terms if folded.find(term) >= 0]
            first_position = min(positions) if positions else 0
            start = max(0, first_position - 350)
            end = min(len(text), first_position + 850)
            excerpt = text[start:end].strip()

            matches.append({
                "path": str(path.relative_to(KNOWLEDGE_ROOT)),
                "score": score,
                "excerpt": excerpt,
            })

        matches.sort(key=lambda item: item["score"], reverse=True)
        matches = matches[:max(1, min(max_results, 30))]

        return json.dumps({
            "query": query,
            "scanned": scanned,
            "skipped_contents": skipped,
            "results": matches,
            "scope": "Libreria IA; ricerca lessicale nei nomi e nei contenuti leggibili",
        }, ensure_ascii=False, indent=2)
    except (RunCancelled, RunTimedOut):
        raise
    except Exception as error:
        return json.dumps({"status":"error","error":f"Errore durante la ricerca locale: {error}"}, ensure_ascii=False)


@agent_tool('local_research_agent', capability='create_word_document', actions=(), effect='write', retry='never', conditional_actions=('create_word_document', 'overwrite_word_document'))
def create_word_document(
    title: str,
    content: str,
    filename: str = "nota.docx",
    overwrite: bool = False,
) -> str:
    """
    Crea un documento Word .docx dentro la cartella documenti autorizzata.
    La sovrascrittura di un file esistente è bloccata dalla policy corrente.
    """
    try:
        clean_name = filename.strip() or "nota.docx"
        if not clean_name.lower().endswith(".docx"):
            clean_name += ".docx"

        output_path = _safe_path(clean_name)

        if output_path.exists():
            if not overwrite:
                return json.dumps({
                    "status": "error",
                    "error": "Il file esiste già. Usa l'aggiornamento non distruttivo oppure scegli un nuovo nome.",
                }, ensure_ascii=False)
            _require_permission("overwrite_word_document")
        else:
            _require_permission("create_word_document")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        document = Document()
        if title.strip():
            document.add_heading(title.strip(), level=1)

        paragraphs = content.splitlines() or [content]
        for paragraph in paragraphs:
            text = paragraph.strip()
            if text:
                document.add_paragraph(text)

        from core.library_tools import publish_bytes
        buffer = io.BytesIO()
        document.save(buffer)
        if len(buffer.getvalue()) > MAX_FILE_BYTES:
            raise ValueError("Documento oltre il limite di dimensione.")
        # Exclusive publication prevents overwriting a file created since the check.
        publish_bytes(output_path, buffer.getvalue(), replace=False)
        return json.dumps({
            "status": "ok",
            "path": str(output_path.relative_to(KNOWLEDGE_ROOT)),
        }, ensure_ascii=False)
    except Exception as error:
        return json.dumps({
            "status": "error",
            "error": str(error),
        }, ensure_ascii=False)


@agent_tool('local_research_agent', capability='append_word_document', actions=('append_word_document',), effect='write', retry='never')
def append_word_document(
    relative_path: str,
    content: str,
    heading: str = "",
    expected_sha256: str = "",
) -> str:
    """
    Propone aggiunta a un Word: richiede conferma e SHA256 restituito dalla lettura.
    """
    try:
        _require_permission("append_word_document")
        path = _safe_path(relative_path)

        if not path.exists() or not path.is_file():
            return json.dumps({
                "status": "error",
                "error": "Il documento Word richiesto non esiste.",
            }, ensure_ascii=False)

        if path.suffix.lower() != ".docx":
            return json.dumps({
                "status": "error",
                "error": "L'aggiornamento è consentito solo per file .docx.",
            }, ensure_ascii=False)

        from core.library_tools import checked_file, archive_previous, publish_bytes
        from core.server_files import operation
        path, before = checked_file(relative_path, expected_sha256)
        document = Document(io.BytesIO(before))
        if heading.strip():
            document.add_heading(heading.strip(), level=2)

        added = 0
        for paragraph in content.splitlines() or [content]:
            text = paragraph.strip()
            if text:
                document.add_paragraph(text)
                added += 1

        if added == 0:
            return json.dumps({
                "status": "error",
                "error": "Nessun contenuto da aggiungere.",
            }, ensure_ascii=False)

        buffer = io.BytesIO()
        document.save(buffer)
        if len(buffer.getvalue()) > MAX_FILE_BYTES:
            raise ValueError("Documento oltre il limite di dimensione.")
        with operation():
            path, before = checked_file(relative_path, expected_sha256)
            archive_previous(path, before)
            publish_bytes(path, buffer.getvalue(), replace=True)
        return json.dumps({
            "status": "ok",
            "path": str(path.relative_to(KNOWLEDGE_ROOT)),
            "paragraphs_added": added,
        }, ensure_ascii=False)
    except Exception as error:
        return json.dumps({
            "status": "error",
            "error": str(error),
        }, ensure_ascii=False)


LOCAL_RESEARCH_TOOLS = [
    list_local_documents,
    search_local_documents,
    read_local_document,
    create_word_document,
    append_word_document,
]


from core.calendar_tools import calendar_tools_for
LOCAL_RESEARCH_TOOLS += calendar_tools_for("local_research_agent")

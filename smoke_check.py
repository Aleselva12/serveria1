"""Smoke check non distruttivo per il proof of concept Cora."""

from __future__ import annotations

import compileall
import importlib
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from core.permissions import validate_permission_configuration


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODULES = [
    "core.auth",
    "core.runtime",
    "core.protocol",
    "core.event_bus",
    "core.governance",
    "core.context_budget",
    "core.capabilities",
    "core.capability_contracts",
    "core.registry",
    "core.logging",
    "core.memory",
    "core.permissions",
    "core.component_bus",
    "core.access",
    "core.approvals",
    "core.run_lifecycle",
    "core.runtime_context",
    "core.runtime_status",
    "core.permissions_api",
    "core.runtime_api",
    "core.orchestration",
    "core.plans",
    "local_tools",
    "search_agent.search_tools",
    "search_agent.search_graph",
    "audio_agent.audio_tools",
    "audio_agent.audio_graph",
    "email_agent.email_connector",
    "email_agent.email_tools",
    "email_agent.email_graph",
    "structure_agent.structure_tools",
    "structure_agent.structure_graph",
    "tools",
    "prompt",
    "graph",
]


def check_syntax() -> bool:
    print("[1/4] Controllo sintassi Python...")
    ok = compileall.compile_dir(
        str(ROOT),
        quiet=1,
        force=True,
        rx=re.compile(r".*[\\/](\.venv|venv|__pycache__|\.git)[\\/].*"),
    )
    print("  OK" if ok else "  ERRORE")
    return ok


def check_imports() -> bool:
    print("[2/4] Controllo import principali...")
    ok = True

    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
            print(f"  OK  {module_name}")
        except Exception as error:
            ok = False
            print(f"  ERR {module_name}: {error}")

    return ok


def check_permissions() -> bool:
    print("[3/4] Controllo copertura Permission Engine...")
    report = validate_permission_configuration()
    if report["valid"]:
        print(f"  OK  {report['rule_count']} regole / {len(report['actors'])} attori")
        return True
    for item in report["duplicates"]:
        print(f"  ERR regola duplicata: {item['actor']}::{item['action']}")
    for item in report["missing"]:
        print(f"  ERR regola mancante: {item['actor']}::{item['action']}")
    return False


def check_configuration() -> None:
    print("[4/4] Configurazione rilevata...")
    print(f"  OLLAMA_MODEL={os.getenv('OLLAMA_MODEL', 'gpt-oss:20b')}")
    print(f"  OLLAMA_BASE_URL={os.getenv('OLLAMA_BASE_URL', 'http://localhost:11435')}")

    optional = {
        "CORA_OWNER_TOKEN": "compatibilita router isolati; non sostituisce login",
        "CORA_DB_POOL_SIZE": "pool PostgreSQL massimo",
        "CORA_DB_POOL_TIMEOUT": "attesa pool PostgreSQL",
        "CORA_KNOWLEDGE_ROOT": "Local Research Agent",
        "CORA_AUDIO_ROOT": "Audio Agent",
        "CORA_DIARIZATION_MODEL": "diarizzazione audio",
        "CORA_GMAIL_CREDENTIALS_PATH": "Gmail",
        "CORA_QUOTE_ROOT": "preventivi PDF",
        "CORA_LOG_ROOT": "logging strutturato",
        "CORA_DATABASE_URL": "PostgreSQL + pgvector",
        "CORA_STRUCTURE_WORKSPACE": "workspace Structure Agent",
    }

    for name, purpose in optional.items():
        value = os.getenv(name)
        status = value if value else "(default / non configurato)"
        print(f"  {name}={status}  [{purpose}]")


def main() -> int:
    syntax_ok = check_syntax()
    imports_ok = check_imports()
    permissions_ok = check_permissions()
    check_configuration()

    if syntax_ok and imports_ok and permissions_ok:
        print("\nSMOKE CHECK: OK")
        return 0

    print("\nSMOKE CHECK: FALLITO")
    return 1


if __name__ == "__main__":
    sys.exit(main())

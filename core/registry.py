from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict
from pathlib import Path

from core.capabilities import Capability, ComponentDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[1]


COMPONENTS: tuple[ComponentDefinition, ...] = (
    ComponentDefinition(
        id="supervisor",
        name="Cora Supervisor",
        kind="core",
        description="Orchestratore centrale LangGraph che risponde o delega ai componenti disponibili.",
        module="graph",
        capabilities=(
            Capability("route_requests", "Instrada richieste verso tool e agenti specializzati."),
            Capability("conversation_state", "Mantiene stato volatile della conversazione tramite LangGraph MemorySaver."),
        ),
        dependencies=("ollama",),
    ),
    ComponentDefinition(
        id="local_research_agent",
        name="Local Research Agent",
        kind="agent",
        description="Ricerca, legge, analizza e può creare documenti Word locali autorizzati.",
        module="search_agent.search_graph",
        capabilities=(
            Capability("list_documents", "Elenca documenti locali autorizzati."),
            Capability("search_documents", "Esegue ricerca lessicale nei documenti locali."),
            Capability("read_documents", "Legge file testuali e documenti Word .docx autorizzati."),
            Capability("create_word_document", "Crea documenti Word .docx nella cartella autorizzata su richiesta esplicita."),
            Capability("analyze_documents", "Analizza i contenuti tramite il modello locale."),
        ),
        dependencies=("ollama",),
    ),
    ComponentDefinition(
        id="audio_agent",
        name="Audio Agent",
        kind="agent",
        description="Trascrive e analizza file audio locali autorizzati.",
        module="audio_agent.audio_graph",
        capabilities=(
            Capability("list_audio", "Elenca file audio autorizzati."),
            Capability("transcribe_audio", "Trascrive audio localmente con faster-whisper."),
            Capability("diarize_speakers", "Può distinguere speaker se un modello pyannote locale è configurato."),
            Capability("save_transcript", "Salva trascrizioni in file di testo quando richiesto."),
        ),
        dependencies=("ollama", "faster_whisper"),
    ),
    ComponentDefinition(
        id="email_quotes_agent",
        name="Email & Quotes Agent",
        kind="agent",
        description="Lavora su archivio Gmail, sintesi/classificazione, bozze e preventivi PDF.",
        module="email_agent.email_graph",
        capabilities=(
            Capability("search_email", "Cerca nell'archivio Gmail autorizzato."),
            Capability("get_email_by_id", "Recupera una singola email tramite Gmail message ID."),
            Capability("daily_email_digest", "Recupera e sintetizza le email di una giornata."),
            Capability("summarize_email", "Riassume una singola email recuperata dall'archivio."),
            Capability("classify_email", "Classifica una singola email come urgent, informational, spam o needs_review."),
            Capability("draft_email", "Prepara testo email e può salvare bozze su richiesta esplicita."),
            Capability("generate_quote_pdf", "Genera preventivi PDF da dati strutturati."),
        ),
        dependencies=("ollama",),
    ),
    ComponentDefinition(
        id="calculator_tool",
        name="Calculator Tool",
        kind="tool",
        description="Calcolatrice locale limitata ad aritmetica di base.",
        module="local_tools",
        capabilities=(Capability("calculate", "Esegue espressioni aritmetiche consentite."),),
    ),
    ComponentDefinition(
        id="system_status_tool",
        name="System Status Tool",
        kind="tool",
        description="Legge utilizzo reale di CPU, RAM e disco.",
        module="local_tools",
        capabilities=(Capability("system_status", "Restituisce metriche locali di CPU, RAM e disco."),),
    ),
    ComponentDefinition(
        id="project_files_tool",
        name="Project Files Tool",
        kind="tool",
        description="Elenca e legge file testuali autorizzati della repository.",
        module="local_tools",
        capabilities=(
            Capability("list_project_files", "Elenca file consentiti dentro il progetto."),
            Capability("read_project_file", "Legge file testuali consentiti dentro il progetto."),
        ),
    ),
    ComponentDefinition(
        id="fastapi_backend",
        name="FastAPI Backend",
        kind="interface",
        description="API locale usata dalla UI per health, capabilities e chat.",
        module="api",
        capabilities=(
            Capability("health_api", "Espone lo stato generale del backend."),
            Capability("capabilities_api", "Espone il registro strutturale."),
            Capability("chat_api", "Espone l'ingresso chat verso Cora."),
        ),
    ),
    ComponentDefinition(
        id="react_ui",
        name="React UI",
        kind="interface",
        description="Interfaccia web locale React/Vite.",
        capabilities=(Capability("chat_ui", "Permette di interagire con Cora dal browser."),),
    ),
)


def _module_available(module_name: str | None) -> bool:
    if not module_name:
        return True
    return importlib.util.find_spec(module_name) is not None


def _dependency_status(name: str) -> bool | None:
    checks = {
        "ollama": bool(os.getenv("OLLAMA_BASE_URL", "http://localhost:11435")),
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
    }
    return checks.get(name)


def component_status(component: ComponentDefinition) -> dict:
    dependency_status = {
        dependency: _dependency_status(dependency)
        for dependency in component.dependencies
    }
    module_available = _module_available(component.module)

    unavailable_dependency = any(value is False for value in dependency_status.values())
    available = module_available and not unavailable_dependency

    return {
        **component.to_dict(),
        "available": available,
        "module_available": module_available,
        "dependency_status": dependency_status,
    }


def get_registry(kind: str | None = None) -> dict:
    selected = [
        component
        for component in COMPONENTS
        if kind is None or component.kind == kind
    ]

    return {
        "project": "Cora Lab",
        "component_count": len(selected),
        "components": [component_status(component) for component in selected],
    }


def get_agents() -> list[dict]:
    return get_registry(kind="agent")["components"]


def get_component(component_id: str) -> dict | None:
    for component in COMPONENTS:
        if component.id == component_id:
            return component_status(component)
    return None


def registry_json(kind: str | None = None) -> str:
    return json.dumps(get_registry(kind=kind), ensure_ascii=False, indent=2)

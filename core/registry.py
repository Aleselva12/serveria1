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
        id="event_logging",
        name="Event Logging",
        kind="core",
        description="Registro append-only locale degli eventi strutturati di Cora.",
        module="core.logging",
        capabilities=(
            Capability("log_events", "Registra eventi con timestamp, componente, stato e durata."),
            Capability("read_recent_events", "Permette di leggere gli eventi recenti per diagnosi."),
        ),
    ),
    ComponentDefinition(
        id="persistent_memory",
        name="Persistent Memory",
        kind="core",
        description="Memoria locale persistente SQLite separata dallo storico eventi.",
        module="core.memory",
        capabilities=(
            Capability("save_memory", "Crea o aggiorna memorie strutturate autorizzate."),
            Capability("search_memory", "Cerca memorie persistenti per tipo, chiave e contenuto."),
            Capability("delete_memory", "Elimina una memoria per ID su richiesta esplicita."),
            Capability("memory_stats", "Espone statistiche sintetiche della memoria."),
        ),
    ),
    ComponentDefinition(
        id="structure_agent",
        name="Structure Agent",
        kind="agent",
        description="Agente di livello sistema per planning, evaluation, control e management di Cora.",
        module="structure_agent.structure_graph",
        capabilities=(
            Capability("plan_work", "Scompone obiettivi in passi, dipendenze, checkpoint e assegnazioni."),
            Capability("evaluate_results", "Valuta piani, output o implementazioni rispetto a criteri e vincoli espliciti."),
            Capability("control_system", "Controlla struttura dichiarata, stato runtime, memoria e log per anomalie o mismatch."),
            Capability("manage_workflow", "Mantiene una vista di priorità, dipendenze, handoff e prossimi passi."),
            Capability("inspect_structure", "Interroga il registro centrale di componenti e capacità."),
            Capability("inspect_runtime", "Legge stato CPU, RAM e disco."),
            Capability("inspect_memory_status", "Legge statistiche tecniche della memoria persistente."),
            Capability("inspect_events", "Analizza eventi recenti del log strutturato."),
            Capability("control_snapshot", "Ottiene una fotografia tecnica combinata del sistema."),
            Capability("inspect_project_files", "Elenca e legge file testuali autorizzati del progetto."),
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

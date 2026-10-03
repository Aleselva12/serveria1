from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import asdict
from pathlib import Path

from core.capabilities import Capability, ComponentDefinition


PROJECT_ROOT = Path(__file__).resolve().parents[1]


COMPONENTS: tuple[ComponentDefinition, ...] = (
    ComponentDefinition(id="capability_execution", name="Capability Contracts", kind="core", module="core.governance",
        description="Registry eseguibile con contratti versionati, schemi stretti e confine unico di esecuzione.",
        capabilities=(Capability("execute_capability", "Valida input, permessi e risultato prima di restituire un esito comune."),
                      Capability("capability_registry", "Espone i contratti effettivi usati dagli agenti e dal catalogo Tools."))),
    ComponentDefinition(id="app_auth", name="Accesso personale", kind="core", module="core.auth",
        description="Login del proprietario, sessioni revocabili di sette giorni e protezione globale API.",
        capabilities=(Capability("owner_login", "Autentica il proprietario prima di accedere alle API."),)),
    ComponentDefinition(
        id="calendar", name="Calendario", kind="core",
        description="Calendario PostgreSQL condiviso tra interfaccia e tool: storico, recupero e proposte agenti approvabili.",
        module="core.calendar",
        capabilities=(
            Capability("calendar_events", "Legge e gestisce gli eventi persistenti nelle viste mese e giorno."),
            Capability("calendar_proposals", "Gestisce le proposte degli agenti con conferma utente e controllo versione."),
            Capability("calendar_history", "Conserva lo storico e recupera gli eventi eliminati."),
        ),
    ),
    ComponentDefinition(
        id="supervisor",
        name="Cora · Agente centrale",
        kind="core",
        description="Agente principale di Cora e orchestratore provvisorio della chat; risponde direttamente o delega ai componenti disponibili.",
        module="graph",
        capabilities=(
            Capability("route_requests", "Riceve tutte le richieste della chat e le instrada verso tool e agenti specializzati quando necessario."),
            Capability("conversation_state", "Ricostruisce il contesto recente dalla cronologia persistente PostgreSQL."),
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
        id="permission_engine",
        name="Permission Engine",
        kind="core",
        description="Controllo deterministico dei permessi per azione e policy di approvazione.",
        module="core.permissions",
        capabilities=(
            Capability("check_permission", "Verifica deterministicamente se un'azione è AUTO, CONFIRM o BLOCKED."),
            Capability("permission_manifest", "Espone le regole di permesso configurate per attore e azione."),
            Capability("validate_permissions", "Verifica la copertura delle azioni implementate."),
            Capability("owner_access", "Unifica il gate proprietario per le API protette, con compatibilità per i token legacy."),
        ),
    ),
    ComponentDefinition(
        id="component_protocol",
        name="Component Protocol & Bus",
        kind="core",
        description="Contratto tipizzato TaskEnvelope/ComponentResult e comunicazione diretta in-process tra componenti.",
        module="core.component_bus",
        capabilities=(
            Capability("typed_tasks", "Scambia richieste strutturate tra componenti senza serializzazione o hop di rete."),
            Capability("typed_results", "Normalizza risultati, artefatti, osservazioni ed errori dei componenti."),
            Capability("runtime_bus_state", "Espone lo stato locale busy/ready/error dei componenti attraversati dal bus."),
        ),
    ),
    ComponentDefinition(
        id="runtime_lifecycle",
        name="Runtime Lifecycle",
        kind="core",
        description="Stato persistente dei run e delle deleghe, separato dalle tracce tecniche.",
        module="core.runtime",
        capabilities=(
            Capability("run_state", "Gestisce queued, running, waiting_approval e stati terminali."),
            Capability("child_runs", "Collega le deleghe specialistiche al run padre."),
            Capability("cooperative_cancel", "Registra richieste di cancellazione per i confini sicuri del runtime."),
        ),
    ),
    ComponentDefinition(
        id="generic_approvals",
        name="Generic Approvals",
        kind="core",
        description="Workflow generico persistente per azioni con policy CONFIRM, riutilizzabile dai domini futuri.",
        module="core.governance",
        capabilities=(
            Capability("request_approval", "Crea richieste persistenti soltanto per azioni CONFIRM."),
            Capability("resolve_approval", "Permette al proprietario di approvare o rifiutare."),
            Capability("execute_approved_tool", "Esegue una sola volta il tool e i parametri mostrati, senza rilasciare grant riutilizzabili."),
        ),
    ),
    ComponentDefinition(
        id="orchestrator_owner_resolver",
        name="Orchestrator Owner Resolver",
        kind="core",
        description="Mantiene ownership='orchestrator' finché l'orchestratore neurale reale non è implementato.",
        module="core.orchestration",
        capabilities=(
            Capability("resolve_plan_owner", "Risoluzione provvisoria e deterministica dell'owner dei piani."),
        ),
    ),
    ComponentDefinition(
        id="planning_artifacts",
        name="Planning Artifacts",
        kind="core",
        description="Persistenza locale strutturata di plan, evaluation e management artifact.",
        module="core.plans",
        capabilities=(
            Capability("create_plan_record", "Crea piani strutturati con owner orchestrator e target_component separato."),
            Capability("save_plan_record", "Salva piani nel workspace autorizzato."),
            Capability("create_evaluation_record", "Crea evaluation strutturate."),
            Capability("save_management_record", "Salva stato di management nel workspace autorizzato."),
        ),
    ),
    ComponentDefinition(
        id="persistent_memory",
        name="Persistent Memory",
        kind="core",
        description="Memoria persistente PostgreSQL con pgvector, separata dalla cronologia completa e dai log.",
        module="core.memory",
        capabilities=(
            Capability("save_memory", "Crea o aggiorna memorie strutturate autorizzate."),
            Capability("search_memory", "Cerca memorie persistenti per tipo, chiave e contenuto."),
            Capability("delete_memory", "Elimina una memoria per ID su richiesta esplicita."),
            Capability("memory_stats", "Espone statistiche sintetiche della memoria."),
            Capability("system_context", "Gestisce il contesto permanente configurato dall’utente e caricato in ogni richiesta."),
            Capability("episodic_memory", "Registra e consulta episodi sintetici separati dai log tecnici."),
            Capability("working_memory", "Mantiene stato operativo temporaneo per agente e thread con scadenza."),
            Capability("memory_provenance", "Registra la provenienza delle memorie persistenti."),
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
            Capability("save_plan_artifact", "Salva piani strutturati nel workspace dedicato."),
            Capability("save_evaluation_artifact", "Salva evaluation strutturate nel workspace dedicato."),
            Capability("save_management_artifact", "Salva artefatti di management nel workspace dedicato."),
            Capability("inspect_permissions", "Legge il manifest deterministico dei permessi per azione."),
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
        description="Ricerca e analizza documenti locali autorizzati; crea e aggiorna Word in modo non distruttivo.",
        module="search_agent.search_graph",
        capabilities=(
            Capability("list_documents", "Elenca documenti locali autorizzati."),
            Capability("search_documents", "Esegue ricerca lessicale nei documenti locali."),
            Capability("read_documents", "Legge file testuali, Word .docx e PDF testuali autorizzati."),
            Capability("create_word_document", "Crea documenti Word .docx nella cartella autorizzata su richiesta esplicita."),
            Capability("append_word_document", "Aggiunge contenuto a Word esistenti senza cancellare quello precedente."),
            Capability("analyze_documents", "Analizza i contenuti tramite il modello locale."),
        ),
        dependencies=("ollama", "pypdf"),
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
            Capability("memory_api", "Espone contesto permanente, memoria semantica, episodica e working memory."),
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
        "pypdf": importlib.util.find_spec("pypdf") is not None,
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

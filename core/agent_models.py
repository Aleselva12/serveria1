"""Owner-selected inference bindings; no agent tools can change this registry."""
import json
import os
import tempfile
import threading
from pathlib import Path
from fastapi import HTTPException

ROLES = {"supervisor": "supervisor", "programmer_agent": "programmer",
         "structure_agent": "structure", "local_research_agent": "research",
         "audio_agent": "audio", "email_quotes_agent": "email"}
_lock = threading.RLock()


def path():
    from core.models import RUNTIME_SETTINGS_PATH
    return RUNTIME_SETTINGS_PATH.parent / "agent-models.json"


def bindings():
    file = path()
    with _lock:
        if not file.exists():
            return {}
        try:
            value = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or any(role not in ROLES.values() or not isinstance(row, dict)
                    or not isinstance(row.get('model'), str) or not isinstance(row.get('machine_id'), str)
                    for role, row in value.items()):
                raise ValueError()
            return value
        except (ValueError, OSError) as error:
            raise RuntimeError("Assegnazioni agenti non leggibili; verifica agent-models.json.") from error


def binding(role):
    return bindings().get(role)


def remote_machine(machine_id, model):
    from core.machines_api import _find, _settings
    from core.runtime_profile import runtime_mode
    if runtime_mode() != 'server':
        raise HTTPException(409, "Il profilo isolated non consente inferenza su worker remoti.")
    machine = _find(machine_id)
    settings = _settings(machine)
    if not settings['enabled']:
        raise HTTPException(409, "Worker OFF: abilitalo manualmente nella pagina Macchine.")
    if model != settings['selected_model']:
        raise HTTPException(409, "Il modello dell'agente non è più quello selezionato manualmente in Macchine. Aggiorna l'assegnazione.")
    return machine


def chat_on_worker(machine_id, model, params):
    from core.machines_api import _worker_call
    machine = remote_machine(machine_id, model)
    require_agent_chat(machine)
    # Native Ollama messages and tool schemas, not a flattened text prompt.
    payload = json.loads(json.dumps(params, default=lambda value: value.model_dump(exclude_none=True)))
    payload.update(model=model, stream=False)
    return _worker_call(machine, '/chat', payload, timeout=315)


def require_agent_chat(machine):
    from core.machines_api import _worker_call
    if _worker_call(machine, '/models').get('agent_chat') is not True:
        raise HTTPException(409, "Assegnazione salvata, ma il worker desktop va aggiornato per la chat agenti. "
                            "Apri Architettura e scarica l’aggiornamento worker. Il test in Macchine prova solo /generate.")


def save_binding(agent_id, machine_id, model):
    from core.models import list_ollama_models
    from core.machines_api import _worker_call
    if agent_id not in ROLES:
        raise HTTPException(404, "Agente non trovato.")
    if machine_id == 'inherit':
        row = None
    elif machine_id == 'local':
        if model not in {m['name'] for m in list_ollama_models()}:
            raise HTTPException(422, "Modello non installato nell’Ollama di Cora.")
        row = dict(machine_id=machine_id, model=model)
    else:
        machine = remote_machine(machine_id, model)
        available = _worker_call(machine, '/models')
        # Persist the owner's choice independently of the bridge version. An old
        # worker must still fail explicitly at inference, never fall back locally.
        if model not in {m.get('name') for m in available.get('models', [])}:
            raise HTTPException(422, "Modello non installato sul worker.")
        row = dict(machine_id=machine_id, model=model)
    with _lock:
        data = bindings()
        if row is None:
            data.pop(ROLES[agent_id], None)
        else:
            data[ROLES[agent_id]] = row
        file = path(); file.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=file.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, file)
        finally:
            if temporary: temporary.unlink(missing_ok=True)
    return row


def remote_ready(machine_id, model):
    from core.machines_api import _worker_call
    try:
        machine = remote_machine(machine_id, model)
        info = _worker_call(machine, '/models')
        return info.get('agent_chat') is True and model in {m.get('name') for m in info.get('models', [])}
    except (HTTPException, OSError, ValueError):
        return False

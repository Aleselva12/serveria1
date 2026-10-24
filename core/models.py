from __future__ import annotations
from core.generation_policy import output_tokens, model_timeout, run_timeout

import os
import json
import tempfile
from pathlib import Path
from core.ollama_transport import DEFAULT_BASE_URL, get_ollama_base_url, urlopen

from langchain_ollama import ChatOllama


def preserve_tool_argument_types(response):
    """Parse the argument envelope once, never reinterpret individual file strings.

    ChatOllama's nested-JSON heuristic changes valid content='{"nodes": ...}'
    into a dict. An encoded outer envelope avoids that heuristic losslessly.
    """
    if hasattr(response, "model_dump"):
        response = response.model_dump(exclude_none=True)
    if not isinstance(response, dict):
        return response
    message = response.get("message")
    if not isinstance(message, dict) or not message.get("tool_calls"):
        return response
    calls = []
    for call in message["tool_calls"]:
        function = call.get("function", {})
        arguments = function.get("arguments")
        if isinstance(arguments, dict):
            arguments = dict(arguments)
            if arguments.get("functionName") == function.get("name"):
                arguments.pop("functionName")
            call = {**call, "function": {**function, "arguments": json.dumps(arguments, ensure_ascii=False)}}
        calls.append(call)
    return {**response, "message": {**message, "tool_calls": calls}}


class ConfiguredChatOllama(ChatOllama):
    """Pass min_p through Ollama options; ChatOllama 1.1 omits that field."""
    min_p: float | None = None
    remote_machine_id: str | None = None
    cora_role: str = ""
    configuration_id: str = ""

    def _observe_reply(self, response):
        from core.model_evidence import observe
        observe(self.cora_role, self.model, self.remote_machine_id or 'local', self.configuration_id, response)


    def _create_chat_stream(self, messages, stop=None, **kwargs):
        if self.remote_machine_id:
            from core.agent_models import chat_on_worker
            response = chat_on_worker(self.remote_machine_id, self.model, self._chat_params(messages, stop=stop, **kwargs))
            self._observe_reply(response)
            yield preserve_tool_argument_types(response)
            return
        for response in super()._create_chat_stream(messages, stop, **kwargs):
            self._observe_reply(response)
            yield preserve_tool_argument_types(response)

    async def _acreate_chat_stream(self, messages, stop=None, **kwargs):
        if self.remote_machine_id:
            import asyncio
            from core.agent_models import chat_on_worker
            response = await asyncio.to_thread(chat_on_worker, self.remote_machine_id, self.model, self._chat_params(messages, stop=stop, **kwargs))
            self._observe_reply(response)
            yield preserve_tool_argument_types(response)
            return
        async for response in super()._acreate_chat_stream(messages, stop, **kwargs):
            self._observe_reply(response)
            yield preserve_tool_argument_types(response)

    def _chat_params(self, messages, stop=None, **kwargs):
        params = super()._chat_params(messages, stop=stop, **kwargs)
        if self.min_p is not None:
            options = params["options"]
            if hasattr(options, "model_dump"):
                options = options.model_dump(exclude_none=True)
            params["options"] = {**options, "min_p": self.min_p}
        return params


DEFAULT_MODEL = "gpt-oss:20b"


RUNTIME_SETTINGS_PATH = Path(os.getenv("CORA_RUNTIME_SETTINGS_PATH", "./data/runtime-settings.json"))

ROLE_MODEL_ENV = {
    "supervisor": "CORA_MODEL_SUPERVISOR",
    "research": "CORA_MODEL_RESEARCH",
    "audio": "CORA_MODEL_AUDIO",
    "email": "CORA_MODEL_EMAIL",
    "structure": "CORA_MODEL_STRUCTURE",
    "programmer": "CORA_MODEL_PROGRAMMER",
}


def get_model_keep_alive() -> str:
    """Keep the active Ollama model resident during an interactive session."""
    return os.getenv("CORA_MODEL_KEEP_ALIVE", "30m").strip() or "30m"


def _runtime_settings() -> dict:
    try:
        data = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


class RuntimeSettingsError(OSError):
    """The provider was reached, but the selected model could not be persisted."""


def save_runtime_model(model: str, *, models: list[dict] | None = None) -> dict:
    """Persist the operator-selected Ollama model for this Cora instance."""
    model = model.strip()
    available = {item["name"] for item in (models if models is not None else list_ollama_models())}
    if model not in available:
        raise ValueError("Il modello non risulta installato nell'istanza Ollama configurata.")
    data = _runtime_settings()
    data["model"] = model
    # Publish a complete JSON file so concurrent readers never see partial settings.
    temporary = None
    try:
        RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=RUNTIME_SETTINGS_PATH.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, RUNTIME_SETTINGS_PATH)
    except OSError as error:
        raise RuntimeSettingsError("Impossibile salvare il modello: verifica spazio e permessi dello stato persistente.") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return data


def list_running_ollama_models() -> set[str]:
    """Return models currently loaded in Ollama memory (/api/ps)."""
    with urlopen(get_ollama_base_url().rstrip("/") + "/api/ps", timeout=3) as response:
        payload = json.load(response)
    return {str(item.get("name", "")) for item in payload.get("models", []) if item.get("name")}


def list_ollama_models() -> list[dict]:
    """Return models physically available in the configured Ollama instance."""
    with urlopen(get_ollama_base_url().rstrip("/") + "/api/tags", timeout=3) as response:
        payload = json.load(response)
    running = list_running_ollama_models()
    return [
        {
            "name": str(item.get("name", "")),
            "size": int(item.get("size", 0) or 0),
            "running": str(item.get("name", "")) in running,
        }
        for item in payload.get("models", [])
        if item.get("name")
    ]


def get_model_name(role: str = "default") -> str:
    """
    Resolve the model assigned to a role.

    A per-agent assignment wins, then the persisted global selection and CORA_MODEL_*.
    OLLAMA_MODEL remains the
    backwards-compatible global fallback.
    """
    return resolve_model(role)['model']


def resolve_model(role: str = "default") -> dict:
    """One snapshot for both provider and model; no mixed reads during a save."""
    import hashlib
    from core.agent_models import binding
    selected = binding(role)
    if selected:
        model, source = selected['model'], 'agent_assignment'
    else:
        model, source = _default_selection(role)
    row = dict(role=role, model=model, machine_id=selected['machine_id'] if selected else 'local', source=source)
    # Source is included so restore-to-default is visible even for the same model.
    row['configuration_id'] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
    return row


def get_default_model_name(role: str = "default") -> str:
    """Global selection and environment, without a per-agent assignment."""
    return _default_selection(role)[0]


def _default_selection(role):
    runtime_model = str(_runtime_settings().get("model", "")).strip()
    if runtime_model:
        return runtime_model, 'global_selection'
    configured = os.getenv(ROLE_MODEL_ENV.get(role, ''), '').strip()
    if configured:
        return configured, 'role_environment'
    return os.getenv('OLLAMA_MODEL', DEFAULT_MODEL), 'default'


def model_options(model: str) -> dict:
    """Qwen3 hybrid profile; do not apply it to Qwen3.5 or other families."""
    family = model.rsplit("/", 1)[-1].split(":", 1)[0].lower()
    if family != "qwen3":
        return {}
    return {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "reasoning": True}


def get_chat_model(
    role: str = "default",
    *,
    temperature: float = 0.0,
    **kwargs,
) -> ChatOllama:
    """Create the local chat model assigned to a Cora role."""
    from core.context_budget import limit_tokens
    resolved = resolve_model(role)
    model = resolved['model']
    remote_id = resolved['machine_id'] if resolved['machine_id'] != 'local' else None
    profile = model_options(model)
    temperature = profile.pop("temperature", temperature)
    kwargs.update(profile)
    kwargs.setdefault("num_ctx", limit_tokens())
    kwargs.setdefault("num_predict", output_tokens())
    kwargs.setdefault("keep_alive", get_model_keep_alive())
    kwargs.setdefault("client_kwargs", {"timeout": model_timeout(), "trust_env": False})
    kwargs['metadata'] = {**(kwargs.get('metadata') or {}), 'cora_role': role,
                          'cora_model': model, 'cora_machine': resolved['machine_id'],
                          'cora_configuration_id': resolved['configuration_id']}
    # Ollama expects num_ctx/num_predict as model options; ChatOllama maps these fields.
    # Keep tool-capable models on the native /api/chat path.
    return ConfiguredChatOllama(
        model=model,
        remote_machine_id=remote_id,
        cora_role=role,
        configuration_id=resolved['configuration_id'],
        base_url=get_ollama_base_url(),
        temperature=temperature,
        **kwargs,
    )


def performance_configuration(target: str = "supervisor") -> dict:
    """Non-secret effective model/runtime settings stored with performance traces."""
    role_map = {
        "supervisor": "supervisor",
        "structure_agent": "structure",
        "local_research_agent": "research",
        "audio_agent": "audio",
        "email_quotes_agent": "email",
        "programmer_agent": "programmer",
    }
    role = role_map.get(target, target if target in ROLE_MODEL_ENV else "supervisor")
    resolved = resolve_model(role)
    machine_id = resolved['machine_id']
    return {
        'configuration_id': resolved['configuration_id'],
        'model_selection_source': resolved['source'],
        "inference_machine": machine_id,
        "inference_transport": "local-ollama" if machine_id == 'local' else 'worker-chat',

        "profile": os.getenv("CORA_PERFORMANCE_PROFILE", "default"),
        "target": target,
        "role": role,
        "model": resolved['model'],
        "models": {name: get_model_name(name) for name in ROLE_MODEL_ENV},
        "ollama_base_url": get_ollama_base_url() if machine_id == "local" else "worker:" + machine_id,
        "keep_alive": get_model_keep_alive(),
        "sampling": model_options(get_model_name(role)),
        "context_tokens": int(os.getenv("CORA_CONTEXT_TOKENS", "16384")),
        "output_tokens": output_tokens(),
        "model_timeout_seconds": model_timeout(),
        "run_timeout_seconds": run_timeout(),
        "queue_size": int(os.getenv("CORA_RUN_QUEUE_SIZE", "8")),
        "db_pool_size": int(os.getenv("CORA_DB_POOL_SIZE", "4")),
        "hardware_label": os.getenv("CORA_PERFORMANCE_HARDWARE_LABEL", "").strip(),
        "gpu_label": os.getenv("CORA_PERFORMANCE_GPU_LABEL", "").strip(),
    }

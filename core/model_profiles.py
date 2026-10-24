"""Model metadata, scoped to the exact machine/model; never changes selection."""
import json
import os
import threading
import time
from urllib.request import Request

_cache = {}
_lock = threading.RLock()

class ModelToolsUnsupported(ValueError):
    pass

class ModelEmptyResponse(ValueError):
    pass

class ModelConfigurationChanged(ValueError):
    pass


def parse_profile(info, resolved):
    requested = max(2048, int(os.getenv('CORA_CONTEXT_TOKENS', '16384')))
    metadata = info.get('model_info')
    metadata = metadata if isinstance(metadata, dict) else {}
    lengths = [v for k,v in metadata.items()
               if k.endswith('.context_length') and isinstance(v, int) and not isinstance(v, bool) and v > 0]
    maximum = min(lengths) if lengths else None
    capabilities = info.get('capabilities')
    known = isinstance(capabilities, list) and all(isinstance(v, str) for v in capabilities)
    thinking = info.get('thinking')
    values = thinking.get('values') if isinstance(thinking, dict) else None
    if not isinstance(values, list) or not values or not all(type(v) is bool or isinstance(v, str) for v in values):
        values = [False, True] if known and 'thinking' in capabilities else ([False] if known else [])
    return {**resolved, 'verified': bool(info), 'tools': ('tools' in capabilities) if known else None,
            'thinking_values': values, 'thinking_default': thinking.get('default') if isinstance(thinking, dict) else None,
            'context_max': maximum, 'context_tokens': min(requested, maximum) if maximum else requested,
            'transport': 'buffered' if resolved['machine_id'] != 'local' else 'streaming'}


def profile_for(resolved, *, refresh=False):
    from core.ollama_transport import get_ollama_base_url, urlopen
    key = (resolved['machine_id'], resolved['model'], get_ollama_base_url())
    with _lock:
        cached = _cache.get(key)
        if not refresh and cached and time.monotonic() - cached[0] < 60:
            return parse_profile(cached[1], resolved)
    info = {}
    try:
        if resolved['machine_id'] == 'local':
            request = Request(get_ollama_base_url() + '/api/show', data=json.dumps({'model':resolved['model']}).encode(), headers={'Content-Type':'application/json'})
            with urlopen(request, timeout=3) as response:
                raw = response.read(1_000_001)
            if len(raw) <= 1_000_000:
                info = json.loads(raw)
        else:
            from core.agent_models import remote_machine
            from core.machines_api import _worker_call
            machine = remote_machine(resolved['machine_id'], resolved['model'])
            info = _worker_call(machine, '/model-info', {'model':resolved['model']}, timeout=5)
        if not isinstance(info, dict) or info.get('error'):
            info = {}
    except Exception:
        # Old worker versions and unavailable metadata are explicitly unknown.
        # Actual inference retains its own errors and never falls back to local.
        info = {}
    with _lock:
        _cache[key] = (time.monotonic(), info)
        if len(_cache) > 64:
            _cache.pop(next(iter(_cache)))
    return parse_profile(info, resolved)

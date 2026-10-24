"""Metadata-only evidence of provider replies; never stores prompts or output text."""
import json
import os
from pathlib import Path
import tempfile
import threading
from datetime import datetime, timezone

_lock = threading.RLock()


def _path():
    from core.models import RUNTIME_SETTINGS_PATH
    return RUNTIME_SETTINGS_PATH.parent / 'model-observations.json'


def observations():
    with _lock:
        try:
            value = json.loads(_path().read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}


def matches_requested(requested, reported):
    if not reported: return None
    canonical = lambda name: name if ':' in name.rsplit('/', 1)[-1] else name + ':latest'
    return canonical(requested) == canonical(reported)


def observe(role, requested_model, machine_id, configuration_id, response):
    from core.agent_models import ROLES
    if role not in ROLES.values():
        return None
    if hasattr(response, 'model_dump'):
        response = response.model_dump(exclude_none=True)
    if not isinstance(response, dict) or response.get('done') is not True:
        return None
    reported = response.get('model')
    reported = reported if isinstance(reported, str) and reported else None
    row = dict(role=role, requested_model=requested_model, reported_model=reported,
               machine_id=machine_id, configuration_id=configuration_id,
               observed_at=datetime.now(timezone.utc).isoformat(),
               matches_requested=matches_requested(requested_model, reported))
    try:
        from core.runtime import current_run
        run = current_run.get()
        if run:
            row['run_id'] = run.id
            with run.lock:
                run.timings.setdefault('inference_observations', []).append(row)
        with _lock:
            data = observations(); data[role] = row
            file = _path(); file.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=file.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    json.dump(data, stream, ensure_ascii=False)
                    stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, file)
            finally:
                if temporary: temporary.unlink(missing_ok=True)
    except OSError:
        # Evidence I/O must not change the result of a successful inference.
        pass
    return row

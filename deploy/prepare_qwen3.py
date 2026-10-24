"""Explicit operator command: install/load Qwen3 8B before selecting it globally."""
import json
from urllib.request import Request
import psutil
from core.ollama_transport import get_ollama_base_url, urlopen
from core.models import save_runtime_model, model_options

MODEL = 'qwen3:8b'


def post(path, payload):
    request = Request(get_ollama_base_url() + path, data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
    # No inference deadline. This is a manually invoked setup operation.
    return urlopen(request, timeout=None)


def main():
    available = psutil.virtual_memory().available / 1024**3
    print(f'RAM disponibile: {available:.2f} GiB', flush=True)
    if available < 8:
        raise SystemExit('Preparazione interrotta: meno di 8 GiB disponibili. Il modello attivo non cambia.')
    print('Download qwen3:8b (~5,2 GB); selezione attuale conservata fino al caricamento riuscito.', flush=True)
    last = ''
    with post('/api/pull', {'model': MODEL, 'stream': True}) as response:
        for line in response:
            row = json.loads(line)
            if row.get('error'):
                raise RuntimeError(row['error'])
            status = row.get('status', '')
            if status != last:
                print(status, flush=True)
                last = status
    if last != 'success':
        raise RuntimeError('Download non confermato; modello attivo invariato.')
    with post('/api/show', {'model': MODEL}) as response:
        info = json.load(response)
    if not {'tools', 'thinking'}.issubset(info.get('capabilities', [])):
        raise RuntimeError('Ollama non conferma tools/thinking: verificare versione prima di attivare.')
    print('Caricamento di prova, contesto 8192; attendere senza avviare chat.', flush=True)
    # Empty prompt loads the model without starting a free-running generation.
    options = model_options(MODEL)
    options.pop('reasoning', None)
    with post('/api/generate', {'model': MODEL, 'prompt': '', 'stream': False,
                              'keep_alive': '30m', 'options': {**options, 'num_ctx': 8192}}) as response:
        loaded = json.load(response)
    if loaded.get('error') or not loaded.get('done'):
        raise RuntimeError('Caricamento non confermato; selezione invariata.')
    save_runtime_model(MODEL)
    print('Selezionato qwen3:8b per tutti i ruoli. Parametri Qwen3 automatici; timeout non reintrodotti.', flush=True)
    print('Caricamento riuscito non significa collaudo completato: provare somma.py e controllare RAM/swap e tempi.', flush=True)


if __name__ == '__main__':
    main()

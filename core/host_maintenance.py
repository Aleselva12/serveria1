"""Prerequisite alignment for owner-requested one-shot checks."""
import os
import time
from pathlib import Path
from updater.maintenance import digest


def ensure():
    if not os.getenv('CORA_UPDATER_URL'):
        return {'status':'not_configured'}
    from programmer_agent.releases import request
    from core.release_identity import revision
    expected = digest(Path(__file__).resolve().parents[1]/'updater')
    state = request('GET','/host/maintenance',timeout=5)
    if state.get('digest') == expected and not state.get('pending'):
        return {'status':'compatible','digest':expected}
    if not state.get('available'):
        raise ValueError('Installazione iniziale host-maintenance necessaria sul Debian.')
    commit = revision()
    if not commit: raise ValueError('Identità del rilascio Cora non disponibile.')
    if not state.get('pending'):
        request('POST','/host/maintenance',{'commit':commit,'digest':expected},timeout=60)
    for _ in range(120):
        time.sleep(2)
        try: state=request('GET','/host/maintenance',timeout=3)
        except ValueError: continue  # Read-only polling across the expected restart.
        result=state.get('lastUpdate',{})
        if result.get('status')=='recovery_required':
            raise ValueError('Recupero manuale updater necessario.')
        if not state.get('pending'):
            if state.get('digest')==expected:
                return {'status':'updated','commit':commit,'digest':expected,'rollbackAvailable':True}
            raise ValueError('Aggiornamento updater non applicato; controllare il ripristino host.')
    raise ValueError('Attesa updater scaduta; controllare lo stato host prima di riprovare.')

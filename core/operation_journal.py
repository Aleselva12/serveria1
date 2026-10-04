"""Durable invocation journal. Uncertainty is evidence, never permission to replay."""
import contextvars
import hashlib
import json
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from core.database import database_configured, db_connection
from core.run_states import DurabilityLost

class OperationConflict(RuntimeError):
    pass

current_approval = contextvars.ContextVar('operation_approval', default=None)


def begin(entry, payload):
    if not database_configured(): raise DurabilityLost('DatabaseNotConfigured')
    from core.runtime import current_run
    from core.runtime_context import _run_id
    run = current_run.get()
    root_id = run.id if run and run.durable else None
    run_id = _run_id.get() or root_id
    contract = entry['contract']
    identifier = uuid4()
    intent = hashlib.sha256((contract.id + "\n" + json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False)).encode()).hexdigest()
    try:
        with db_connection() as conn:
            if root_id:
                root = conn.execute('SELECT status,cancel_requested,stop_reason FROM runtime_runs WHERE id=%s FOR UPDATE',(UUID(root_id),)).fetchone()
                if not root: raise ValueError('Root run missing')
                if root['cancel_requested'] or root['status'] != 'running':
                    from core.runtime import RunStopped
                    run.reason = root['stop_reason'] or 'interrupted'
                    run.cancel.set()
                    raise RunStopped(run.reason)
            row = conn.execute('''INSERT INTO capability_operations
                (id,run_id,root_run_id,approval_id,capability_id,contract_version,contract_digest,
                 implementation_revision,actor,effect,retry,payload,status,intent_digest)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'started',%s)
                ON CONFLICT DO NOTHING RETURNING *''',
                (identifier, UUID(run_id) if run_id else None, UUID(root_id) if root_id else None,
                 current_approval.get(),contract.id,contract.version,entry['contract_digest'],entry['revision'],
                 contract.actor,contract.effect,contract.retry,Jsonb(payload),intent)).fetchone()
            if row:
                from core.domain_events import operation_state
                operation_state(conn,row,1)
    except Exception as error:
        raise DurabilityLost('OperationStartNotPersisted') from error
    if not row: raise OperationConflict('Esiste un’operazione identica in corso o con esito da verificare in Attività.')
    return str(identifier)


def finish(identifier, effect, result=None, error_type=None):
    if identifier is None: return
    if result is not None and result.status == 'ok': status = 'succeeded'
    elif result is not None and result.status == 'pending': status = 'pending'
    else: status = 'uncertain' if effect in {'write','delegate'} else 'failed'
    try:
        with db_connection() as conn:
            row = conn.execute('''UPDATE capability_operations SET status=%s,finished_at=NOW(),result=%s,error_type=%s
                WHERE id=%s AND status='started' RETURNING *''',
                (status,Jsonb(result.model_dump(mode='json')) if result is not None else None,
                 error_type or (result.error.code if result and result.error else None),UUID(identifier))).fetchone()
            if not row: raise ValueError('Operation already finalized')
            from core.domain_events import operation_state
            operation_state(conn,row,2)
    except Exception as error:
        raise DurabilityLost('OperationOutcomeNotPersisted') from error
    return status


def list_operations(limit=100, run_id=None, unresolved=False):
    clauses, params = [], []
    if run_id:
        clauses.append('(root_run_id=%s OR run_id=%s)');params += [UUID(run_id),UUID(run_id)]
    if unresolved: clauses.append("status='uncertain' AND review_outcome IS NULL")
    where = 'WHERE ' + ' AND '.join(clauses) if clauses else ''
    with db_connection() as conn:
        return conn.execute('SELECT * FROM capability_operations '+where+' ORDER BY created_at DESC LIMIT %s',
                            (*params,max(1,min(int(limit),500)))).fetchall()


def review(identifier, outcome, note, username):
    if outcome not in {'effect_verified','no_effect_verified'}: raise ValueError('Esito di verifica non valido.')
    if not note.strip() or len(note) > 2000: raise ValueError('Descrivi la verifica effettuata (massimo 2000 caratteri).')
    with db_connection() as conn:
        row = conn.execute('''UPDATE capability_operations
            SET review_outcome=%s,reviewed_at=NOW(),reviewed_by=%s,review_note=%s
            WHERE id=%s AND status='uncertain' AND review_outcome IS NULL RETURNING *''',
            (outcome,username,note.strip(),UUID(identifier))).fetchone()
        if not row: raise ValueError('Operazione non verificabile o già verificata.')
        from core.domain_events import append
        append(conn,type='operation.reviewed',source='owner',aggregate_id=row['id'],revision=3,
               run_id=row['run_id'],root_run_id=str(row['root_run_id']) if row['root_run_id'] else None,
               payload={'operation_id':str(row['id']),'outcome':outcome})
    return row


def get_operation(identifier):
    with db_connection() as conn:
        row = conn.execute('SELECT * FROM capability_operations WHERE id=%s',(UUID(identifier),)).fetchone()
    if not row: raise KeyError(identifier)
    return row

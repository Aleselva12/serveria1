"""Canonical PostgreSQL lifecycle shared by root runs and delegations."""
import json
import threading
from uuid import UUID, uuid4
from core.database import db_connection
from core.run_states import TERMINAL, TRANSITIONS

STATUSES = set(TRANSITIONS)
class RunConflict(RuntimeError): pass
class RunCancelled(RuntimeError): pass
_cancelled = set()
_cancel_lock = threading.Lock()


def cancel_requested(run_id):
    with _cancel_lock: return run_id in _cancelled


def create_run(*, thread_id, kind='chat', target='supervisor', parent_run_id=None, metadata=None, run_id=None):
    with db_connection() as conn:
        row = conn.execute('''INSERT INTO runtime_runs (id,thread_id,kind,target,parent_run_id,status,metadata)
            VALUES (%s,%s,%s,%s,%s,'queued',%s::jsonb) RETURNING *''',
            (UUID(run_id) if run_id else uuid4(),thread_id,kind,target,UUID(parent_run_id) if parent_run_id else None,
             json.dumps(metadata or {},ensure_ascii=False))).fetchone()
        from core.domain_events import run_state
        run_state(conn,row)
        return row


def transition_run(run_id, status, *, error_type=None, metadata=None, expected_status=None, result=None, approval_ids=None):
    if status not in STATUSES: raise ValueError('Stato run non valido.')
    with db_connection() as conn:
        current = conn.execute('SELECT * FROM runtime_runs WHERE id=%s FOR UPDATE',(UUID(run_id),)).fetchone()
        if not current: raise KeyError('Run non trovato.')
        if expected_status is not None and current['status'] != expected_status:
            raise RunConflict('Stato persistente del run diverso da quello atteso.')
        if current['status'] in TERMINAL:
            if status == current['status']: return current
            raise RunConflict('Il run è già terminato.')
        if status != current['status'] and status not in TRANSITIONS[current['status']]:
            raise RunConflict(f"Transizione {current['status']} → {status} non consentita.")
        row = conn.execute('''UPDATE runtime_runs SET status=%s,revision=revision+1,
            started_at=CASE WHEN %s='running' AND started_at IS NULL THEN NOW() ELSE started_at END,
            finished_at=CASE WHEN %s THEN NOW() ELSE finished_at END,
            error_type=COALESCE(%s,error_type),metadata=metadata || %s::jsonb,
            result=COALESCE(%s::jsonb,result),approval_ids=COALESCE(%s::jsonb,approval_ids)
            WHERE id=%s RETURNING *''',
            (status,status,status in TERMINAL,error_type,json.dumps(metadata or {},default=str),
             json.dumps(result,default=str) if result is not None else None,
             json.dumps(approval_ids) if approval_ids is not None else None,current['id'])).fetchone()
        from core.domain_events import run_state
        run_state(conn,row,current['status'])
    if status in TERMINAL:
        with _cancel_lock: _cancelled.discard(str(run_id))
    return row


def mark_stop(run_id, reason):
    with db_connection() as conn:
        changed = conn.execute('''UPDATE runtime_runs SET cancel_requested=TRUE,stop_reason=%s,revision=revision+1
            WHERE id=%s AND NOT cancel_requested AND status=ANY(%s) RETURNING *''',
            (reason,UUID(run_id),[s for s in STATUSES if s not in TERMINAL])).fetchone()
        if changed:
            from core.domain_events import append
            append(conn,type='run.stop_requested',source='runtime',aggregate_id=changed['id'],revision=changed['revision'],run_id=changed['id'],payload={'reason':reason})
        row = conn.execute('SELECT stop_reason,status FROM runtime_runs WHERE id=%s',(UUID(run_id),)).fetchone()
        if not row: raise KeyError(run_id)
    return row['stop_reason'] or reason


def request_cancel(run_id):
    # Walk to the root and mark every active descendant before notifying the live worker.
    with db_connection() as conn:
        row = conn.execute('SELECT * FROM runtime_runs WHERE id=%s',(UUID(run_id),)).fetchone()
        if not row or row['status'] in TERMINAL: raise RunConflict('Run non cancellabile o inesistente.')
        family = conn.execute('''WITH RECURSIVE ancestors AS (
            SELECT id,parent_run_id FROM runtime_runs WHERE id=%s
            UNION ALL SELECT r.id,r.parent_run_id FROM runtime_runs r JOIN ancestors a ON r.id=a.parent_run_id
        ), descendants AS (
            SELECT id FROM ancestors WHERE parent_run_id IS NULL
            UNION ALL SELECT r.id FROM runtime_runs r JOIN descendants d ON r.parent_run_id=d.id
        ) SELECT id FROM descendants''',(row['id'],)).fetchall()
        ids = [r['id'] for r in family]
        marked = conn.execute('''UPDATE runtime_runs SET cancel_requested=TRUE,stop_reason=COALESCE(stop_reason,'cancelled'),revision=revision+1
            WHERE id=ANY(%s) AND status=ANY(%s) RETURNING *''',(ids,[s for s in STATUSES if s not in TERMINAL])).fetchall()
        from core.domain_events import append
        for changed in marked:
            append(conn,type='run.stop_requested',source='runtime',aggregate_id=changed['id'],revision=changed['revision'],run_id=changed['id'],payload={'reason':changed['stop_reason']})
    ids = [r["id"] for r in marked]
    with _cancel_lock: _cancelled.update(str(id) for id in ids)
    from core.runtime import runtime
    for id in ids:
        live = runtime.get(str(id))
        if live: live.stop()
    return get_run(run_id)


def get_run(run_id):
    with db_connection() as conn:
        row = conn.execute('SELECT * FROM runtime_runs WHERE id=%s',(UUID(run_id),)).fetchone()
    if not row: raise KeyError('Run non trovato.')
    return row


def list_runs(limit=100, status=''):
    if status and status not in STATUSES: raise ValueError('Stato run non valido.')
    with db_connection() as conn:
        return conn.execute('SELECT * FROM runtime_runs '+('WHERE status=%s ' if status else '')+'ORDER BY created_at DESC LIMIT %s',
                            (status,max(1,min(int(limit),500))) if status else (max(1,min(int(limit),500)),)).fetchall()


def persisted_snapshot(row):
    from datetime import datetime, timezone
    metadata = row['metadata']
    return {'id':str(row['id']), 'thread_id':row['thread_id'], 'status':row['status'],
            'error_type':row['error_type'], 'result':row['result'], 'agents':{},
            'timings':metadata.get('metrics',{}), 'output':'', 'approval_ids':row['approval_ids'],
            'elapsed_ms':round(((row['finished_at'] or datetime.now(timezone.utc))-row['created_at']).total_seconds()*1000,2),
            'created_at':row['created_at'], 'finished_at':row['finished_at'],
            'kind':row['kind'], 'target':row['target'], 'parent_run_id':str(row['parent_run_id']) if row['parent_run_id'] else None,
            'cancel_requested':row['cancel_requested'], 'stop_reason':row['stop_reason'], 'revision':row['revision']}


def recover():
    # Single backend worker: call only at process startup, before accepting submissions.
    with db_connection() as conn:
        runs = conn.execute('''UPDATE runtime_runs SET status='interrupted',finished_at=NOW(),revision=revision+1,
            error_type=COALESCE(error_type,'ProcessInterrupted') WHERE status=ANY(%s) RETURNING *''',
            ([s for s in STATUSES if s not in TERMINAL],)).fetchall()
        operations = conn.execute('''UPDATE capability_operations SET status=CASE WHEN effect IN ('write','delegate') THEN 'uncertain' ELSE 'failed' END,
            finished_at=NOW(),error_type='ProcessInterrupted' WHERE status='started' RETURNING *''').fetchall()
        from core.domain_events import run_state, operation_state
        for row in runs: run_state(conn,row)
        for row in operations: operation_state(conn,row,2)
        conn.execute("UPDATE action_approvals SET status='uncertain',error_type='ProcessInterrupted' WHERE status='executing'")
        if runs:
            conn.execute("UPDATE working_memory SET state=state || '{\"status\":\"interrupted\"}'::jsonb WHERE state->>'run_id'=ANY(%s)",
                         ([str(r['id']) for r in runs],))
    with _cancel_lock:
        for row in runs: _cancelled.discard(str(row["id"]))
    return len(runs)

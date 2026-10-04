"""Transactional critical facts. Notifications are not commands or effect replay."""
from uuid import UUID
from psycopg.types.json import Jsonb
from core.protocol import ComponentEvent
from core.database import db_connection


def root_for(connection, run_id):
    if not run_id: return None
    row = connection.execute('''WITH RECURSIVE parents AS (
        SELECT id,parent_run_id FROM runtime_runs WHERE id=%s
        UNION ALL SELECT r.id,r.parent_run_id FROM runtime_runs r JOIN parents p ON r.id=p.parent_run_id
    ) SELECT id FROM parents WHERE parent_run_id IS NULL''',(UUID(str(run_id)),)).fetchone()
    return str(row['id']) if row else None


def append(connection, *, type, source, aggregate_id, revision, run_id=None, root_run_id=None, payload=None):
    """Caller owns the transaction. Failure rolls back the canonical state too.

    A tiny clock row serializes assignment until commit, avoiding cursor gaps from
    transactions which allocate sequence numbers and commit out of order.
    """
    existing = connection.execute('SELECT id FROM domain_events WHERE type=%s AND aggregate_id=%s AND aggregate_revision=%s',
                                  (type,UUID(str(aggregate_id)),revision)).fetchone()
    if existing: return str(existing['id'])
    root = root_run_id or root_for(connection,run_id)
    sequence = connection.execute('UPDATE domain_event_clock SET sequence=sequence+1 WHERE id=1 RETURNING sequence').fetchone()['sequence']
    # Concurrent repeats serialize here too. Gaps from duplicate requests are harmless;
    # no committed event with a lower cursor can appear after a later commit.
    existing = connection.execute('SELECT id FROM domain_events WHERE type=%s AND aggregate_id=%s AND aggregate_revision=%s',
                                  (type,UUID(str(aggregate_id)),revision)).fetchone()
    if existing: return str(existing['id'])
    event = ComponentEvent(type=type,source=source,sequence=sequence,run_id=root,correlation_id=root,
                           component_run_id=str(run_id) if run_id else None,payload=payload or {})
    connection.execute('''INSERT INTO domain_events
        (sequence,id,type,source,root_run_id,component_run_id,aggregate_id,aggregate_revision,event)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (sequence,UUID(event.id),type,source,UUID(root) if root else None,UUID(str(run_id)) if run_id else None,
         UUID(str(aggregate_id)),revision,Jsonb(event.model_dump(mode='json'))))
    return event.id


def run_state(connection,row,previous=None):
    return append(connection,type='run.committed',source=row['target'],aggregate_id=row['id'],revision=row['revision'],run_id=row['id'],
                  payload={'status':row['status'],'previous_status':previous,'revision':row['revision'],'error_type':row['error_type']})


def operation_state(connection,row,revision):
    return append(connection,type='operation.committed',source=row['actor'],aggregate_id=row['id'],revision=revision,
                  run_id=row['run_id'],root_run_id=str(row['root_run_id']) if row['root_run_id'] else None,
                  payload={'operation_id':str(row['id']),'capability_id':row['capability_id'],
                           'contract_version':row['contract_version'],'effect':row['effect'],'status':row['status'],
                           'error_type':row.get('error_type'),'revision':revision})


def read(*,after=0,limit=100,run_id=None):
    with db_connection() as connection:
        root = root_for(connection,run_id) if run_id else None
        if run_id and not root: return {'events':[],'next_cursor':after}
        rows = connection.execute('''SELECT sequence,event FROM domain_events WHERE sequence>%s
            AND (%s::uuid IS NULL OR root_run_id=%s::uuid) ORDER BY sequence LIMIT %s''',
            (after,root,root,max(1,min(limit,500)))).fetchall()
    return {'events':[r['event'] for r in rows],'next_cursor':rows[-1]['sequence'] if rows else after}

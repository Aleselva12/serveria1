"""Bounded, metadata-only diagnostics. Failure cannot invalidate business outcomes."""
import json
import math
import os
import threading
from collections import deque
from uuid import UUID
from psycopg.types.json import Jsonb
from core.database import db_connection, database_configured

PAYLOAD_FIELDS = {
    'run.state': {'status'}, 'run.persistence_failed': {'status','persisted'},
    'tool.finished': {'tool_id','capability_id','contract_version','status','duration_ms','operation_id','error_type'},
    'agent.state': {'status'},
    'component.request': {'task_id','target','capability'},
    'component.finished': {'task_id','duration_ms','status','error_type'},
    'context.selected': {'estimated_tokens','input_budget','tool_reserve','dropped_turns','optional_included'},
    'memory.selected': {'references'},
    'trace.span': {'kind','status','name','duration_ms','error_type','graph_version'},
}
SAFE_LOG_FIELDS = {'memory_id','message_id','user_message_id','assistant_message_id','episode_id','run_id','task_id',
                   'version','assertion','action','memory_type','result_count','query_chars','message_chars',
                   'content_chars','message_count','embedding_dimensions','semantic_search','error_type','query_chars'}


def metadata_event(event):
    if event['type'] in {'chat.delta','chat.reset','library.activity'}: return None
    result = dict(event)
    allowed = SAFE_LOG_FIELDS | {'duration_ms','status'} if event['type'].startswith('log.') else PAYLOAD_FIELDS.get(event['type'],set())
    result['payload'] = {k:v for k,v in event['payload'].items() if k in allowed}
    if 'references' in result['payload']:
        references = []
        for reference in result['payload']['references'][:20]:
            if not isinstance(reference,dict): continue
            try: identifier = str(UUID(str(reference.get('id'))))
            except (ValueError,TypeError,AttributeError): continue
            version = reference.get('version')
            if isinstance(version,int) and not isinstance(version,bool) and version>=1:
                references.append({'id':identifier,'version':version})
        result['payload']['references'] = references
    if 'optional_included' in result['payload']:
        result['payload']['optional_included'] = [v for v in result['payload']['optional_included'] if v in {'conversation_summary','persistent_memories'}]
    # Never include exception messages, prompts, results or tool arguments.
    for key,value in list(result['payload'].items()):
        if key not in {'references','optional_included'} and not isinstance(value,(str,int,float,bool,type(None))):
            del result['payload'][key]
            continue
        if isinstance(value,float) and not math.isfinite(value): del result['payload'][key]
    if len(json.dumps(result,default=str).encode()) > 8192: raise ValueError('DiagnosticEventTooLarge')
    return result


class DiagnosticArchive:
    def __init__(self,capacity=2048):
        self.queue = deque()
        self.capacity = capacity
        self.lock = threading.RLock()
        self.flush_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.worker = None
        self.accepted = self.persisted = self.dropped = self.failures = 0
        self.last_error = None

    def record(self,event):
        try:
            selected = metadata_event(event)
            if selected is None: return
            # Freeze nested payloads so later producer mutations cannot change the archive.
            selected = json.loads(json.dumps(selected,default=str))
            with self.lock:
                self.accepted += 1
                if len(self.queue) >= self.capacity:
                    self.dropped += 1
                    return
                self.queue.append(selected)
        except Exception as error:
            with self.lock:
                self.dropped += 1
                self.last_error = type(error).__name__

    def flush(self):
        if not database_configured(): return False
        if not self.flush_lock.acquire(blocking=False): return False
        try:
            with self.lock: batch = list(self.queue)[:64]
            if not batch: return False
            with db_connection() as conn:
                for event in batch:
                    conn.execute('''INSERT INTO diagnostic_events(id,timestamp,root_run_id,component_run_id,type,source,event)
                        VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING''',
                        (UUID(event['id']),event['timestamp'],event['run_id'],event.get('component_run_id'),event['type'],event['source'],Jsonb(event)))
            with self.lock:
                for event in batch:
                    if self.queue and self.queue[0]['id'] == event['id']: self.queue.popleft()
                self.persisted += len(batch)
                self.last_error = None
            return True
        except Exception as error:
            with self.lock:
                self.failures += 1
                self.last_error = type(error).__name__
            return False
        finally: self.flush_lock.release()

    def status(self):
        with self.lock:
            return {'version':1,'privacy':'metadata_only','retention_days':retention_days(),
                    'pending':len(self.queue),'capacity':self.capacity,'accepted':self.accepted,
                    'persisted':self.persisted,'dropped':self.dropped,'write_failures':self.failures,
                    'last_error':self.last_error,'worker_alive':bool(self.worker and self.worker.is_alive()),
                    'guarantee':'best_effort','critical_events':'transactional'}

    def start(self):
        if self.worker and self.worker.is_alive(): return
        self.stop_event.clear()
        def loop():
            import time
            last_cleanup = 0
            while not self.stop_event.is_set():
                worked = self.flush()
                if time.monotonic()-last_cleanup > 3600:
                    try: prune()
                    except Exception as error:
                        with self.lock: self.last_error = type(error).__name__
                    last_cleanup = time.monotonic()
                self.stop_event.wait(.05 if worked else 1)
        self.worker = threading.Thread(target=loop,name='cora-diagnostics',daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker: self.worker.join(timeout=2)
        # No indefinite shutdown waiting; unflushed diagnostics can be lost, never actions.


archive = DiagnosticArchive()


def retention_days():
    try: return max(1,min(3650,int(os.getenv('CORA_DIAGNOSTIC_RETENTION_DAYS','30'))))
    except ValueError: return 30


def prune():
    if not database_configured(): return 0
    with db_connection() as conn:
        result = conn.execute('''DELETE FROM diagnostic_events WHERE id IN
            (SELECT id FROM diagnostic_events WHERE timestamp < NOW()-(%s * INTERVAL '1 day') ORDER BY timestamp LIMIT 1000)''',
            (retention_days(),))
        return result.rowcount


def read(*,run_id=None,limit=200,before=None):
    limit = max(1,min(limit,500))
    with db_connection() as conn:
        cursor = conn.execute('SELECT timestamp,id FROM diagnostic_events WHERE id=%s',(UUID(before),)).fetchone() if before else None
        if before and not cursor: raise ValueError('Cursore diagnostico scaduto: ricarica lo storico.')
        rows = conn.execute('''SELECT event FROM diagnostic_events
            WHERE (%s::text IS NULL OR root_run_id=%s) AND (%s::timestamptz IS NULL OR (timestamp,id)<(%s::timestamptz,%s::uuid))
            ORDER BY timestamp DESC,id DESC LIMIT %s''',(run_id,run_id,cursor['timestamp'] if cursor else None,
            cursor['timestamp'] if cursor else None,cursor['id'] if cursor else None,limit+1)).fetchall()
    more = len(rows)>limit
    chosen = rows[:limit]
    return {'events':[r['event'] for r in reversed(chosen)],'truncated':more,
            'next_before':chosen[-1]['event']['id'] if more else None,'guarantee':'best_effort'}

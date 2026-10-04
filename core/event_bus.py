"""Bounded in-process replay bus; no broker/network round trips or implicit persistence."""
from collections import deque
from threading import Condition
from uuid import uuid4
from core.protocol import ComponentEvent

class EventBus:
    def __init__(self, capacity=512):
        self.events = deque(maxlen=capacity)
        self.sequence = 0
        self.condition = Condition()
        self.process_id = str(uuid4())

    def publish(self, type, source, *, run_id=None, thread_id=None, payload=None, component_run_id=None,
                parent_run_id=None, span_id=None, parent_span_id=None, operation_id=None):
        if component_run_id is None:
            from core.runtime_context import _run_id
            component_run_id = _run_id.get() or run_id
        with self.condition:
            self.sequence += 1
            event = ComponentEvent(type=type, source=source, run_id=run_id, thread_id=thread_id,
                                   correlation_id=run_id, sequence=self.sequence, payload=payload or {},process_id=self.process_id,
                                   component_run_id=component_run_id,parent_run_id=parent_run_id,span_id=span_id,
                                   parent_span_id=parent_span_id,operation_id=operation_id)
            self.events.append(event.model_dump())
            self.condition.notify_all()
            from core.observability import archive
            try: archive.record(event.model_dump(mode='json'))
            except Exception as error:
                with archive.lock:
                    archive.dropped += 1
                    archive.last_error = error.__class__.__name__
            return event

    def read(self, after=0, run_id=None):
        events,gap,_ = self.read_window(after,run_id)
        return events,gap

    def read_window(self, after=0, run_id=None):
        with self.condition:
            gap = bool(after and (after>self.sequence or (self.events and after < self.events[0]["sequence"] - 1)))
            return [e for e in self.events if e["sequence"] > after and (run_id is None or e["run_id"] == run_id)], gap,self.sequence

bus = EventBus()

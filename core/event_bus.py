"""Bounded in-process replay bus; no broker/network round trips or implicit persistence."""
from collections import deque
from threading import Condition
from core.protocol import ComponentEvent

class EventBus:
    def __init__(self, capacity=512):
        self.events = deque(maxlen=capacity)
        self.sequence = 0
        self.condition = Condition()

    def publish(self, type, source, *, run_id=None, thread_id=None, payload=None):
        with self.condition:
            self.sequence += 1
            event = ComponentEvent(type=type, source=source, run_id=run_id, thread_id=thread_id,
                                   correlation_id=run_id, sequence=self.sequence, payload=payload or {})
            self.events.append(event.model_dump())
            self.condition.notify_all()
            return event

    def read(self, after=0, run_id=None):
        with self.condition:
            gap = bool(self.events and after and after < self.events[0]["sequence"] - 1)
            return [e for e in self.events if e["sequence"] > after and (run_id is None or e["run_id"] == run_id)], gap

bus = EventBus()

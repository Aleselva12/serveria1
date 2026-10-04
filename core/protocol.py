"""Versioned component events. Transport is deliberately independent of LangGraph."""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict

class ComponentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: str
    source: str
    run_id: str | None = None
    thread_id: str | None = None
    correlation_id: str | None = None
    sequence: int = 0
    process_id: str | None = None
    component_run_id: str | None = None
    parent_run_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    operation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

class ComponentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    target: str
    capability: str
    run_id: str
    thread_id: str
    deadline: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class TaskEnvelope(ComponentRequest):
    """Compatible command envelope used by the direct component dispatcher."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    context_refs: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComponentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    component: str
    status: Literal["completed", "failed", "waiting_approval", "cancelled", "timed_out"] = "completed"
    content: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

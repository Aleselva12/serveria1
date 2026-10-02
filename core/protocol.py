from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ResultStatus = Literal["completed", "failed", "waiting_approval", "cancelled", "timed_out"]


class TaskEnvelope(BaseModel):
    """Typed in-process message shared by Cora components."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    thread_id: str
    source: str
    target: str
    capability: str
    payload: dict[str, Any] = Field(default_factory=dict)
    context_refs: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComponentResult(BaseModel):
    """Normalized result returned by tools, agents and future workers."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    component: str
    status: ResultStatus = "completed"
    content: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

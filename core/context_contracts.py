"""Standard contracts for progressive, permission-bound context retrieval."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    task_id: str
    requester: str
    objective: str = Field(min_length=1, max_length=4000)
    requested_topics: list[str] = Field(default_factory=list, max_length=32)
    required_precision: Literal["low", "medium", "high", "exact"] = "medium"
    time_scope: dict[str, str | None] = Field(default_factory=dict)
    source_constraints: list[str] = Field(default_factory=list, max_length=32)
    budget_hint: int | None = Field(default=None, ge=256)
    permission_scope: list[str] = Field(default_factory=list, max_length=64)
    expansion_of: str | None = None


class ContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["literal", "summary"]
    content: str
    source_type: str
    source_ref: str
    observed_at: datetime | None = None
    source_timestamp: datetime | None = None
    freshness: float | None = Field(default=None, ge=0, le=1)
    authority: Literal["primary", "derived"] = "derived"
    expandable: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    winner_item_id: str
    loser_item_ids: list[str] = Field(default_factory=list)
    reason: str = "literal_or_newer_source_wins"


class ContextPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    packet_id: str
    task_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    literal_items: list[ContextItem] = Field(default_factory=list)
    summarized_items: list[ContextItem] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    conflicts: list[ContextConflict] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    degraded_sources: list[str] = Field(default_factory=list)
    budget_used: int = Field(default=0, ge=0)
    budget_available: int | None = Field(default=None, ge=0)
    expandable_sections: list[str] = Field(default_factory=list)
    complete_for_objective: bool = False

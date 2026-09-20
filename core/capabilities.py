from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


ComponentKind = Literal["core", "agent", "tool", "interface"]


@dataclass(frozen=True)
class Capability:
    id: str
    description: str


@dataclass(frozen=True)
class ComponentDefinition:
    id: str
    name: str
    kind: ComponentKind
    description: str
    module: str | None = None
    capabilities: tuple[Capability, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return asdict(self)

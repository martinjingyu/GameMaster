from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GiveInfoEffect:
    recipient_id: str
    role_id: str
    message: str
    value: Any
    tags: tuple[str, ...] = ("info",)


@dataclass(frozen=True)
class ApplyConditionEffect:
    target_id: str
    condition: str
    source_role_id: str
    source_player_id: str | None = None
    duration: str = "tonight"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KillEffect:
    target_id: str
    source_role_id: str
    source_player_id: str | None = None
    cause: str = "night_attack"


@dataclass(frozen=True)
class NoOpEffect:
    reason: str

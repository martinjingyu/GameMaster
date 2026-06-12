from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from .types import ActionType


@dataclass(frozen=True)
class PlayerIntent:
    intent_type: str
    actor_id: str
    raw_text: str
    targets: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass(frozen=True)
class GameAction:
    action_id: str
    action_type: ActionType
    actor_id: str | None = None
    targets: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "code"

    @classmethod
    def create(
        cls,
        action_type: ActionType,
        *,
        actor_id: str | None = None,
        targets: tuple[str, ...] = (),
        payload: dict[str, Any] | None = None,
        source: str = "code",
    ) -> "GameAction":
        return cls(
            action_id=secrets.token_hex(8),
            action_type=action_type,
            actor_id=actor_id,
            targets=targets,
            payload=payload or {},
            source=source,
        )


@dataclass(frozen=True)
class ActionResult:
    action_id: str
    ok: bool
    events: tuple[Any, ...] = ()
    outbound_messages: tuple[Any, ...] = ()
    error: str | None = None

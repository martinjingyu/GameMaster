from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .types import EventType, GamePhase, Visibility


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GameEvent:
    event_id: str
    created_at: str
    event_type: EventType
    phase: GamePhase
    day: int
    actor_id: str | None = None
    visibility: Visibility = Visibility.SYSTEM
    recipients: tuple[str, ...] = ()
    public_text: str = ""
    private_text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        event_type: EventType,
        phase: GamePhase,
        day: int,
        *,
        actor_id: str | None = None,
        visibility: Visibility = Visibility.SYSTEM,
        recipients: tuple[str, ...] = (),
        public_text: str = "",
        private_text: str = "",
        payload: dict[str, Any] | None = None,
        tags: tuple[str, ...] = (),
    ) -> "GameEvent":
        return cls(
            event_id=secrets.token_hex(8),
            created_at=utc_now(),
            event_type=event_type,
            phase=phase,
            day=day,
            actor_id=actor_id,
            visibility=visibility,
            recipients=recipients,
            public_text=public_text,
            private_text=private_text,
            payload=payload or {},
            tags=tags,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_type"] = self.event_type.value
        payload["phase"] = self.phase.value
        payload["visibility"] = self.visibility.value
        payload["recipients"] = list(self.recipients)
        payload["tags"] = list(self.tags)
        return payload


@dataclass(frozen=True)
class VisibleEvent:
    event_id: str
    created_at: str
    event_type: str
    phase: str
    day: int
    actor_id: str | None
    text: str
    payload: dict[str, Any]
    tags: tuple[str, ...] = ()

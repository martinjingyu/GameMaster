from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Player:
    user_id: str
    display_name: str
    seat: int
    role_name: str | None = None
    apparent_role_name: str | None = None
    alignment: str = "good"
    alive: bool = True
    ghost_vote: bool = True
    traveler: bool = False
    reminders: list[str] = field(default_factory=list)

    @property
    def shown_role(self) -> str | None:
        return self.apparent_role_name or self.role_name

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Player":
        return cls(**payload)


@dataclass
class Nomination:
    nominator_id: str
    target_id: str
    votes: dict[str, bool] = field(default_factory=dict)
    closed: bool = False

    def yes_count(self) -> int:
        return sum(1 for vote in self.votes.values() if vote)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Nomination":
        return cls(**payload)


@dataclass
class MemoryEvent:
    event_id: str
    created_at: str
    event_type: str
    actor_id: str | None
    actor_name: str | None
    visibility: str
    text: str
    phase: str
    day: int
    recipient_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryEvent":
        return cls(**payload)


@dataclass
class Game:
    game_id: str
    channel_id: str
    owner_id: str
    script_id: str
    phase: str = "lobby"
    day: int = 0
    players: list[Player] = field(default_factory=list)
    bluffs: list[str] = field(default_factory=list)
    fabled: list[str] = field(default_factory=list)
    nominations: list[Nomination] = field(default_factory=list)
    night_actions: list[dict[str, str]] = field(default_factory=list)
    public_log: list[str] = field(default_factory=list)
    memory_events: list[MemoryEvent] = field(default_factory=list)
    memory_summary: str = ""
    pipeline_state: dict[str, Any] = field(default_factory=dict)
    winner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["players"] = [player.to_dict() for player in self.players]
        payload["nominations"] = [nomination.to_dict() for nomination in self.nominations]
        payload["memory_events"] = [event.to_dict() for event in self.memory_events]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Game":
        data = dict(payload)
        data["players"] = [Player.from_dict(player) for player in data.get("players", [])]
        data["nominations"] = [
            Nomination.from_dict(nomination) for nomination in data.get("nominations", [])
        ]
        data["memory_events"] = [
            MemoryEvent.from_dict(event) for event in data.get("memory_events", [])
        ]
        return cls(**data)

    def player_by_id(self, user_id: str) -> Player | None:
        return next((player for player in self.players if player.user_id == user_id), None)

    def living_players(self) -> list[Player]:
        return [player for player in self.players if player.alive]

    def active_nomination(self) -> Nomination | None:
        for nomination in reversed(self.nominations):
            if not nomination.closed:
                return nomination
        return None

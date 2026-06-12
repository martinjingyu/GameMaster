from __future__ import annotations

from dataclasses import dataclass, field

from .types import Alignment


@dataclass
class Player:
    player_id: str
    display_name: str
    is_connected: bool = True
    is_ready: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Seat:
    seat_index: int
    player_id: str


@dataclass
class RoleAssignment:
    player_id: str
    role_id: str
    alignment: Alignment
    shown_role_id: str | None = None
    is_alive: bool = True
    ghost_vote_available: bool = True
    is_drunk: bool = False
    is_poisoned: bool = False
    reminders: list[str] = field(default_factory=list)
    ability_used: bool = False

    @property
    def visible_role_id(self) -> str:
        return self.shown_role_id or self.role_id

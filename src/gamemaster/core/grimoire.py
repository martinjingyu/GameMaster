from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .events import GameEvent, VisibleEvent
from .players import Player, RoleAssignment, Seat
from .types import Alignment, EventType, GamePhase, RoleType, Visibility


@dataclass
class Grimoire:
    game_id: str
    script_id: str
    phase: GamePhase = GamePhase.WAITING_PLAYERS
    day: int = 0
    players: dict[str, Player] = field(default_factory=dict)
    seats: list[Seat] = field(default_factory=list)
    assignments: dict[str, RoleAssignment] = field(default_factory=dict)
    events: list[GameEvent] = field(default_factory=list)
    summary: str = ""
    pipeline_state: dict[str, Any] = field(default_factory=dict)
    night_actions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def append_event(self, event: GameEvent) -> None:
        self.events.append(event)

    def add_player(self, player: Player) -> None:
        self.players[player.player_id] = player
        self.seats.append(Seat(seat_index=len(self.seats) + 1, player_id=player.player_id))
        self.append_event(
            GameEvent.create(
                EventType.PLAYER_JOINED,
                self.phase,
                self.day,
                actor_id=player.player_id,
                visibility=Visibility.PUBLIC,
                public_text=f"{player.display_name} joined the game.",
                payload={"seat": len(self.seats)},
            )
        )

    def assign_role(self, assignment: RoleAssignment) -> None:
        self.assignments[assignment.player_id] = assignment
        self.append_event(
            GameEvent.create(
                EventType.ROLE_ASSIGNED,
                self.phase,
                self.day,
                actor_id="__storyteller__",
                visibility=Visibility.STORYTELLER,
                recipients=("__storyteller__",),
                private_text=f"{assignment.player_id} is {assignment.role_id}.",
                payload={
                    "player_id": assignment.player_id,
                    "role_id": assignment.role_id,
                    "shown_role_id": assignment.shown_role_id,
                    "alignment": assignment.alignment.value,
                },
                tags=("setup",),
            )
        )

    def submit_night_action(
        self, actor_id: str, role_id: str, targets: tuple[str, ...], payload: dict[str, Any] | None = None
    ) -> None:
        self.night_actions[actor_id] = {
            "role_id": role_id,
            "targets": list(targets),
            "payload": payload or {},
        }
        self.append_event(
            GameEvent.create(
                EventType.NIGHT_ACTION_SUBMITTED,
                self.phase,
                self.day,
                actor_id=actor_id,
                visibility=Visibility.STORYTELLER,
                recipients=("__storyteller__",),
                private_text=f"{actor_id} submitted {role_id} action.",
                payload={"role_id": role_id, "targets": list(targets), **(payload or {})},
                tags=("night_action",),
            )
        )

    def change_phase(self, phase: GamePhase) -> None:
        self.phase = phase
        self.append_event(
            GameEvent.create(
                EventType.PHASE_CHANGED,
                self.phase,
                self.day,
                actor_id="__storyteller__",
                visibility=Visibility.PUBLIC,
                public_text=f"Phase changed to {phase.value}.",
            )
        )

    def visible_events_for(self, player_id: str) -> list[VisibleEvent]:
        return [
            self._visible_event(event, player_id)
            for event in self.events
            if self._can_player_see(event, player_id)
        ]

    def storyteller_events(self) -> list[VisibleEvent]:
        return [self._visible_event(event, "__storyteller__") for event in self.events]

    def llm_context_for(self, player_id: str) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "script_id": self.script_id,
            "phase": self.phase.value,
            "day": self.day,
            "player": self._visible_player_state(player_id),
            "summary": self.summary,
            "events": [event.__dict__ for event in self.visible_events_for(player_id)[-30:]],
        }

    def storyteller_context(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "script_id": self.script_id,
            "phase": self.phase.value,
            "day": self.day,
            "players": {
                player_id: {
                    "display_name": player.display_name,
                    "seat": self.seat_of(player_id),
                    "assignment": self.assignments.get(player_id).__dict__
                    if player_id in self.assignments
                    else None,
                }
                for player_id, player in self.players.items()
            },
            "summary": self.summary,
            "events": [event.__dict__ for event in self.storyteller_events()[-50:]],
        }

    def seat_of(self, player_id: str) -> int | None:
        for seat in self.seats:
            if seat.player_id == player_id:
                return seat.seat_index
        return None

    def evil_neighbor_count(self, player_id: str) -> int:
        neighbors = self.alive_neighbors(player_id)
        return sum(
            1
            for neighbor_id in neighbors
            if self.registered_alignment(neighbor_id) == Alignment.EVIL
        )

    def alive_neighbors(self, player_id: str) -> tuple[str, str]:
        alive_seats = [
            seat for seat in self.seats if self.assignments.get(seat.player_id).is_alive
        ]
        index = next(i for i, seat in enumerate(alive_seats) if seat.player_id == player_id)
        left = alive_seats[(index - 1) % len(alive_seats)].player_id
        right = alive_seats[(index + 1) % len(alive_seats)].player_id
        return (left, right)

    def living_player_ids(self) -> tuple[str, ...]:
        return tuple(
            seat.player_id
            for seat in self.seats
            if seat.player_id in self.assignments and self.assignments[seat.player_id].is_alive
        )

    def player_ids_by_role(self, role_id: str) -> tuple[str, ...]:
        return tuple(
            player_id
            for player_id, assignment in self.assignments.items()
            if assignment.role_id == role_id or assignment.visible_role_id == role_id
        )

    def player_ids_by_alignment(self, alignment: Alignment) -> tuple[str, ...]:
        return tuple(
            player_id
            for player_id, assignment in self.assignments.items()
            if self.registered_alignment(player_id) == alignment
        )

    def registered_alignment(self, player_id: str) -> Alignment:
        override = self._registration_override(player_id).get("alignment")
        if override:
            return Alignment(str(override))
        return self.assignments[player_id].alignment

    def registered_role_type(self, player_id: str, script_roles: dict[str, Any]) -> RoleType:
        override = self._registration_override(player_id).get("role_type")
        if override:
            return RoleType(str(override))
        assignment = self.assignments[player_id]
        return script_roles[assignment.role_id].role_type

    def _registration_override(self, player_id: str) -> dict[str, Any]:
        overrides = self.pipeline_state.get("registration_overrides") or {}
        return dict(overrides.get(player_id) or {})

    def action_for(self, player_id: str) -> dict[str, Any] | None:
        return self.night_actions.get(player_id)

    def has_condition(self, player_id: str, condition: str) -> bool:
        assignment = self.assignments[player_id]
        if condition == "poisoned":
            return assignment.is_poisoned
        if condition == "drunk":
            return assignment.is_drunk
        return condition in assignment.reminders

    def _visible_player_state(self, player_id: str) -> dict[str, Any]:
        player = self.players[player_id]
        assignment = self.assignments.get(player_id)
        return {
            "player_id": player_id,
            "display_name": player.display_name,
            "seat": self.seat_of(player_id),
            "role_id": assignment.visible_role_id if assignment else None,
            "is_alive": assignment.is_alive if assignment else True,
            "ghost_vote_available": assignment.ghost_vote_available if assignment else True,
        }

    def _can_player_see(self, event: GameEvent, player_id: str) -> bool:
        if event.visibility == Visibility.PUBLIC:
            return True
        if event.visibility == Visibility.PRIVATE:
            return player_id in event.recipients or event.actor_id == player_id
        if event.visibility == Visibility.EVIL_TEAM:
            assignment = self.assignments.get(player_id)
            return bool(assignment and assignment.alignment == Alignment.EVIL)
        if event.visibility in {Visibility.STORYTELLER, Visibility.SYSTEM}:
            return player_id == "__storyteller__"
        if event.visibility == Visibility.POSTGAME:
            return self.phase == GamePhase.GAME_OVER
        return False

    def _visible_event(self, event: GameEvent, player_id: str) -> VisibleEvent:
        text = event.public_text
        if event.visibility in {Visibility.PRIVATE, Visibility.STORYTELLER, Visibility.SYSTEM}:
            text = event.private_text or event.public_text
        return VisibleEvent(
            event_id=event.event_id,
            created_at=event.created_at,
            event_type=event.event_type.value,
            phase=event.phase.value,
            day=event.day,
            actor_id=event.actor_id,
            text=text,
            payload=event.payload,
            tags=event.tags,
        )

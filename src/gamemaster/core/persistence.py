from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .decision_engine import StorytellerDecisionEngine
from .events import GameEvent
from .flow import GameFlow, GameFlowConfig
from .grimoire import Grimoire
from .llm_provider import LLMDecisionProvider
from .players import Player, RoleAssignment, Seat
from .script import trouble_brewing_minimal
from .types import Alignment, EventType, GamePhase, Visibility


class CoreGameStore:
    def __init__(self, data_path: Path | None = None, min_players: int = 5) -> None:
        self.data_path = data_path
        self.min_players = min_players
        self.games: dict[str, GameFlow] = {}
        self.channel_games: dict[str, str] = {}
        if data_path and data_path.exists():
            self.load()

    def load(self) -> None:
        if not self.data_path:
            return
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.channel_games = {
            str(channel_id): str(game_id)
            for channel_id, game_id in payload.get("channel_games", {}).items()
        }
        self.games = {
            game_id: self._flow_from_dict(game_payload)
            for game_id, game_payload in payload.get("games", {}).items()
        }

    def save(self) -> None:
        if not self.data_path:
            return
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "games": {
                game_id: self._flow_to_dict(flow)
                for game_id, flow in self.games.items()
            },
            "channel_games": self.channel_games,
        }
        self.data_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _flow_to_dict(self, flow: GameFlow) -> dict[str, Any]:
        grimoire = flow.grimoire
        return {
            "game_id": grimoire.game_id,
            "script_id": grimoire.script_id,
            "phase": grimoire.phase.value,
            "day": grimoire.day,
            "summary": grimoire.summary,
            "players": {
                player_id: {
                    "player_id": player.player_id,
                    "display_name": player.display_name,
                    "is_connected": player.is_connected,
                    "is_ready": player.is_ready,
                    "metadata": player.metadata,
                }
                for player_id, player in grimoire.players.items()
            },
            "seats": [
                {"seat_index": seat.seat_index, "player_id": seat.player_id}
                for seat in grimoire.seats
            ],
            "assignments": {
                player_id: {
                    "player_id": assignment.player_id,
                    "role_id": assignment.role_id,
                    "alignment": assignment.alignment.value,
                    "shown_role_id": assignment.shown_role_id,
                    "is_alive": assignment.is_alive,
                    "ghost_vote_available": assignment.ghost_vote_available,
                    "is_drunk": assignment.is_drunk,
                    "is_poisoned": assignment.is_poisoned,
                    "reminders": list(assignment.reminders),
                    "ability_used": assignment.ability_used,
                }
                for player_id, assignment in grimoire.assignments.items()
            },
            "events": [event.to_dict() for event in grimoire.events],
            "pipeline_state": grimoire.pipeline_state,
            "night_actions": grimoire.night_actions,
            "config": {
                "min_players": flow.config.min_players,
                "auto_apply_decisions": flow.config.auto_apply_decisions,
            },
        }

    def _flow_from_dict(self, payload: dict[str, Any]) -> GameFlow:
        config_payload = payload.get("config") or {}
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(
                min_players=int(config_payload.get("min_players") or self.min_players),
                auto_apply_decisions=bool(config_payload.get("auto_apply_decisions", True)),
            ),
            decision_engine=StorytellerDecisionEngine(provider=LLMDecisionProvider()),
            game_id=str(payload["game_id"]),
        )
        flow.grimoire = Grimoire(
            game_id=str(payload["game_id"]),
            script_id=str(payload.get("script_id") or "tb"),
            phase=GamePhase(str(payload.get("phase") or GamePhase.WAITING_PLAYERS.value)),
            day=int(payload.get("day") or 0),
            players={
                player_id: Player(
                    player_id=str(player_payload["player_id"]),
                    display_name=str(player_payload["display_name"]),
                    is_connected=bool(player_payload.get("is_connected", True)),
                    is_ready=bool(player_payload.get("is_ready", False)),
                    metadata=dict(player_payload.get("metadata") or {}),
                )
                for player_id, player_payload in payload.get("players", {}).items()
            },
            seats=[
                Seat(
                    seat_index=int(seat_payload["seat_index"]),
                    player_id=str(seat_payload["player_id"]),
                )
                for seat_payload in payload.get("seats", [])
            ],
            assignments={
                player_id: RoleAssignment(
                    player_id=str(assignment_payload["player_id"]),
                    role_id=str(assignment_payload["role_id"]),
                    alignment=Alignment(str(assignment_payload["alignment"])),
                    shown_role_id=assignment_payload.get("shown_role_id"),
                    is_alive=bool(assignment_payload.get("is_alive", True)),
                    ghost_vote_available=bool(assignment_payload.get("ghost_vote_available", True)),
                    is_drunk=bool(assignment_payload.get("is_drunk", False)),
                    is_poisoned=bool(assignment_payload.get("is_poisoned", False)),
                    reminders=list(assignment_payload.get("reminders") or []),
                    ability_used=bool(assignment_payload.get("ability_used", False)),
                )
                for player_id, assignment_payload in payload.get("assignments", {}).items()
            },
            events=[
                GameEvent(
                    event_id=str(event_payload["event_id"]),
                    created_at=str(event_payload["created_at"]),
                    event_type=EventType(str(event_payload["event_type"])),
                    phase=GamePhase(str(event_payload["phase"])),
                    day=int(event_payload["day"]),
                    actor_id=event_payload.get("actor_id"),
                    visibility=Visibility(str(event_payload.get("visibility") or Visibility.SYSTEM.value)),
                    recipients=tuple(event_payload.get("recipients") or ()),
                    public_text=str(event_payload.get("public_text") or ""),
                    private_text=str(event_payload.get("private_text") or ""),
                    payload=dict(event_payload.get("payload") or {}),
                    tags=tuple(event_payload.get("tags") or ()),
                )
                for event_payload in payload.get("events", [])
            ],
            summary=str(payload.get("summary") or ""),
            pipeline_state=dict(payload.get("pipeline_state") or {}),
            night_actions=dict(payload.get("night_actions") or {}),
        )
        return flow

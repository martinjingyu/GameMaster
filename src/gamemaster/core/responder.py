from __future__ import annotations

import json
from typing import Protocol

from ..llm import LLMError, OpenAICompatibleClient
from .flow import GameFlow
from .types import Visibility


class CompletionClient(Protocol):
    @property
    def configured(self) -> bool: ...

    def complete(self, messages: list[dict[str, str]], response_format: str = "text") -> str: ...


class CorePlayerResponder:
    def __init__(self, client: CompletionClient | None = None) -> None:
        self.client = client or OpenAICompatibleClient()

    def reply(self, flow: GameFlow, player_id: str, text: str, *, private: bool) -> str:
        context = self.context_for(flow, player_id, private=private)
        fallback = self.fallback_reply(flow, player_id, text, private=private)
        if not self.client.configured:
            return fallback

        try:
            response = self.client.complete(self._messages(context, text, private=private)).strip()
        except (LLMError, OSError, RuntimeError, ValueError):
            return fallback
        if not response:
            return fallback
        if self._looks_leaky(flow, player_id, response, context):
            return fallback
        return response

    def context_for(self, flow: GameFlow, player_id: str, *, private: bool) -> dict[str, object]:
        if private:
            return flow.grimoire.llm_context_for(player_id)
        return {
            "game_id": flow.grimoire.game_id,
            "script_id": flow.grimoire.script_id,
            "phase": flow.grimoire.phase.value,
            "day": flow.grimoire.day,
            "players": [
                {
                    "player_id": public_player_id,
                    "display_name": player.display_name,
                    "seat": flow.grimoire.seat_of(public_player_id),
                    "is_alive": flow.grimoire.assignments.get(public_player_id).is_alive
                    if public_player_id in flow.grimoire.assignments
                    else True,
                }
                for public_player_id, player in flow.grimoire.players.items()
            ],
            "summary": flow.grimoire.summary,
            "events": [
                event.__dict__
                for event in flow.grimoire.visible_events_for(player_id)
                if event.event_type in {"player_joined", "phase_changed", "nomination_started", "vote_cast", "execution_result", "death"}
            ][-30:],
        }

    def fallback_reply(self, flow: GameFlow, player_id: str, text: str, *, private: bool) -> str:
        assignment = flow.grimoire.assignments.get(player_id)
        role_line = ""
        if private and assignment:
            role = flow.script.role(assignment.visible_role_id)
            role_line = f"\nYour visible role is {role.name}: {role.ability_text}"
        if private:
            return (
                f"Current phase is {flow.grimoire.phase.value}, day {flow.grimoire.day}. "
                "Ask privately for your own role, or speak publicly to nominate and vote."
                f"{role_line}"
            )
        return (
            f"Current phase is {flow.grimoire.phase.value}, day {flow.grimoire.day}. "
            "Public discussion, nominations, and votes belong in group chat."
        )

    def _messages(
        self,
        context: dict[str, object],
        text: str,
        *,
        private: bool,
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are the AI Storyteller for a Blood on the Clocktower test game. "
                    "Answer briefly and helpfully. Use only the JSON context provided. "
                    "Never reveal hidden roles, alignments, night actions, poisoning, drunkenness, "
                    "or storyteller-only events unless they are explicitly present in this player's context. "
                    "If the player asks for unavailable hidden information, refuse in-world and explain what they can do."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "visibility": "private" if private else "public",
                        "context": context,
                        "player_message": text,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _looks_leaky(
        self,
        flow: GameFlow,
        viewer_id: str,
        response: str,
        context: dict[str, object],
    ) -> bool:
        response_text = response.lower()
        context_text = json.dumps(context, ensure_ascii=False).lower()
        for player_id, assignment in flow.grimoire.assignments.items():
            actual_role = flow.script.role(assignment.role_id)
            hidden_role_tokens = {
                assignment.role_id.lower(),
                actual_role.name.lower(),
            }
            visible_role_id = assignment.visible_role_id
            if player_id == viewer_id and visible_role_id == assignment.role_id:
                continue
            if player_id != viewer_id and self._role_visible_in_context(context_text, flow, player_id, hidden_role_tokens):
                continue
            aliases = self._player_aliases(flow, player_id)
            if player_id == viewer_id and visible_role_id != assignment.role_id:
                if any(token in response_text for token in hidden_role_tokens):
                    return True
                continue
            if any(alias in response_text for alias in aliases) and any(
                token in response_text for token in hidden_role_tokens
            ):
                return True
        return False

    @staticmethod
    def _role_visible_in_context(
        context_text: str,
        flow: GameFlow,
        player_id: str,
        role_tokens: set[str],
    ) -> bool:
        player = flow.grimoire.players[player_id]
        aliases = {player_id.lower(), player.display_name.lower()}
        return any(alias in context_text for alias in aliases) and any(token in context_text for token in role_tokens)

    @staticmethod
    def _player_aliases(flow: GameFlow, player_id: str) -> set[str]:
        player = flow.grimoire.players[player_id]
        aliases = {player_id.lower(), player.display_name.lower()}
        seat = flow.grimoire.seat_of(player_id)
        if seat is not None:
            aliases.update({f"p{seat}", f"player{seat}", f"seat{seat}"})
        return aliases

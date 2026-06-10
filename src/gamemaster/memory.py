from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from .clocktower.models import Game, MemoryEvent


class GameMemory:
    """Structured memory for the storyteller agent.

    The event log is the source of truth for short-term recall. The summary is
    intentionally compact and deterministic so LLM prompts do not grow with the
    full table transcript.
    """

    MAX_EVENTS = 400
    SUMMARY_TRIGGER_EVENTS = 120
    SUMMARY_KEEP_RECENT_EVENTS = 80
    PROMPT_RECENT_EVENTS = 18

    def record(
        self,
        game: Game,
        event_type: str,
        *,
        actor_id: str | None = None,
        actor_name: str | None = None,
        visibility: str = "system",
        text: str = "",
        recipient_id: str | None = None,
        payload: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryEvent:
        event = MemoryEvent(
            event_id=secrets.token_hex(6),
            created_at=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            actor_id=actor_id,
            actor_name=actor_name,
            visibility=visibility,
            text=text,
            recipient_id=recipient_id,
            phase=game.phase,
            day=game.day,
            payload=payload or {},
            tags=tags or [],
        )
        game.memory_events.append(event)
        self.compact(game)
        return event

    def record_outbound_batch(self, game: Game, messages: list[Any]) -> None:
        for message in messages:
            self.record(
                game,
                "outbound_message",
                actor_id="__storyteller__",
                actor_name="GameMaster",
                visibility=message.visibility,
                recipient_id=message.recipient_id,
                text=message.text,
                payload={"metadata": message.metadata},
                tags=["llm" if message.metadata.get("llm") else "agent"],
            )

    def compact(self, game: Game) -> None:
        if len(game.memory_events) <= self.SUMMARY_TRIGGER_EVENTS:
            return

        older = game.memory_events[: -self.SUMMARY_KEEP_RECENT_EVENTS]
        if older:
            game.memory_summary = self._merge_summary(game.memory_summary, older)
        game.memory_events = game.memory_events[-self.MAX_EVENTS :]

    def prompt_context(
        self,
        game: Game,
        *,
        perspective_user_id: str | None = None,
        include_private: bool = False,
        max_events: int | None = None,
    ) -> dict[str, Any]:
        recent = self.recent_events(
            game,
            perspective_user_id=perspective_user_id,
            include_private=include_private,
            limit=max_events or self.PROMPT_RECENT_EVENTS,
        )
        return {
            "memory_summary": game.memory_summary,
            "recent_events": [self._event_for_prompt(event) for event in recent],
        }

    def recent_events(
        self,
        game: Game,
        *,
        perspective_user_id: str | None = None,
        include_private: bool = False,
        limit: int = PROMPT_RECENT_EVENTS,
    ) -> list[MemoryEvent]:
        visible: list[MemoryEvent] = []
        for event in reversed(game.memory_events):
            if self._is_visible_to_prompt(event, perspective_user_id, include_private):
                visible.append(event)
            if len(visible) >= limit:
                break
        return list(reversed(visible))

    def _is_visible_to_prompt(
        self,
        event: MemoryEvent,
        perspective_user_id: str | None,
        include_private: bool,
    ) -> bool:
        if include_private:
            return True
        if event.visibility == "public":
            return True
        if perspective_user_id and event.recipient_id == perspective_user_id:
            return True
        if perspective_user_id and event.actor_id == perspective_user_id and event.visibility == "private":
            return True
        return event.visibility == "system" and "public_state" in event.tags

    def _event_for_prompt(self, event: MemoryEvent) -> dict[str, Any]:
        return {
            "type": event.event_type,
            "actor_id": event.actor_id,
            "actor_name": event.actor_name,
            "visibility": event.visibility,
            "recipient_id": event.recipient_id,
            "phase": event.phase,
            "day": event.day,
            "text": event.text,
            "tags": event.tags,
            "payload": event.payload,
        }

    def _merge_summary(self, existing: str, events: list[MemoryEvent]) -> str:
        lines = [line for line in existing.splitlines() if line.strip()]
        important = [
            event
            for event in events
            if event.event_type
            in {
                "game_created",
                "player_joined",
                "game_started",
                "phase_changed",
                "nomination",
                "vote",
                "execution",
                "death",
                "revival",
                "night_resolution",
            }
            or "important" in event.tags
        ]
        for event in important[-40:]:
            actor = event.actor_name or event.actor_id or "system"
            text = event.text.replace("\n", " ").strip()
            if len(text) > 180:
                text = text[:177] + "..."
            lines.append(f"D{event.day} {event.phase} {event.event_type} {actor}: {text}")
        return "\n".join(lines[-80:])

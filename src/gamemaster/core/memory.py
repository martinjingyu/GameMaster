from __future__ import annotations

from dataclasses import dataclass

from .events import GameEvent
from .grimoire import Grimoire


@dataclass(frozen=True)
class MemoryCompactionResult:
    summarized_event_count: int
    retained_event_count: int
    summary: str


class MemoryCompactor:
    def compact(self, grimoire: Grimoire, keep_last: int = 50) -> MemoryCompactionResult:
        if keep_last < 1:
            raise ValueError("keep_last must be positive")
        old_events = grimoire.events[:-keep_last]
        retained_events = grimoire.events[-keep_last:]
        if not old_events:
            return MemoryCompactionResult(
                summarized_event_count=0,
                retained_event_count=len(retained_events),
                summary=grimoire.summary,
            )

        new_lines = [self._summarize_event(event) for event in old_events]
        new_lines = [line for line in new_lines if line]
        parts = [grimoire.summary.strip(), *new_lines]
        grimoire.summary = "\n".join(part for part in parts if part)
        return MemoryCompactionResult(
            summarized_event_count=len(old_events),
            retained_event_count=len(retained_events),
            summary=grimoire.summary,
        )

    @staticmethod
    def _summarize_event(event: GameEvent) -> str:
        actor = event.actor_id or "system"
        text = event.public_text or event.private_text
        payload = event.payload
        if event.event_type.value == "role_assigned":
            return f"[setup] role assigned for {payload.get('player_id')}: {payload.get('role_id')}"
        if event.event_type.value == "info_given":
            kind = payload.get("kind") or "info"
            return f"[{event.phase.value} day {event.day}] {kind} for {actor}"
        if event.event_type.value in {"death", "execution_result", "nomination_started", "vote_cast"}:
            return f"[{event.phase.value} day {event.day}] {event.event_type.value}: {text}"
        if event.event_type.value in {"decision_applied", "condition_applied", "player_targeted"}:
            return f"[{event.phase.value} day {event.day}] {event.event_type.value}: {payload}"
        if text:
            return f"[{event.phase.value} day {event.day}] {event.event_type.value}: {text}"
        return f"[{event.phase.value} day {event.day}] {event.event_type.value}"

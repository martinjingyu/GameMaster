from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from ..llm import LLMError, OpenAICompatibleClient

from .flow import GameFlow


@dataclass(frozen=True)
class Recap:
    game_id: str
    viewer_id: str
    title: str
    lines: tuple[str, ...]
    mode: str = "structured"

    def to_dict(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "viewer_id": self.viewer_id,
            "title": self.title,
            "lines": list(self.lines),
            "text": "\n".join((self.title, "", *self.lines)),
            "mode": self.mode,
        }


class CompletionClient(Protocol):
    @property
    def configured(self) -> bool: ...

    def complete(self, messages: list[dict[str, str]], response_format: str = "text") -> str: ...


def build_recap(flow: GameFlow, viewer_id: str = "__storyteller__") -> Recap:
    grimoire = flow.grimoire
    if viewer_id == "__storyteller__":
        events = grimoire.storyteller_events()
        title = f"Storyteller recap for {grimoire.game_id}"
    else:
        events = grimoire.visible_events_for(viewer_id)
        title = f"Player recap for {grimoire.players[viewer_id].display_name}"

    lines = [
        f"Script: {grimoire.script_id}",
        f"Final phase: {grimoire.phase.value}",
        f"Day: {grimoire.day}",
    ]
    winner = grimoire.pipeline_state.get("winner")
    if winner:
        lines.append(f"Winner: {winner} ({grimoire.pipeline_state.get('win_reason', '')})")
    if grimoire.summary:
        lines.extend(("", "Summary:", grimoire.summary))

    lines.append("")
    lines.append("Timeline:")
    for event in events:
        text = event.text or str(event.payload)
        lines.append(f"- D{event.day} {event.phase} {event.event_type}: {text}")
    return Recap(
        game_id=grimoire.game_id,
        viewer_id=viewer_id,
        title=title,
        lines=tuple(lines),
    )


def build_llm_recap(
    flow: GameFlow,
    viewer_id: str = "__storyteller__",
    *,
    client: CompletionClient | None = None,
) -> Recap:
    grimoire = flow.grimoire
    client = client or OpenAICompatibleClient()
    fallback = build_recap(flow, "__storyteller__")
    title = f"LLM postgame recap for {grimoire.game_id}"
    if not client.configured:
        return _llm_fallback(title, flow, viewer_id, "LLM is not configured.", fallback)

    try:
        text = client.complete(_llm_recap_messages(_postgame_context(flow), viewer_id)).strip()
    except (LLMError, OSError, RuntimeError, ValueError) as exc:
        return _llm_fallback(title, flow, viewer_id, f"LLM recap failed: {exc}", fallback)
    if not text:
        return _llm_fallback(title, flow, viewer_id, "LLM returned an empty recap.", fallback)
    return Recap(
        game_id=grimoire.game_id,
        viewer_id=viewer_id,
        title=title,
        lines=tuple(line.rstrip() for line in text.splitlines()),
        mode="llm",
    )


def _postgame_context(flow: GameFlow) -> dict[str, object]:
    grimoire = flow.grimoire
    return {
        "game_id": grimoire.game_id,
        "script_id": grimoire.script_id,
        "final_phase": grimoire.phase.value,
        "day": grimoire.day,
        "winner": grimoire.pipeline_state.get("winner"),
        "win_reason": grimoire.pipeline_state.get("win_reason"),
        "players": [
            {
                "player_id": player_id,
                "display_name": player.display_name,
                "seat": grimoire.seat_of(player_id),
                "assignment": grimoire.assignments[player_id].__dict__
                if player_id in grimoire.assignments
                else None,
            }
            for player_id, player in grimoire.players.items()
        ],
        "summary": grimoire.summary,
        "events": [
            {
                "event_type": event.event_type,
                "phase": event.phase,
                "day": event.day,
                "actor_id": event.actor_id,
                "text": event.text,
                "payload": event.payload,
                "tags": list(event.tags),
            }
            for event in grimoire.storyteller_events()
        ],
        "conversation": [
            {
                "phase": event.phase,
                "day": event.day,
                "actor_id": event.actor_id,
                "text": event.text,
                "scope": event.payload.get("scope"),
                "tags": list(event.tags),
            }
            for event in grimoire.storyteller_events()
            if "chat" in event.tags
        ],
    }


def _llm_recap_messages(context: dict[str, object], viewer_id: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a postgame analyst for a Blood on the Clocktower game. "
                "The game is over, so you may use the full hidden record. "
                "Write in Chinese. Be vivid, specific, and fair. Analyze all player conversations, "
                "night actions, misinformation, executions, and win conditions. Include: "
                "1) final result, 2) key turning points, 3) best player/MVP with reasons, "
                "4) each player's notable choices and table talk, 5) a playful roast section. "
                "Roast decisions and table reads, not real people; keep it funny rather than cruel."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "viewer_id": viewer_id,
                    "postgame_context": context,
                },
                ensure_ascii=False,
            ),
        },
    ]


def _llm_fallback(title: str, flow: GameFlow, viewer_id: str, reason: str, fallback: Recap) -> Recap:
    return Recap(
        game_id=flow.grimoire.game_id,
        viewer_id=viewer_id,
        title=title,
        lines=(f"{reason} Falling back to structured full recap.", "", *fallback.lines),
        mode="llm_fallback",
    )

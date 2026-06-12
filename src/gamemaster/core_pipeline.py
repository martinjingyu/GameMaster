from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .config import GameMasterConfig
from .core.action_validator import NIGHT_TARGET_COUNTS
from .core.decision_engine import StorytellerDecisionEngine
from .core.flow import GameFlow, GameFlowConfig
from .core.llm_provider import LLMDecisionProvider
from .core.script import trouble_brewing_minimal
from .core.types import GamePhase, Visibility


@dataclass(frozen=True)
class CoreOutboundMessage:
    channel_id: str
    game_id: str
    visibility: str
    text: str
    recipient_id: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "game_id": self.game_id,
            "visibility": self.visibility,
            "text": self.text,
            "recipient_id": self.recipient_id,
            "metadata": self.metadata or {},
        }


class CorePipeline:
    def __init__(
        self,
        config: GameMasterConfig,
        games: dict[str, GameFlow] | None = None,
        channel_games: dict[str, str] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.games = games if games is not None else {}
        self.channel_games = channel_games if channel_games is not None else {}
        self.on_change = on_change

    def tick(self, channel_id: str | None = None) -> list[CoreOutboundMessage]:
        channel_id = channel_id or self.config.default_channel_id
        flow = self.current_for_channel(channel_id)
        if not flow:
            if not self.config.auto_create_game:
                return []
            flow = self.create_game(channel_id)
            self._changed()
            return [self._public(flow, channel_id, "Core pipeline created a new game.")]

        if flow.grimoire.phase == GamePhase.GAME_OVER or flow.grimoire.pipeline_state.get("paused"):
            return []
        if flow.grimoire.phase == GamePhase.WAITING_PLAYERS:
            messages = self._tick_waiting(flow, channel_id)
            if messages:
                self._changed()
            return messages
        if flow.grimoire.phase in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}:
            messages = self._tick_night(flow, channel_id)
            if messages:
                self._changed()
            return messages
        if flow.grimoire.phase == GamePhase.DAY:
            messages = self._tick_day(flow, channel_id)
            if messages:
                self._changed()
            return messages
        return []

    def apply_action(
        self,
        channel_id: str,
        action: str,
        params: dict[str, Any] | None = None,
        actor_id: str = "__storyteller__",
    ) -> CoreOutboundMessage:
        flow = self.current_for_channel(channel_id)
        if not flow:
            raise ValueError("no active core game for channel")
        params = params or {}
        action = action.strip().lower().replace("-", "_")

        if action in {"extend", "extend_timer"}:
            seconds = int(params.get("seconds", 0))
            key = str(params.get("timer") or self._active_deadline_key(flow))
            self.adjust_deadline(flow, key, seconds)
            text = f"Core pipeline extended {key} by {seconds} seconds."
        elif action in {"shorten", "shorten_timer"}:
            seconds = int(params.get("seconds", 0))
            key = str(params.get("timer") or self._active_deadline_key(flow))
            self.adjust_deadline(flow, key, -seconds)
            text = f"Core pipeline shortened {key} by {seconds} seconds."
        elif action == "set_timer":
            seconds = int(params.get("seconds", 0))
            key = str(params.get("timer") or self._active_deadline_key(flow))
            self._set_deadline(flow, key, seconds)
            text = f"Core pipeline set {key} to {seconds} seconds."
        elif action == "pause":
            flow.grimoire.pipeline_state["paused"] = True
            text = "Core pipeline paused."
        elif action == "resume":
            flow.grimoire.pipeline_state["paused"] = False
            text = "Core pipeline resumed."
        elif action == "set_override":
            name = str(params["name"])
            value = params["value"]
            flow.grimoire.pipeline_state.setdefault("overrides", {})[name] = value
            text = f"Core pipeline set override {name}={value}."
        elif action == "clear_override":
            name = str(params["name"])
            flow.grimoire.pipeline_state.setdefault("overrides", {}).pop(name, None)
            text = f"Core pipeline cleared override {name}."
        elif action == "force_phase":
            phase = GamePhase(str(params["phase"]))
            flow.grimoire.change_phase(phase)
            text = f"Core pipeline forced phase to {phase.value}."
        else:
            raise ValueError(f"Unknown core pipeline action: {action}")

        flow.grimoire.pipeline_state["last_action"] = {
            "action": action,
            "params": params,
            "actor_id": actor_id,
            "at": self._now().isoformat(),
        }
        self._changed()
        return self._public(flow, channel_id, text)

    def create_game(self, channel_id: str, game_id: str | None = None) -> GameFlow:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=self.config.min_players_to_start),
            decision_engine=StorytellerDecisionEngine(provider=LLMDecisionProvider()),
            game_id=game_id or f"core-{channel_id}",
        )
        flow.grimoire.pipeline_state["channel_id"] = channel_id
        flow.grimoire.pipeline_state["stage"] = "waiting_players"
        self.games[flow.grimoire.game_id] = flow
        self.channel_games[channel_id] = flow.grimoire.game_id
        return flow

    def current_for_channel(self, channel_id: str) -> GameFlow | None:
        game_id = self.channel_games.get(channel_id)
        if not game_id:
            return None
        return self.games.get(game_id)

    def _tick_waiting(self, flow: GameFlow, channel_id: str) -> list[CoreOutboundMessage]:
        player_count = len(flow.grimoire.players)
        min_players = int(self._setting(flow, "min_players_to_start"))
        if player_count < min_players:
            return []
        if not self._setting(flow, "auto_start_game"):
            return []

        deadline = self._deadline(flow, "lobby_start_deadline")
        if not deadline:
            seconds = int(self._setting(flow, "lobby_countdown_seconds"))
            self._set_deadline(flow, "lobby_start_deadline", seconds)
            flow.grimoire.pipeline_state["stage"] = "lobby_countdown"
            if seconds > 0:
                return [self._public(flow, channel_id, f"Core game starts in {seconds} seconds.")]

        if deadline and self._remaining_seconds(deadline) > 0:
            return []

        before = len(flow.grimoire.events)
        flow.start_setup()
        flow.allocate_roles()
        flow.enter_first_night()
        self._clear_deadline(flow, "lobby_start_deadline")
        flow.grimoire.pipeline_state["stage"] = "night_actions"
        setup_messages = self._messages_from_events(flow, channel_id, flow.grimoire.events[before:])
        return [
            self._public(flow, channel_id, "Core game started. First night begins."),
            *setup_messages,
        ]

    def _tick_night(self, flow: GameFlow, channel_id: str) -> list[CoreOutboundMessage]:
        deadline_key = "night_deadline"
        deadline = self._deadline(flow, deadline_key)
        if not deadline:
            seconds = int(self._setting(flow, "night_action_seconds"))
            self._set_deadline(flow, deadline_key, seconds)
            flow.grimoire.pipeline_state["stage"] = "night_actions"
            if seconds > 0:
                return [self._public(flow, channel_id, f"Night actions close in {seconds} seconds.")]

        if deadline and self._remaining_seconds(deadline) > 0:
            return self._night_reminders(flow, channel_id, deadline)

        messages: list[CoreOutboundMessage] = []
        if self._setting(flow, "auto_resolve_night"):
            for result in flow.resolve_current_night():
                for outbound in result.outbound_messages:
                    messages.append(self._from_outbound(flow, channel_id, outbound))
        flow.enter_day()
        self._clear_deadline(flow, deadline_key)
        flow.grimoire.pipeline_state["stage"] = "day_discussion"
        messages.append(self._public(flow, channel_id, f"Day {flow.grimoire.day} begins."))
        return messages

    def _tick_day(self, flow: GameFlow, channel_id: str) -> list[CoreOutboundMessage]:
        deadline_key = "day_deadline"
        deadline = self._deadline(flow, deadline_key)
        if not deadline:
            seconds = int(self._setting(flow, "day_discussion_seconds"))
            self._set_deadline(flow, deadline_key, seconds)
            flow.grimoire.pipeline_state["stage"] = "day_discussion"
            if seconds > 0:
                return [self._public(flow, channel_id, f"Day discussion timer: {seconds} seconds.")]

        if deadline and self._remaining_seconds(deadline) > 0:
            return []

        if not self._setting(flow, "auto_advance_day"):
            return []

        result = flow.end_day()
        self._clear_deadline(flow, deadline_key)
        if flow.grimoire.phase != GamePhase.GAME_OVER:
            flow.grimoire.pipeline_state["stage"] = "night_actions"
        return [
            *[self._from_outbound(flow, channel_id, outbound) for outbound in result.outbound_messages],
            self._public(flow, channel_id, f"Day {flow.grimoire.day} closed."),
        ]

    def adjust_deadline(self, flow: GameFlow, key: str, seconds_delta: int) -> datetime:
        deadline = self._deadline(flow, key) or self._now()
        deadline = deadline + timedelta(seconds=seconds_delta)
        if deadline < self._now():
            deadline = self._now()
        flow.grimoire.pipeline_state[key] = deadline.isoformat()
        return deadline

    def _deadline(self, flow: GameFlow, key: str) -> datetime | None:
        value = flow.grimoire.pipeline_state.get(key)
        if not value:
            return None
        return datetime.fromisoformat(str(value))

    def _set_deadline(self, flow: GameFlow, key: str, seconds: int) -> datetime:
        deadline = self._now() + timedelta(seconds=max(0, seconds))
        flow.grimoire.pipeline_state[key] = deadline.isoformat()
        return deadline

    def _clear_deadline(self, flow: GameFlow, key: str) -> None:
        flow.grimoire.pipeline_state.pop(key, None)

    def _active_deadline_key(self, flow: GameFlow) -> str:
        for key in ("lobby_start_deadline", "night_deadline", "day_deadline"):
            if flow.grimoire.pipeline_state.get(key):
                return key
        if flow.grimoire.phase == GamePhase.WAITING_PLAYERS:
            return "lobby_start_deadline"
        if flow.grimoire.phase in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}:
            return "night_deadline"
        return "day_deadline"

    def _setting(self, flow: GameFlow, name: str) -> object:
        overrides = flow.grimoire.pipeline_state.get("overrides") or {}
        if name in overrides:
            return overrides[name]
        return getattr(self.config, name)

    def _public(self, flow: GameFlow, channel_id: str, text: str) -> CoreOutboundMessage:
        return CoreOutboundMessage(
            channel_id=channel_id,
            game_id=flow.grimoire.game_id,
            visibility=Visibility.PUBLIC.value,
            text=text,
            metadata={"pipeline": True, "core": True},
        )

    def _from_outbound(self, flow: GameFlow, channel_id: str, outbound: object) -> CoreOutboundMessage:
        return CoreOutboundMessage(
            channel_id=channel_id,
            game_id=flow.grimoire.game_id,
            visibility=outbound.visibility.value,
            text=outbound.text,
            recipient_id=outbound.recipient_id,
            metadata={"core": True},
        )

    def _messages_from_events(
        self,
        flow: GameFlow,
        channel_id: str,
        events: list[object],
    ) -> list[CoreOutboundMessage]:
        messages: list[CoreOutboundMessage] = []
        for event in events:
            visibility = event.visibility
            if visibility == Visibility.PRIVATE:
                for recipient_id in event.recipients:
                    messages.append(
                        CoreOutboundMessage(
                            channel_id=channel_id,
                            game_id=flow.grimoire.game_id,
                            visibility=Visibility.PRIVATE.value,
                            recipient_id=recipient_id,
                            text=event.private_text or event.public_text,
                            metadata={"core": True, "setup": True},
                        )
                    )
            elif visibility == Visibility.EVIL_TEAM:
                for player_id, assignment in flow.grimoire.assignments.items():
                    if assignment.alignment.value != "evil":
                        continue
                    messages.append(
                        CoreOutboundMessage(
                            channel_id=channel_id,
                            game_id=flow.grimoire.game_id,
                            visibility=Visibility.PRIVATE.value,
                            recipient_id=player_id,
                            text=event.private_text or event.public_text,
                            metadata={"core": True, "setup": True},
                        )
                    )
        return messages

    def _night_reminders(
        self,
        flow: GameFlow,
        channel_id: str,
        deadline: datetime,
    ) -> list[CoreOutboundMessage]:
        key = f"night_reminder_sent:{flow.grimoire.day}:{flow.grimoire.phase.value}"
        if flow.grimoire.pipeline_state.get(key):
            return []
        seconds_total = int(self._setting(flow, "night_action_seconds"))
        if seconds_total <= 0:
            return []
        remaining = self._remaining_seconds(deadline)
        if remaining > max(1, seconds_total // 2):
            return []

        reminders: list[CoreOutboundMessage] = []
        for player_id, assignment in flow.grimoire.assignments.items():
            visible_role_id = assignment.visible_role_id
            if visible_role_id not in NIGHT_TARGET_COUNTS:
                continue
            if player_id in flow.grimoire.night_actions:
                continue
            role = flow.script.role(visible_role_id)
            order = (
                role.first_night_order
                if flow.grimoire.phase == GamePhase.FIRST_NIGHT
                else role.other_night_order
            )
            if order is None:
                continue
            if not assignment.is_alive and visible_role_id != "ravenkeeper":
                continue
            reminders.append(
                CoreOutboundMessage(
                    channel_id=channel_id,
                    game_id=flow.grimoire.game_id,
                    visibility=Visibility.PRIVATE.value,
                    recipient_id=player_id,
                    text="Night reminder: please send your choice privately.",
                    metadata={"core": True, "pipeline": True, "reminder": "night_action"},
                )
            )
        if reminders:
            flow.grimoire.pipeline_state[key] = self._now().isoformat()
        return reminders

    def _changed(self) -> None:
        if self.on_change:
            self.on_change()

    @staticmethod
    def _remaining_seconds(deadline: datetime) -> int:
        return max(0, int((deadline - CorePipeline._now()).total_seconds()))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

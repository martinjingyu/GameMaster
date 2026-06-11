from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .agent import GatewayEvent, OutboundMessage
from .clocktower.models import Game
from .config import GameMasterConfig


STORYTELLER_EVENT = GatewayEvent(
    channel_id="",
    user_id="__storyteller__",
    display_name="GameMaster",
    text="",
    metadata={"storyteller": True, "source": "pipeline"},
)


class AgentPipeline:
    """Hard-coded storyteller pipeline for local and future channel test modes."""

    def __init__(self, agent: object, config: GameMasterConfig):
        self.agent = agent
        self.config = config

    def tick(self, channel_id: str | None = None) -> list[OutboundMessage]:
        channel_id = channel_id or self.config.default_channel_id
        game = self.agent.store.current_for_channel(channel_id)
        if not game:
            if not self.config.auto_create_game:
                return []
            return self._create_game(channel_id)

        if game.winner:
            return []
        if game.pipeline_state.get("paused"):
            return []
        if game.phase == "lobby":
            return self._tick_lobby(game)
        if game.phase == "night":
            return self._tick_night(game)
        if game.phase == "day":
            return self._tick_day(game)
        return []

    def apply_action(
        self,
        game: Game,
        action: str,
        params: dict[str, Any] | None = None,
        actor_id: str = "__storyteller__",
    ) -> OutboundMessage:
        params = params or {}
        action = action.strip().lower().replace("-", "_")

        if action in {"extend", "extend_timer"}:
            seconds = int(params.get("seconds", 0))
            key = str(params.get("timer") or self._active_deadline_key(game))
            self.adjust_deadline(game, key, seconds)
            text = f"GameMaster extended {key} by {seconds} seconds."
        elif action in {"shorten", "shorten_timer"}:
            seconds = int(params.get("seconds", 0))
            key = str(params.get("timer") or self._active_deadline_key(game))
            self.adjust_deadline(game, key, -seconds)
            text = f"GameMaster shortened {key} by {seconds} seconds."
        elif action == "set_timer":
            seconds = int(params.get("seconds", 0))
            key = str(params.get("timer") or self._active_deadline_key(game))
            self._set_deadline(game, key, seconds)
            text = f"GameMaster set {key} to {seconds} seconds."
        elif action == "pause":
            game.pipeline_state["paused"] = True
            text = "GameMaster paused the pipeline."
        elif action == "resume":
            game.pipeline_state["paused"] = False
            text = "GameMaster resumed the pipeline."
        elif action == "set_override":
            name = str(params["name"])
            value = params["value"]
            game.pipeline_state.setdefault("overrides", {})[name] = value
            text = f"GameMaster set override {name}={value}."
        elif action == "clear_override":
            name = str(params["name"])
            game.pipeline_state.setdefault("overrides", {}).pop(name, None)
            text = f"GameMaster cleared override {name}."
        elif action == "force_stage":
            stage = str(params["stage"])
            self._set_stage(game, stage)
            text = f"GameMaster forced pipeline stage to {stage}."
        else:
            raise ValueError(f"Unknown pipeline action: {action}")

        game.pipeline_state["last_action"] = {
            "action": action,
            "params": params,
            "actor_id": actor_id,
            "at": self._now().isoformat(),
        }
        self._record_pipeline(game, "pipeline_action", text)
        return self._public(game, text)

    def _create_game(self, channel_id: str) -> list[OutboundMessage]:
        event = self._event(channel_id, f"/new {self.config.default_script}")
        messages = self.agent.handle_event(event)
        game = self.agent.store.current_for_channel(channel_id)
        if game:
            self._record_pipeline(game, "pipeline_game_created", "Pipeline created a new game.")
            self._set_stage(game, "lobby_waiting")
        return messages

    def _tick_lobby(self, game: Game) -> list[OutboundMessage]:
        player_count = len(game.players)
        min_players = int(self._setting(game, "min_players_to_start"))
        if player_count < min_players:
            if self._should_announce(game, "lobby_waiting", 15):
                return [
                    self._public(
                        game,
                        (
                            f"GameMaster is waiting for players: {player_count}/"
                            f"{min_players}. Send /join <name> to sit down."
                        ),
                    )
                ]
            return []

        if not self._setting(game, "auto_start_game"):
            return []

        deadline = self._deadline(game, "lobby_start_deadline")
        if not deadline:
            deadline = self._set_deadline(
                game, "lobby_start_deadline", int(self._setting(game, "lobby_countdown_seconds"))
            )
            self._set_stage(game, "lobby_countdown")
            return [
                self._public(
                    game,
                    (
                        f"Enough players are seated. Game starts in "
                        f"{int(self._setting(game, 'lobby_countdown_seconds'))} seconds."
                    ),
                )
            ]

        remaining = self._remaining_seconds(deadline)
        if remaining > 0:
            if remaining in {60, 30, 10, 5} or self._should_announce(game, "lobby_countdown", 20):
                return [self._public(game, f"Game starts in {remaining} seconds.")]
            return []

        event = self._event(game.channel_id, "/start")
        messages = self.agent.handle_event(event)
        self._clear_deadline(game, "lobby_start_deadline")
        self._set_stage(game, "night")
        self._record_pipeline(game, "pipeline_game_started", "Pipeline started the game.")
        return messages

    def _tick_night(self, game: Game) -> list[OutboundMessage]:
        deadline = self._deadline(game, "night_deadline")
        if not deadline:
            seconds = int(self._setting(game, "night_action_seconds"))
            deadline = self._set_deadline(game, "night_deadline", seconds)
            self._set_stage(game, "night_actions")
            return [
                self._public(
                    game,
                    (
                        f"Night falls. You have {seconds} seconds "
                        "to send private actions to GameMaster."
                    ),
                )
            ]

        remaining = self._remaining_seconds(deadline)
        if remaining > 0:
            if remaining in {60, 30, 10, 5} or self._should_announce(game, "night_actions", 30):
                return [self._public(game, f"Night action window closes in {remaining} seconds.")]
            return []

        messages: list[OutboundMessage] = []
        if self._setting(game, "auto_resolve_night"):
            messages.extend(self.agent.handle_event(self._event(game.channel_id, "/resolve")))
        messages.extend(self.agent.handle_event(self._event(game.channel_id, "/day")))
        self._clear_deadline(game, "night_deadline")
        self._set_stage(game, "day_discussion")
        self._record_pipeline(game, "pipeline_night_resolved", "Pipeline resolved night and opened day.")
        return messages

    def _tick_day(self, game: Game) -> list[OutboundMessage]:
        deadline = self._deadline(game, "day_deadline")
        if not deadline:
            seconds = int(self._setting(game, "day_discussion_seconds"))
            deadline = self._set_deadline(game, "day_deadline", seconds)
            self._set_stage(game, "day_discussion")
            return [
                self._public(
                    game,
                    (
                        f"Day {game.day} is open. Discussion timer: "
                        f"{seconds} seconds."
                    ),
                )
            ]

        remaining = self._remaining_seconds(deadline)
        if remaining > 0:
            if remaining in {120, 60, 30, 10, 5} or self._should_announce(game, "day_discussion", 60):
                return [self._public(game, f"Day discussion has {remaining} seconds remaining.")]
            return []

        if not self._setting(game, "auto_advance_day"):
            if self._should_announce(game, "day_overtime", 60):
                return [
                    self._public(
                        game,
                        "Day timer has ended. GameMaster is waiting before moving to night.",
                    )
                ]
            return []

        messages = self.agent.handle_event(self._event(game.channel_id, "/night"))
        self._clear_deadline(game, "day_deadline")
        self._set_stage(game, "night_actions")
        self._record_pipeline(game, "pipeline_day_closed", "Pipeline closed day and opened night.")
        return messages

    def _event(self, channel_id: str, text: str) -> GatewayEvent:
        return GatewayEvent(
            channel_id=channel_id,
            user_id=STORYTELLER_EVENT.user_id,
            display_name=STORYTELLER_EVENT.display_name,
            text=text,
            metadata=dict(STORYTELLER_EVENT.metadata),
        )

    def _public(self, game: Game, text: str) -> OutboundMessage:
        message = OutboundMessage(
            channel_id=game.channel_id,
            game_id=game.game_id,
            visibility="public",
            text=text,
            metadata={"pipeline": True},
        )
        self.agent.memory.record_outbound_batch(game, [message])
        self.agent.store.save()
        return message

    def _record_pipeline(self, game: Game, event_type: str, text: str) -> None:
        self.agent.memory.record(
            game,
            event_type,
            actor_id="__storyteller__",
            actor_name="GameMaster",
            visibility="system",
            text=text,
            payload={"pipeline_state": dict(game.pipeline_state)},
            tags=["pipeline", "important"],
        )
        self.agent.store.save()

    def _set_stage(self, game: Game, stage: str) -> None:
        game.pipeline_state["stage"] = stage
        game.pipeline_state["updated_at"] = self._now().isoformat()
        self.agent.store.save()

    def _deadline(self, game: Game, key: str) -> datetime | None:
        value = game.pipeline_state.get(key)
        if not value:
            return None
        return datetime.fromisoformat(value)

    def _set_deadline(self, game: Game, key: str, seconds: int) -> datetime:
        deadline = self._now() + timedelta(seconds=max(0, seconds))
        game.pipeline_state[key] = deadline.isoformat()
        self.agent.store.save()
        return deadline

    def adjust_deadline(self, game: Game, key: str, seconds_delta: int) -> datetime:
        deadline = self._deadline(game, key) or self._now()
        deadline = deadline + timedelta(seconds=seconds_delta)
        if deadline < self._now():
            deadline = self._now()
        game.pipeline_state[key] = deadline.isoformat()
        self.agent.store.save()
        return deadline

    def _clear_deadline(self, game: Game, key: str) -> None:
        game.pipeline_state.pop(key, None)
        self.agent.store.save()

    def _should_announce(self, game: Game, topic: str, interval_seconds: int) -> bool:
        key = f"last_announce_{topic}"
        last = game.pipeline_state.get(key)
        now = self._now()
        if last:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds()
            if elapsed < interval_seconds:
                return False
        game.pipeline_state[key] = now.isoformat()
        self.agent.store.save()
        return True

    def _active_deadline_key(self, game: Game) -> str:
        for key in ("lobby_start_deadline", "night_deadline", "day_deadline"):
            if game.pipeline_state.get(key):
                return key
        if game.phase == "lobby":
            return "lobby_start_deadline"
        if game.phase == "night":
            return "night_deadline"
        if game.phase == "day":
            return "day_deadline"
        return "lobby_start_deadline"

    def _setting(self, game: Game, name: str) -> object:
        overrides = game.pipeline_state.get("overrides") or {}
        if name in overrides:
            return overrides[name]
        return getattr(self.config, name)

    @staticmethod
    def _remaining_seconds(deadline: datetime) -> int:
        return max(0, int((deadline - AgentPipeline._now()).total_seconds()))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

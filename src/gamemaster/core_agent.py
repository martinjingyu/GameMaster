from __future__ import annotations

import re
import shlex

from .agent import GatewayEvent, OutboundMessage
from .core.events import GameEvent
from .core.responder import CorePlayerResponder
from .core.types import EventType, GamePhase, Visibility
from .core_pipeline import CorePipeline


class CoreAgent:
    def __init__(self, pipeline: CorePipeline, responder: CorePlayerResponder | None = None) -> None:
        self.pipeline = pipeline
        self.responder = responder or CorePlayerResponder()

    def handle_event(self, event: GatewayEvent) -> list[OutboundMessage]:
        text = event.text.strip()
        if not text:
            return []
        self._record_player_message(event, text)
        if not text.startswith("/"):
            return self._handle_free_text(event)
        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return [self._private(event, f"Command parse failed: {exc}")]
        command = tokens[0].lower()
        args = tokens[1:]
        try:
            if command in {"/new", "/create"}:
                return self._cmd_new(event, args)
            if command == "/join":
                return self._cmd_join(event, args)
            if command == "/start":
                return self._cmd_start(event, args)
            if command == "/role":
                return self._cmd_role(event)
            if command == "/status":
                return self._cmd_status(event)
            if command == "/action":
                return self._cmd_action(event, args)
            if command == "/resolve":
                return self._cmd_resolve(event)
            if command == "/day":
                flow = self._current_flow(event)
                flow.enter_day()
                return [self._public(event, f"Day {flow.grimoire.day} begins.")]
            if command == "/night":
                flow = self._current_flow(event)
                flow.grimoire.change_phase(GamePhase.NIGHT)
                return [self._public(event, "Night begins.")]
            if command == "/nominate":
                return self._cmd_nominate(event, args)
            if command == "/vote":
                return self._cmd_vote(event, args)
            if command == "/closevote":
                flow = self._current_flow(event)
                result = flow.close_vote()
                return self._messages_from_result(event, result)
            if command == "/slayer":
                return self._cmd_slayer(event, args)
            return [self._private(event, f"Unknown core command: {command}")]
        except Exception as exc:
            return [self._private(event, f"Core storyteller hint: {exc}")]

    def _handle_free_text(self, event: GatewayEvent) -> list[OutboundMessage]:
        flow = self.pipeline.current_for_channel(event.channel_id)
        if event.is_private:
            if flow and flow.grimoire.phase in {GamePhase.FIRST_NIGHT, GamePhase.NIGHT}:
                return self._cmd_action(event, [event.text])
            if flow:
                return [self._private(event, self._rules_answer(flow, event))]
        if not flow:
            return []
        if flow.grimoire.phase in {GamePhase.DAY, GamePhase.VOTING}:
            parsed = self._parse_day_intent(event.text)
            if parsed["intent"] == "nominate" and parsed["target"]:
                return self._cmd_nominate(event, [str(parsed["target"])])
            if parsed["intent"] == "vote":
                return self._cmd_vote(event, ["yes" if parsed["yes"] else "no"])
        return []

    def _record_player_message(self, event: GatewayEvent, text: str) -> None:
        flow = self.pipeline.current_for_channel(event.channel_id)
        if not flow:
            return
        player = flow.grimoire.players.get(event.user_id)
        display_name = player.display_name if player else event.display_name or event.user_id
        scope = "private" if event.is_private else "public"
        flow.grimoire.append_event(
            GameEvent.create(
                EventType.PRIVATE_MESSAGE if event.is_private else EventType.PUBLIC_MESSAGE,
                flow.grimoire.phase,
                flow.grimoire.day,
                actor_id=event.user_id,
                visibility=Visibility.POSTGAME,
                public_text=f"[{scope}] {display_name}: {text}",
                private_text=f"[{scope}] {display_name}: {text}",
                payload={
                    "player_id": event.user_id,
                    "display_name": display_name,
                    "text": text,
                    "scope": scope,
                    "is_command": text.startswith("/"),
                },
                tags=("chat", scope, "command" if text.startswith("/") else "free_text"),
            )
        )

    def _cmd_new(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        game_id = args[0] if args else None
        flow = self.pipeline.create_game(event.channel_id, game_id=game_id)
        return [self._public(event, f"Core game created: {flow.grimoire.game_id}.")]

    def _cmd_join(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        flow = self.pipeline.current_for_channel(event.channel_id)
        if not flow:
            flow = self.pipeline.create_game(event.channel_id)
        display_name = " ".join(args).strip() or event.display_name or event.user_id
        flow.join(event.user_id, display_name)
        return [self._public(event, f"{display_name} joined the core game.")]

    def _cmd_start(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        before = len(flow.grimoire.events)
        flow.start_setup()
        seed = args[0] if args else None
        flow.allocate_roles(seed=seed)
        flow.enter_first_night()
        messages = [self._public(event, "Core game started. First night begins.")]
        messages.extend(self._messages_from_events(event, flow.grimoire.events[before:]))
        return messages

    def _cmd_role(self, event: GatewayEvent) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        assignment = flow.grimoire.assignments.get(event.user_id)
        if not assignment:
            return [self._private(event, "You do not have a role yet.")]
        role = flow.script.role(assignment.visible_role_id)
        return [self._private(event, f"You are the {role.name}.")]

    def _cmd_status(self, event: GatewayEvent) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        alive = len(flow.grimoire.living_player_ids())
        total = len(flow.grimoire.players)
        return [
            self._public(
                event,
                (
                    f"Core game {flow.grimoire.game_id}: phase={flow.grimoire.phase.value}, "
                    f"day={flow.grimoire.day}, alive={alive}/{total}."
                ),
            )
        ]

    def _cmd_action(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        assignment = flow.grimoire.assignments.get(event.user_id)
        if not assignment:
            return [self._private(event, "You do not have a role yet.")]
        action_text = " ".join(args).strip()
        targets = self._resolve_target_ids(flow, action_text)
        result = flow.submit_night_action(
            event.user_id,
            assignment.visible_role_id,
            tuple(targets),
        )
        if not result.ok:
            return [self._private(event, f"Action rejected: {result.error}")]
        target_names = ", ".join(flow.grimoire.players[target].display_name for target in targets)
        return [self._private(event, f"Action received: {target_names}.")]

    def _cmd_resolve(self, event: GatewayEvent) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        messages: list[OutboundMessage] = []
        for result in flow.resolve_current_night():
            messages.extend(self._messages_from_result(event, result))
        flow.enter_day()
        messages.append(self._public(event, f"Day {flow.grimoire.day} begins."))
        return messages

    def _cmd_nominate(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            return [self._private(event, "Usage: /nominate <player_id>")]
        flow = self._current_flow(event)
        targets = self._resolve_target_ids(flow, " ".join(args), limit=1)
        if not targets:
            return [self._private(event, "Usage: /nominate <player_id>")]
        result = flow.nominate(event.user_id, targets[0])
        return self._messages_from_result(event, result)

    def _cmd_vote(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        yes = not args or args[0].lower() in {"yes", "y", "true", "1"}
        result = flow.vote(event.user_id, yes)
        return self._messages_from_result(event, result)

    def _cmd_slayer(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            return [self._private(event, "Usage: /slayer <player_id>")]
        flow = self._current_flow(event)
        targets = self._resolve_target_ids(flow, " ".join(args), limit=1)
        if not targets:
            return [self._private(event, "Usage: /slayer <player_id>")]
        result = flow.slayer_shoot(event.user_id, targets[0])
        return self._messages_from_result(event, result)

    def _resolve_target_ids(self, flow: object, text: str, limit: int | None = None) -> list[str]:
        normalized = self._normalize_text(text)
        matches: list[tuple[int, int, str]] = []
        for player_id, aliases in self._player_aliases(flow).items():
            for alias in aliases:
                pattern = self._alias_pattern(alias)
                match = re.search(pattern, normalized)
                if match:
                    matches.append((match.start(), -(match.end() - match.start()), player_id))
                    break
        ordered: list[str] = []
        for _, _, player_id in sorted(matches):
            if player_id not in ordered:
                ordered.append(player_id)
            if limit and len(ordered) >= limit:
                break
        return ordered

    def _player_aliases(self, flow: object) -> dict[str, set[str]]:
        aliases: dict[str, set[str]] = {}
        for player_id, player in flow.grimoire.players.items():
            seat = flow.grimoire.seat_of(player_id)
            values = {
                player_id,
                player.display_name,
                player.display_name.lower(),
            }
            if seat is not None:
                values.update(
                    {
                        str(seat),
                        f"p{seat}",
                        f"player{seat}",
                        f"seat{seat}",
                        f"{seat}号",
                        f"{seat}號",
                    }
                )
            aliases[player_id] = {self._normalize_text(value) for value in values if value}
        return aliases

    @staticmethod
    def _normalize_text(text: str) -> str:
        return text.strip().lower().replace("＃", "#").replace("，", " ").replace("、", " ")

    @staticmethod
    def _alias_pattern(alias: str) -> str:
        escaped = re.escape(alias)
        if re.fullmatch(r"\d+", alias):
            return rf"(?<![a-z0-9])(?:#?\s*{escaped}|{escaped}\s*[号號]?)(?![a-z0-9])"
        if re.fullmatch(r"p\d+|u\d+|player\d+|seat\d+", alias):
            return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"

    @staticmethod
    def _parse_day_intent(text: str) -> dict[str, object]:
        normalized = text.strip().lower()
        yes_words = ("赞成", "同意", "投是", "yes", "y", "支持", "上票")
        no_words = ("反对", "不同意", "投否", "no", "n", "弃票", "不上票")
        if any(word in normalized for word in yes_words):
            return {"intent": "vote", "yes": True}
        if any(word in normalized for word in no_words):
            return {"intent": "vote", "yes": False}
        nominate_words = ("提名", "nominate", "我要提", "我提")
        if any(word in normalized for word in nominate_words):
            return {"intent": "nominate", "target": text}
        return {"intent": None}

    def _rules_answer(self, flow: object, event: GatewayEvent) -> str:
        return self.responder.reply(flow, event.user_id, event.text, private=event.is_private)

    def _current_flow(self, event: GatewayEvent):
        flow = self.pipeline.current_for_channel(event.channel_id)
        if not flow:
            raise ValueError("no active core game for this channel")
        return flow

    def _messages_from_result(self, event: GatewayEvent, result: object) -> list[OutboundMessage]:
        if not result.ok:
            return [self._private(event, f"Action rejected: {result.error}")]
        return [
            OutboundMessage(
                channel_id=event.channel_id,
                game_id=self._current_flow(event).grimoire.game_id,
                recipient_id=outbound.recipient_id,
                visibility=outbound.visibility.value,
                text=outbound.text,
                metadata={"core": True},
            )
            for outbound in result.outbound_messages
        ] or [self._private(event, "Done.")]

    def _messages_from_events(
        self,
        event: GatewayEvent,
        events: list[GameEvent],
    ) -> list[OutboundMessage]:
        flow = self._current_flow(event)
        messages: list[OutboundMessage] = []
        for game_event in events:
            if game_event.visibility == Visibility.PRIVATE:
                for recipient_id in game_event.recipients:
                    messages.append(
                        self._private(
                            event,
                            game_event.private_text or game_event.public_text,
                            recipient_id=recipient_id,
                            game_id=flow.grimoire.game_id,
                        )
                    )
            elif game_event.visibility == Visibility.EVIL_TEAM:
                for player_id, assignment in flow.grimoire.assignments.items():
                    if assignment.alignment.value == "evil":
                        messages.append(
                            self._private(
                                event,
                                game_event.public_text or game_event.private_text,
                                recipient_id=player_id,
                                game_id=flow.grimoire.game_id,
                            )
                        )
        return messages

    def _public(self, event: GatewayEvent, text: str) -> OutboundMessage:
        flow = self.pipeline.current_for_channel(event.channel_id)
        return OutboundMessage(
            channel_id=event.channel_id,
            game_id=flow.grimoire.game_id if flow else None,
            visibility="public",
            text=text,
            metadata={"core": True},
        )

    def _private(
        self,
        event: GatewayEvent,
        text: str,
        *,
        recipient_id: str | None = None,
        game_id: str | None = None,
    ) -> OutboundMessage:
        flow = self.pipeline.current_for_channel(event.channel_id)
        return OutboundMessage(
            channel_id=event.channel_id,
            game_id=game_id or (flow.grimoire.game_id if flow else None),
            recipient_id=recipient_id or event.user_id,
            visibility="private",
            text=text,
            metadata={"core": True},
        )

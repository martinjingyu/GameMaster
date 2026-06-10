from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any

from .config import env_bool
from .clocktower.engine import ClocktowerEngine, GameError, GameStore
from .clocktower.models import Game
from .clocktower.scripts import SCRIPTS, resolve_script
from .llm import LLMError, StorytellerLLM
from .memory import GameMemory


STORYTELLER_USER_IDS = {"__storyteller__", "__agent__", "gamemaster", "storyteller"}


@dataclass
class GatewayEvent:
    channel_id: str
    user_id: str
    text: str
    display_name: str | None = None
    is_private: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GatewayEvent":
        return cls(
            channel_id=str(payload.get("channel_id") or payload.get("room_id") or "default"),
            user_id=str(payload.get("user_id") or payload.get("sender_id") or "anonymous"),
            display_name=payload.get("display_name") or payload.get("sender_name"),
            text=str(payload.get("text") or payload.get("message") or ""),
            is_private=bool(payload.get("is_private") or payload.get("private") or False),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class OutboundMessage:
    channel_id: str
    text: str
    game_id: str | None = None
    recipient_id: str | None = None
    visibility: str = "public"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "game_id": self.game_id,
            "recipient_id": self.recipient_id,
            "visibility": self.visibility,
            "text": self.text,
            "metadata": self.metadata,
        }


class GameMasterAgent:
    def __init__(self, store: GameStore, llm: StorytellerLLM | None = None):
        self.store = store
        self.engine = ClocktowerEngine(store)
        self.llm = llm or StorytellerLLM.from_env()
        self.memory = GameMemory()
        self.allow_player_storyteller_commands = env_bool(
            "GAMEMASTER_ALLOW_PLAYER_ST_COMMANDS", False
        )

    def handle_event(self, event: GatewayEvent) -> list[OutboundMessage]:
        before_game = self.store.current_for_channel(event.channel_id)
        if before_game:
            self.memory.record(
                before_game,
                "inbound_message",
                actor_id=event.user_id,
                actor_name=event.display_name,
                visibility="private" if event.is_private else "public",
                recipient_id="__storyteller__" if event.is_private else None,
                text=event.text,
                payload={"metadata": event.metadata},
            )

        messages = self._handle_event(event)
        after_game = self.store.current_for_channel(event.channel_id)
        if after_game:
            if not before_game and event.text.strip().startswith("/new"):
                self.memory.record(
                    after_game,
                    "inbound_message",
                    actor_id=event.user_id,
                    actor_name=event.display_name,
                    visibility="private" if event.is_private else "public",
                    recipient_id="__storyteller__" if event.is_private else None,
                    text=event.text,
                    payload={"metadata": event.metadata},
                    tags=["game_bootstrap"],
                )
            self.memory.record_outbound_batch(after_game, messages)
            self.store.save()
        return messages

    def _handle_event(self, event: GatewayEvent) -> list[OutboundMessage]:
        text = event.text.strip()
        if not text:
            return []
        if not text.startswith("/"):
            return self._handle_free_text(event)

        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return [self._public(event, f"命令格式解析失败：{exc}")]
        command = tokens[0].lower()
        args = tokens[1:]

        try:
            if command in ("/help", "/?", "/菜单"):
                return [self._private(event, self.help_text())]
            if command in ("/new", "/create", "/开局"):
                return self._cmd_new(event, args)
            if command in ("/join", "/加入"):
                return self._cmd_join(event, args)
            if command in ("/start", "/开始"):
                return self._cmd_start(event, args)
            if command in ("/status", "/状态"):
                game = self._current_game(event)
                return [self._public(event, self.engine.public_status(game), game)]
            if command in ("/sheet", "/script", "/剧本"):
                game = self._current_game(event)
                return [self._private(event, self.engine.script_sheet(game), game)]
            if command in ("/role", "/身份"):
                return self._cmd_role(event)
            if command in ("/day", "/白天"):
                game = self._current_game(event)
                self._require_storyteller(event)
                return [self._public(event, self.engine.begin_day(game), game)]
            if command in ("/night", "/夜晚"):
                game = self._current_game(event)
                self._require_storyteller(event)
                return [self._public(event, self.engine.begin_night(game), game)]
            if command in ("/action", "/行动"):
                return self._cmd_action(event, args)
            if command in ("/actions", "/行动列表"):
                game = self._current_game(event)
                self._require_storyteller(event)
                return [self._private(event, self.engine.list_actions(game), game)]
            if command in ("/resolve", "/结算"):
                return self._cmd_resolve(event)
            if command in ("/nominate", "/提名"):
                return self._cmd_nominate(event, args)
            if command in ("/vote", "/投票"):
                return self._cmd_vote(event, args)
            if command in ("/closevote", "/结票"):
                game = self._current_game(event)
                return [self._public(event, self.engine.close_vote(game), game)]
            if command in ("/execute", "/处决"):
                return self._cmd_execute(event, args)
            if command in ("/kill", "/死亡"):
                return self._cmd_kill(event, args)
            if command in ("/revive", "/复活"):
                return self._cmd_revive(event, args)
            if command in ("/info", "/私信"):
                return self._cmd_info(event, args)
            if command in ("/scripts", "/剧本列表"):
                names = "\n".join(f"- {script.script_id}: {script.name}" for script in SCRIPTS.values())
                return [self._private(event, f"可用剧本：\n{names}")]
            return [self._private(event, f"未知命令：{command}\n\n{self.help_text()}")]
        except GameError as exc:
            return [self._private(event, f"说书人提示：{exc}")]
        except ValueError as exc:
            return [self._private(event, f"说书人提示：{exc}")]

    def _handle_free_text(self, event: GatewayEvent) -> list[OutboundMessage]:
        game = self.store.current_for_channel(event.channel_id)
        if event.is_private and game and game.phase == "night":
            try:
                reply = self.engine.record_action(game, event.user_id, event.text)
            except GameError as exc:
                return [self._private(event, f"说书人提示：{exc}", game)]
            llm_reply = self._llm_reply(event, game)
            if llm_reply:
                reply = llm_reply
            return [self._private(event, reply, game)]
        if self._should_llm_answer(event):
            llm_reply = self._llm_reply(event, game)
            if llm_reply:
                visibility = "private" if event.is_private else "public"
                return [
                    OutboundMessage(
                        channel_id=event.channel_id,
                        game_id=game.game_id if game else None,
                        recipient_id=event.user_id if event.is_private else None,
                        visibility=visibility,
                        text=llm_reply,
                    )
                ]
        return []

    def _cmd_new(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        script_name = args[0] if args else None
        game = self.engine.create_game(
            channel_id=event.channel_id,
            owner_id="__agent__",
            script_name=script_name,
        )
        script = resolve_script(game.script_id)
        return [
            self._public(
                event,
                (
                    f"已创建游戏 {game.game_id}：{script.name}。\n"
                    "玩家发送 /join 加入；人数够了由说书人 agent 发送 /start。"
                ),
                game,
            )
        ]

    def _cmd_join(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        game = self._current_game(event)
        display_name = " ".join(args).strip() or event.display_name or event.user_id
        player = self.engine.add_player(game, event.user_id, display_name)
        return [
            self._public(
                event,
                f"{player.display_name} 加入游戏，座位号 {player.seat}。当前人数：{len(game.players)}。",
                game,
            )
        ]

    def _cmd_start(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        game = self._current_game(event)
        self._require_storyteller(event)
        seed = args[0] if args else None
        report = self.engine.start_game(game, seed=seed)
        messages = [self._public(event, report.public_summary, game)]
        for player in game.players:
            role_text = report.private_roles[player.user_id]
            if player.role_name == "Drunk" and player.apparent_role_name:
                player_text = "\n".join(
                    line
                    for line in role_text.splitlines()
                    if not line.startswith("说书人备注：")
                )
            else:
                player_text = role_text
            messages.append(
                OutboundMessage(
                    channel_id=event.channel_id,
                    game_id=game.game_id,
                    recipient_id=player.user_id,
                    visibility="private",
                    text=player_text,
                )
            )
        return messages

    def _cmd_role(self, event: GatewayEvent) -> list[OutboundMessage]:
        game = self._current_game(event)
        player = game.player_by_id(event.user_id)
        if not player or not player.role_name:
            raise GameError("你还没有身份。")
        shown = player.shown_role or player.role_name
        return [self._private(event, f"你的身份是：{shown}。阵营：{self._alignment_label(player.alignment)}。", game)]

    def _cmd_action(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        game = self._current_game(event)
        if not args:
            raise GameError("请在 /action 后写明你的夜间行动。")
        reply = self.engine.record_action(game, event.user_id, " ".join(args))
        return [self._private(event, reply, game)]

    def _cmd_nominate(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            raise GameError("用法：/nominate <玩家名|座位号>")
        game = self._current_game(event)
        target = self.engine.find_player(game, args[0])
        return [self._public(event, self.engine.nominate(game, event.user_id, target), game)]

    def _cmd_vote(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            raise GameError("用法：/vote yes 或 /vote no")
        game = self._current_game(event)
        yes_words = {"yes", "y", "true", "1", "赞成", "是", "投", "同意"}
        no_words = {"no", "n", "false", "0", "反对", "否", "不投", "不同意"}
        value = args[0].lower()
        if value not in yes_words | no_words:
            raise GameError("投票只能是 yes/no。")
        return [self._public(event, self.engine.vote(game, event.user_id, value in yes_words), game)]

    def _cmd_execute(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            raise GameError("用法：/execute <玩家名|座位号>")
        game = self._current_game(event)
        self._require_storyteller(event)
        target = self.engine.find_player(game, args[0])
        return [self._public(event, self.engine.execute(game, target), game)]

    def _cmd_kill(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            raise GameError("用法：/kill <玩家名|座位号> [原因]")
        game = self._current_game(event)
        self._require_storyteller(event)
        target = self.engine.find_player(game, args[0])
        cause = " ".join(args[1:]) or "说书人结算"
        return [self._public(event, self.engine.kill(game, target, cause=cause), game)]

    def _cmd_revive(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if not args:
            raise GameError("用法：/revive <玩家名|座位号>")
        game = self._current_game(event)
        self._require_storyteller(event)
        target = self.engine.find_player(game, args[0])
        return [self._public(event, self.engine.revive(game, target), game)]

    def _cmd_info(self, event: GatewayEvent, args: list[str]) -> list[OutboundMessage]:
        if len(args) < 2:
            raise GameError("用法：/info <玩家名|座位号> <私密信息>")
        game = self._current_game(event)
        self._require_storyteller(event)
        target = self.engine.find_player(game, args[0])
        return [
            OutboundMessage(
                channel_id=event.channel_id,
                game_id=game.game_id,
                recipient_id=target.user_id,
                visibility="private",
                text="说书人私信：" + " ".join(args[1:]),
            )
        ]

    def _cmd_resolve(self, event: GatewayEvent) -> list[OutboundMessage]:
        game = self._current_game(event)
        self._require_storyteller(event)
        try:
            memory_context = self.memory.prompt_context(game, include_private=True, max_events=40)
            resolution = self.llm.resolve_night(game, memory_context=memory_context)
        except LLMError as exc:
            raise GameError(str(exc)) from exc

        messages: list[OutboundMessage] = []
        if resolution.public:
            messages.append(self._public(event, resolution.public, game))

        for user_id in resolution.kills:
            target = game.player_by_id(user_id)
            if target:
                messages.append(self._public(event, self.engine.kill(game, target, cause="LLM 夜晚结算"), game))

        for user_id in resolution.revives:
            target = game.player_by_id(user_id)
            if target:
                messages.append(self._public(event, self.engine.revive(game, target), game))

        for item in resolution.private:
            messages.append(
                OutboundMessage(
                    channel_id=event.channel_id,
                    game_id=game.game_id,
                    recipient_id=item.user_id,
                    visibility="private",
                    text=item.text,
                )
            )

        if resolution.notes:
            messages.append(self._private(event, "LLM 结算备注：" + resolution.notes, game))

        self.memory.record(
            game,
            "night_resolution",
            actor_id="__storyteller__",
            actor_name="GameMaster",
            visibility="system",
            text=resolution.notes or resolution.public or "night resolved",
            payload={
                "public": resolution.public,
                "private_count": len(resolution.private),
                "kills": resolution.kills,
                "revives": resolution.revives,
            },
            tags=["important", "llm"],
        )

        game.night_actions.clear()
        self.store.save()
        if not messages:
            messages.append(self._private(event, "LLM 没有生成需要发送的结算消息。", game))
        return messages

    def _current_game(self, event: GatewayEvent) -> Game:
        game = self.store.current_for_channel(event.channel_id)
        if not game:
            raise GameError("当前频道还没有游戏。先发送 /new tb 创建一局。")
        return game

    def _require_storyteller(self, event: GatewayEvent) -> None:
        if self.allow_player_storyteller_commands:
            return
        if event.user_id.lower() in STORYTELLER_USER_IDS:
            return
        if event.metadata.get("storyteller") is True:
            return
        raise GameError("这个命令由说书人 agent 执行；本地测试页面请用测试控制台按钮。")

    def _should_llm_answer(self, event: GatewayEvent) -> bool:
        if not self.llm.configured:
            return False
        if event.is_private:
            return True
        lowered = event.text.lower()
        triggers = ("说书人", "主持", "gm", "gamemaster", "?")
        return event.text.endswith("？") or any(trigger in lowered for trigger in triggers)

    def _llm_reply(self, event: GatewayEvent, game: Game | None) -> str | None:
        if not self.llm.configured:
            return None
        player_role = None
        if game and event.is_private:
            player = game.player_by_id(event.user_id)
            if player:
                player_role = player.shown_role
        try:
            memory_context = (
                self.memory.prompt_context(
                    game,
                    perspective_user_id=event.user_id,
                    include_private=event.user_id.lower() in STORYTELLER_USER_IDS
                    or event.metadata.get("storyteller") is True,
                )
                if game
                else None
            )
            return self.llm.reply_to_message(
                game=game,
                user_id=event.user_id,
                text=event.text,
                private=event.is_private,
                player_role=player_role,
                memory_context=memory_context,
            )
        except LLMError as exc:
            return f"LLM 暂时不可用：{exc}"

    def _public(self, event: GatewayEvent, text: str, game: Game | None = None) -> OutboundMessage:
        return OutboundMessage(
            channel_id=event.channel_id,
            game_id=game.game_id if game else None,
            visibility="public",
            text=text,
        )

    def _private(self, event: GatewayEvent, text: str, game: Game | None = None) -> OutboundMessage:
        return OutboundMessage(
            channel_id=event.channel_id,
            game_id=game.game_id if game else None,
            recipient_id=event.user_id,
            visibility="private",
            text=text,
        )

    @staticmethod
    def _alignment_label(alignment: str) -> str:
        return "邪恶" if alignment == "evil" else "善良"

    @staticmethod
    def help_text() -> str:
        return (
            "GameMaster 说书人命令：\n"
            "/new [tb|bmr|sv] - 创建游戏\n"
            "/join [昵称] - 加入当前游戏\n"
            "/start [seed] - 分配身份并进入首夜\n"
            "/role - 私聊查看自己的身份\n"
            "/status - 查看公开状态\n"
            "/sheet - 查看当前剧本角色表\n"
            "/day 或 /night - 切换白天/夜晚（说书人）\n"
            "/action <内容> - 私聊提交夜间行动\n"
            "/actions - 查看最近行动（说书人）\n"
            "/resolve - 使用 LLM 自动生成夜晚结算（说书人）\n"
            "/nominate <玩家>、/vote yes|no、/closevote - 提名投票\n"
            "/execute、/kill、/revive、/info - 说书人结算工具"
        )

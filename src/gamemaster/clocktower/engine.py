from __future__ import annotations

import json
import random
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import Game, Nomination, Player
from .scripts import (
    ROLE_DEMON,
    ROLE_MINION,
    ROLE_OUTSIDER,
    ROLE_TOWNSFOLK,
    TEAM_EVIL,
    TEAM_GOOD,
    Role,
    Script,
    resolve_script,
)


PLAYER_DISTRIBUTION: dict[int, tuple[int, int, int, int]] = {
    5: (3, 0, 1, 1),
    6: (3, 1, 1, 1),
    7: (5, 0, 1, 1),
    8: (5, 1, 1, 1),
    9: (5, 2, 1, 1),
    10: (7, 0, 2, 1),
    11: (7, 1, 2, 1),
    12: (7, 2, 2, 1),
    13: (9, 0, 3, 1),
    14: (9, 1, 3, 1),
    15: (9, 2, 3, 1),
}


class GameError(ValueError):
    """Raised when a game command cannot be applied."""


@dataclass
class StartReport:
    public_summary: str
    private_roles: dict[str, str]


class GameStore:
    def __init__(self, data_path: Path | None = None):
        self.data_path = data_path
        self.games: dict[str, Game] = {}
        if data_path and data_path.exists():
            self.load()

    def load(self) -> None:
        if not self.data_path:
            return
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.games = {
            game_id: Game.from_dict(game_payload)
            for game_id, game_payload in payload.get("games", {}).items()
        }

    def save(self) -> None:
        if not self.data_path:
            return
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"games": {game_id: game.to_dict() for game_id, game in self.games.items()}}
        self.data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, game: Game) -> None:
        self.games[game.game_id] = game
        self.save()

    def get(self, game_id: str) -> Game:
        try:
            return self.games[game_id]
        except KeyError as exc:
            raise GameError(f"找不到游戏 {game_id}。") from exc

    def current_for_channel(self, channel_id: str) -> Game | None:
        matches = [game for game in self.games.values() if game.channel_id == channel_id]
        if not matches:
            return None
        unfinished = [game for game in matches if game.winner is None]
        return (unfinished or matches)[-1]


class ClocktowerEngine:
    def __init__(self, store: GameStore):
        self.store = store

    def create_game(
        self,
        channel_id: str,
        owner_id: str,
        script_name: str | None = None,
        game_id: str | None = None,
    ) -> Game:
        script = resolve_script(script_name)
        game = Game(
            game_id=game_id or secrets.token_hex(4),
            channel_id=channel_id,
            owner_id=owner_id,
            script_id=script.script_id,
        )
        self.store.add(game)
        return game

    def add_player(self, game: Game, user_id: str, display_name: str) -> Player:
        if game.phase != "lobby":
            raise GameError("游戏已经开始，不能再加入普通玩家。")
        existing = game.player_by_id(user_id)
        if existing:
            existing.display_name = display_name or existing.display_name
            self.store.save()
            return existing
        if len(game.players) >= 15:
            raise GameError("普通玩家上限是 15 人；更多玩家建议作为旅行者加入。")
        player = Player(user_id=user_id, display_name=display_name or user_id, seat=len(game.players) + 1)
        game.players.append(player)
        self.store.save()
        return player

    def start_game(self, game: Game, seed: str | None = None) -> StartReport:
        if game.phase != "lobby":
            raise GameError("游戏已经开始。")
        player_count = len(game.players)
        if player_count not in PLAYER_DISTRIBUTION:
            raise GameError("需要 5 到 15 名普通玩家才能开始。")

        script = resolve_script(game.script_id)
        rng = random.Random(seed)
        assignments, bluffs = self._build_assignments(script, player_count, rng)
        shuffled_players = list(game.players)
        rng.shuffle(shuffled_players)

        for player, role in zip(shuffled_players, assignments, strict=True):
            player.role_name = role.name
            player.apparent_role_name = None
            player.alignment = role.team
            player.alive = True
            player.ghost_vote = True
            player.reminders.clear()

        self._apply_drunk(script, shuffled_players, assignments, rng)
        game.bluffs = [role.name for role in bluffs]
        game.phase = "night"
        game.day = 0
        game.public_log.append(f"游戏开始：{script.name}，{player_count} 名玩家。")
        private_roles = self._private_role_messages(game, script)
        self.store.save()

        return StartReport(
            public_summary=(
                f"游戏 {game.game_id} 开始。剧本：{script.name}。"
                f"现在进入首夜，请玩家等待私聊信息。"
            ),
            private_roles=private_roles,
        )

    def _build_assignments(
        self, script: Script, player_count: int, rng: random.Random
    ) -> tuple[list[Role], list[Role]]:
        townsfolk_count, outsider_count, minion_count, demon_count = PLAYER_DISTRIBUTION[player_count]
        demons = rng.sample(script.roles_by_type(ROLE_DEMON), demon_count)
        minions = rng.sample(script.roles_by_type(ROLE_MINION), minion_count)

        outsider_delta = sum(role.outsider_delta for role in (*demons, *minions))
        outsider_count = max(0, min(outsider_count + outsider_delta, player_count - minion_count - demon_count))
        townsfolk_count = player_count - outsider_count - minion_count - demon_count

        outsiders = rng.sample(script.roles_by_type(ROLE_OUTSIDER), outsider_count)
        townsfolk = rng.sample(script.roles_by_type(ROLE_TOWNSFOLK), townsfolk_count)

        in_play = [*townsfolk, *outsiders, *minions, *demons]
        bluff_pool = [
            role
            for role in script.roles_by_type(ROLE_TOWNSFOLK) + script.roles_by_type(ROLE_OUTSIDER)
            if role.name not in {played.name for played in in_play}
        ]
        bluffs = rng.sample(bluff_pool, min(3, len(bluff_pool)))
        return in_play, bluffs

    def _apply_drunk(
        self,
        script: Script,
        players: list[Player],
        assignments: list[Role],
        rng: random.Random,
    ) -> None:
        drunk_players = [
            player for player, role in zip(players, assignments, strict=True) if role.name == "Drunk"
        ]
        if not drunk_players:
            return

        used = {role.name for role in assignments}
        available_townsfolk = [role for role in script.roles_by_type(ROLE_TOWNSFOLK) if role.name not in used]
        if not available_townsfolk:
            available_townsfolk = script.roles_by_type(ROLE_TOWNSFOLK)

        for player in drunk_players:
            apparent = rng.choice(available_townsfolk)
            player.apparent_role_name = apparent.name
            player.reminders.append("drunk")

    def _private_role_messages(self, game: Game, script: Script) -> dict[str, str]:
        evil_players = [player for player in game.players if player.alignment == TEAM_EVIL]
        demons = [player for player in evil_players if self._role(script, player).role_type == ROLE_DEMON]
        minions = [player for player in evil_players if self._role(script, player).role_type == ROLE_MINION]
        minion_names = ", ".join(player.display_name for player in minions) or "没有爪牙"
        demon_names = ", ".join(player.display_name for player in demons) or "未知"
        bluff_text = ", ".join(game.bluffs) or "无"

        messages: dict[str, str] = {}
        for player in game.players:
            role = self._role(script, player)
            shown_role = player.shown_role or role.name
            shown_role_info = script.by_name(shown_role)
            lines = [
                f"你的身份是：{shown_role}。",
                f"阵营：{'邪恶' if player.alignment == TEAM_EVIL else '善良'}。",
                f"角色提示：{shown_role_info.summary}",
            ]
            if player.role_name == "Drunk" and player.apparent_role_name:
                lines.append("说书人备注：你实际是酒鬼；此行只会发给主持日志，不应转发给玩家。")
            if role.role_type == ROLE_MINION:
                lines.append(f"邪恶信息：恶魔是 {demon_names}；爪牙同伴：{minion_names}。")
            if role.role_type == ROLE_DEMON:
                if len(game.players) >= 7:
                    lines.append(f"邪恶信息：爪牙是 {minion_names}。")
                lines.append(f"恶魔伪装角色：{bluff_text}。")
            messages[player.user_id] = "\n".join(lines)
        return messages

    def _role(self, script: Script, player: Player) -> Role:
        if not player.role_name:
            raise GameError(f"{player.display_name} 还没有角色。")
        return script.by_name(player.role_name)

    def public_status(self, game: Game) -> str:
        script = resolve_script(game.script_id)
        rows = [
            f"游戏：{game.game_id}",
            f"剧本：{script.name}",
            f"阶段：{self.phase_label(game.phase)}，第 {game.day} 天",
        ]
        if game.winner:
            rows.append(f"胜者：{self.team_label(game.winner)}")
        rows.append("玩家：")
        for player in sorted(game.players, key=lambda item: item.seat):
            life = "存活" if player.alive else ("死亡，有鬼票" if player.ghost_vote else "死亡，无鬼票")
            rows.append(f"{player.seat}. {player.display_name} - {life}")
        return "\n".join(rows)

    def script_sheet(self, game: Game) -> str:
        script = resolve_script(game.script_id)
        labels = {
            ROLE_TOWNSFOLK: "镇民",
            ROLE_OUTSIDER: "外来者",
            ROLE_MINION: "爪牙",
            ROLE_DEMON: "恶魔",
        }
        rows = [f"{script.name} 角色表："]
        for role_type, label in labels.items():
            rows.append(f"{label}：" + "、".join(role.name for role in script.roles_by_type(role_type)))
        return "\n".join(rows)

    def begin_day(self, game: Game) -> str:
        if game.winner:
            raise GameError("游戏已经结束。")
        game.phase = "day"
        game.day += 1
        game.public_log.append(f"第 {game.day} 天开始。")
        self.store.save()
        return f"天亮了。现在是第 {game.day} 天，玩家可以公开讨论、私聊、提名。"

    def begin_night(self, game: Game) -> str:
        if game.winner:
            raise GameError("游戏已经结束。")
        game.phase = "night"
        game.public_log.append(f"第 {game.day} 天结束，进入夜晚。")
        self.store.save()
        return "夜幕降临。请所有玩家停止公开讨论，按私聊提示提交夜间行动。"

    def record_action(self, game: Game, user_id: str, text: str) -> str:
        player = game.player_by_id(user_id)
        if not player:
            raise GameError("你还没有加入这局游戏。")
        game.night_actions.append(
            {
                "day": str(game.day),
                "phase": game.phase,
                "user_id": user_id,
                "display_name": player.display_name,
                "text": text,
            }
        )
        self.store.save()
        return "行动已记录。说书人会把它纳入当晚结算。"

    def list_actions(self, game: Game) -> str:
        if not game.night_actions:
            return "目前没有记录的行动。"
        rows = ["已记录行动："]
        for item in game.night_actions[-20:]:
            rows.append(
                f"[{item['phase']} D{item['day']}] {item['display_name']}：{item['text']}"
            )
        return "\n".join(rows)

    def nominate(self, game: Game, nominator_id: str, target: Player) -> str:
        if game.phase != "day":
            raise GameError("只有白天可以提名。")
        if game.active_nomination():
            raise GameError("当前已有未关闭的提名，请先 /closevote。")
        nominator = game.player_by_id(nominator_id)
        if not nominator:
            raise GameError("你还没有加入这局游戏。")
        if not nominator.alive:
            raise GameError("死亡玩家不能提名。")
        nomination = Nomination(nominator_id=nominator_id, target_id=target.user_id)
        game.nominations.append(nomination)
        self.store.save()
        threshold = self.execution_threshold(game)
        return f"{nominator.display_name} 提名 {target.display_name}。处决门槛是 {threshold} 票。请用 /vote yes 或 /vote no 投票。"

    def vote(self, game: Game, voter_id: str, yes: bool) -> str:
        nomination = game.active_nomination()
        if not nomination:
            raise GameError("当前没有进行中的投票。")
        voter = game.player_by_id(voter_id)
        if not voter:
            raise GameError("你还没有加入这局游戏。")
        if not voter.alive and not voter.ghost_vote:
            raise GameError("你已经用过鬼票，不能再投票。")
        nomination.votes[voter_id] = yes
        if yes and not voter.alive:
            voter.ghost_vote = False
        self.store.save()
        return f"{voter.display_name} 投票：{'赞成' if yes else '反对'}。当前赞成票：{nomination.yes_count()}。"

    def close_vote(self, game: Game) -> str:
        nomination = game.active_nomination()
        if not nomination:
            raise GameError("当前没有进行中的投票。")
        nomination.closed = True
        target = game.player_by_id(nomination.target_id)
        if not target:
            raise GameError("提名目标不存在。")
        threshold = self.execution_threshold(game)
        if nomination.yes_count() < threshold:
            self.store.save()
            return f"投票关闭。{target.display_name} 获得 {nomination.yes_count()} 票，未达到 {threshold} 票门槛。"
        result = self.execute(game, target)
        return f"投票关闭。{target.display_name} 达到处决门槛。\n{result}"

    def execute(self, game: Game, target: Player) -> str:
        if not target.alive:
            raise GameError(f"{target.display_name} 已经死亡。")
        target.alive = False
        game.public_log.append(f"{target.display_name} 被处决。")

        script = resolve_script(game.script_id)
        role = self._role(script, target)
        if role.name == "Saint":
            game.winner = TEAM_EVIL
            self.store.save()
            return f"{target.display_name} 被处决并死亡。善良阵营处决了圣徒，邪恶阵营获胜。"

        transfer = self._maybe_transfer_demon(game, target, script)
        winner = self.check_win(game)
        self.store.save()
        tail = f"\n{self.team_label(winner)}获胜。" if winner else ""
        transfer_text = f"\n{transfer}" if transfer else ""
        return f"{target.display_name} 被处决并死亡。{transfer_text}{tail}"

    def kill(self, game: Game, target: Player, cause: str = "死亡") -> str:
        if not target.alive:
            raise GameError(f"{target.display_name} 已经死亡。")
        target.alive = False
        game.public_log.append(f"{target.display_name} 死亡：{cause}。")
        winner = self.check_win(game)
        self.store.save()
        tail = f"\n{self.team_label(winner)}获胜。" if winner else ""
        return f"{target.display_name} 死亡。{tail}"

    def revive(self, game: Game, target: Player) -> str:
        if target.alive:
            raise GameError(f"{target.display_name} 仍然存活。")
        target.alive = True
        game.public_log.append(f"{target.display_name} 复活。")
        self.store.save()
        return f"{target.display_name} 复活。"

    def _maybe_transfer_demon(self, game: Game, dead_demon: Player, script: Script) -> str | None:
        role = self._role(script, dead_demon)
        if role.role_type != ROLE_DEMON:
            return None
        if len(game.living_players()) < 5:
            return None
        scarlet = next(
            (
                player
                for player in game.living_players()
                if player.role_name == "Scarlet Woman" and player.alignment == TEAM_EVIL
            ),
            None,
        )
        if not scarlet:
            return None
        scarlet.role_name = "Imp"
        scarlet.apparent_role_name = None
        scarlet.reminders.append("became_demon")
        return "说书人私密提示：猩红女郎已成为新的 Imp。"

    def check_win(self, game: Game) -> str | None:
        if game.winner:
            return game.winner
        script = resolve_script(game.script_id)
        living = game.living_players()
        demon_alive = any(
            self._role(script, player).role_type == ROLE_DEMON for player in living if player.role_name
        )
        if not demon_alive:
            game.winner = TEAM_GOOD
            return game.winner
        if len(living) <= 2:
            game.winner = TEAM_EVIL
            return game.winner
        return None

    def execution_threshold(self, game: Game) -> int:
        living_count = len(game.living_players())
        return living_count // 2 + 1

    def find_player(self, game: Game, query: str) -> Player:
        normalized = query.strip().lstrip("@").lower()
        if not normalized:
            raise GameError("需要指定玩家。")
        if normalized.isdigit():
            seat = int(normalized)
            match = next((player for player in game.players if player.seat == seat), None)
            if match:
                return match
        candidates: Iterable[Player] = game.players
        for player in candidates:
            names = {player.user_id.lower(), player.display_name.lower()}
            if normalized in names:
                return player
        partial = [player for player in game.players if normalized in player.display_name.lower()]
        if len(partial) == 1:
            return partial[0]
        if partial:
            names = ", ".join(player.display_name for player in partial)
            raise GameError(f"玩家名不唯一：{names}")
        raise GameError(f"找不到玩家 {query}。")

    @staticmethod
    def phase_label(phase: str) -> str:
        return {"lobby": "等待加入", "night": "夜晚", "day": "白天", "ended": "已结束"}.get(phase, phase)

    @staticmethod
    def team_label(team: str) -> str:
        return "善良阵营" if team == TEAM_GOOD else "邪恶阵营"

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from .clocktower.models import Game
from .clocktower.scripts import TEAM_EVIL, resolve_script


class LLMError(RuntimeError):
    """Raised when the storyteller LLM cannot complete a request."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None
    model: str | None = None
    temperature: float = 0.4
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=os.getenv("GAMEMASTER_LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("GAMEMASTER_LLM_API_KEY") or None,
            model=os.getenv("GAMEMASTER_LLM_MODEL") or None,
            temperature=float(os.getenv("GAMEMASTER_LLM_TEMPERATURE", "0.4")),
            timeout_seconds=float(os.getenv("GAMEMASTER_LLM_TIMEOUT_SECONDS", "30")),
        )

    @property
    def configured(self) -> bool:
        if not self.model:
            return False
        if self.api_key:
            return True
        return not self.base_url.rstrip("/") == "https://api.openai.com/v1"


class OpenAICompatibleClient:
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.from_env()

    @property
    def configured(self) -> bool:
        return self.config.configured

    def complete(self, messages: list[dict[str, str]], response_format: str = "text") -> str:
        if not self.config.configured:
            raise LLMError("LLM 尚未配置。请在 .env 里设置 GAMEMASTER_LLM_MODEL 和 API key/base URL。")

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM HTTP {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"LLM 请求失败：{exc}") from exc

        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"LLM 响应格式不符合预期：{data}") from exc

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers


@dataclass
class PrivateResolution:
    user_id: str
    text: str


@dataclass
class NightResolution:
    public: str = ""
    private: list[PrivateResolution] = field(default_factory=list)
    kills: list[str] = field(default_factory=list)
    revives: list[str] = field(default_factory=list)
    notes: str = ""


class StorytellerLLM:
    def __init__(self, client: OpenAICompatibleClient | None = None):
        self.client = client or OpenAICompatibleClient()

    @classmethod
    def from_env(cls) -> "StorytellerLLM":
        return cls(OpenAICompatibleClient(LLMConfig.from_env()))

    @property
    def configured(self) -> bool:
        return self.client.configured

    def status(self) -> dict[str, Any]:
        config = self.client.config
        return {
            "configured": self.configured,
            "base_url": config.base_url,
            "model": config.model,
            "has_api_key": bool(config.api_key),
        }

    def reply_to_message(
        self,
        game: Game | None,
        user_id: str,
        text: str,
        private: bool,
        player_role: str | None = None,
        memory_context: dict[str, Any] | None = None,
    ) -> str | None:
        if not self.configured:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "你是《血染钟楼》的 AI 说书人。用简洁中文回复。"
                    "公开频道只能使用公开信息；私聊可以回应该玩家自己的身份和行动，"
                    "但绝不能泄露其他玩家的隐藏身份、阵营或夜间行动。"
                    "不要逐字复述官方规则文本，使用概括说明。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "visibility": "private" if private else "public",
                        "player_role": player_role,
                        "game_public_state": self._public_snapshot(game) if game else None,
                        "memory": memory_context,
                        "player_message": text,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        return self.client.complete(messages).strip()

    def resolve_night(
        self, game: Game, memory_context: dict[str, Any] | None = None
    ) -> NightResolution:
        if not self.configured:
            raise LLMError("LLM 尚未配置，不能自动结算夜晚。")

        script = resolve_script(game.script_id)
        payload = {
            "instruction": (
                "根据当前魔典和玩家夜间行动，为这一夜生成说书人结算。"
                "输出 JSON，不要输出额外文本。"
                "只在确定需要时使用 kills/revives；复杂或不确定的规则写入 notes。"
            ),
            "schema": {
                "public": "天亮时可公开宣布的文本，可为空",
                "private": [{"user_id": "玩家 user_id", "text": "私密回复"}],
                "kills": ["需要死亡的 user_id"],
                "revives": ["需要复活的 user_id"],
                "notes": "给说书人的结算备注",
            },
            "script": script.name,
            "phase": game.phase,
            "day": game.day,
            "players": [
                {
                    "user_id": player.user_id,
                    "name": player.display_name,
                    "seat": player.seat,
                    "role": player.role_name,
                    "shown_role": player.shown_role,
                    "alignment": player.alignment,
                    "alive": player.alive,
                    "reminders": player.reminders,
                }
                for player in game.players
            ],
            "demon_bluffs": game.bluffs,
            "memory": memory_context,
            "night_actions": game.night_actions[-40:],
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是严谨的《血染钟楼》AI 说书人。"
                    "你可以辅助结算，但不能编造不存在的玩家。"
                    "保持游戏可玩性；不确定时不要擅自杀人，把原因写入 notes。"
                    "必须输出单个 JSON object。"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        raw = self.client.complete(messages, response_format="json")
        data = self._parse_json_object(raw)
        return NightResolution(
            public=str(data.get("public") or ""),
            private=[
                PrivateResolution(user_id=str(item.get("user_id")), text=str(item.get("text") or ""))
                for item in data.get("private", [])
                if item.get("user_id") and item.get("text")
            ],
            kills=[str(item) for item in data.get("kills", [])],
            revives=[str(item) for item in data.get("revives", [])],
            notes=str(data.get("notes") or ""),
        )

    def _public_snapshot(self, game: Game | None) -> dict[str, Any] | None:
        if not game:
            return None
        return {
            "game_id": game.game_id,
            "script_id": game.script_id,
            "phase": game.phase,
            "day": game.day,
            "winner": game.winner,
            "players": [
                {
                    "user_id": player.user_id,
                    "name": player.display_name,
                    "seat": player.seat,
                    "alive": player.alive,
                    "ghost_vote": player.ghost_vote,
                }
                for player in game.players
            ],
        }

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                raise LLMError(f"LLM 没有返回 JSON：{raw}")
            return json.loads(match.group(0))

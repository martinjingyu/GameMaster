from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(path: Path | str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


@dataclass(frozen=True)
class GameMasterConfig:
    default_channel_id: str = "local-table"
    default_script: str = "tb"
    min_players_to_start: int = 5
    max_players: int = 15
    auto_create_game: bool = True
    auto_start_game: bool = True
    auto_resolve_night: bool = True
    auto_advance_day: bool = False
    lobby_countdown_seconds: int = 30
    night_action_seconds: int = 90
    day_discussion_seconds: int = 300
    tick_seconds: int = 1

    @classmethod
    def from_env(cls) -> "GameMasterConfig":
        return cls(
            default_channel_id=os.getenv("GAMEMASTER_DEFAULT_CHANNEL_ID", "local-table"),
            default_script=os.getenv("GAMEMASTER_DEFAULT_SCRIPT", "tb"),
            min_players_to_start=env_int("GAMEMASTER_MIN_PLAYERS_TO_START", 5),
            max_players=env_int("GAMEMASTER_MAX_PLAYERS", 15),
            auto_create_game=env_bool("GAMEMASTER_AUTO_CREATE_GAME", True),
            auto_start_game=env_bool("GAMEMASTER_AUTO_START_GAME", True),
            auto_resolve_night=env_bool("GAMEMASTER_AUTO_RESOLVE_NIGHT", True),
            auto_advance_day=env_bool("GAMEMASTER_AUTO_ADVANCE_DAY", False),
            lobby_countdown_seconds=env_int("GAMEMASTER_LOBBY_COUNTDOWN_SECONDS", 30),
            night_action_seconds=env_int("GAMEMASTER_NIGHT_ACTION_SECONDS", 90),
            day_discussion_seconds=env_int("GAMEMASTER_DAY_DISCUSSION_SECONDS", 300),
            tick_seconds=env_int("GAMEMASTER_TICK_SECONDS", 1),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "default_channel_id": self.default_channel_id,
            "default_script": self.default_script,
            "min_players_to_start": self.min_players_to_start,
            "max_players": self.max_players,
            "auto_create_game": self.auto_create_game,
            "auto_start_game": self.auto_start_game,
            "auto_resolve_night": self.auto_resolve_night,
            "auto_advance_day": self.auto_advance_day,
            "lobby_countdown_seconds": self.lobby_countdown_seconds,
            "night_action_seconds": self.night_action_seconds,
            "day_discussion_seconds": self.day_discussion_seconds,
            "tick_seconds": self.tick_seconds,
        }

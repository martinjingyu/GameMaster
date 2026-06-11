from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.agent import GameMasterAgent, GatewayEvent
from gamemaster.clocktower.engine import GameStore
from gamemaster.config import GameMasterConfig
from gamemaster.pipeline import AgentPipeline


class AgentPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = GameMasterAgent(GameStore())
        self.pipeline = AgentPipeline(
            self.agent,
            GameMasterConfig(
                default_channel_id="pipe-table",
                min_players_to_start=5,
                lobby_countdown_seconds=0,
                night_action_seconds=999,
                auto_resolve_night=False,
            ),
        )
        self.agent.pipeline = self.pipeline

    def send_player(self, user_id: str, text: str) -> None:
        self.agent.handle_event(
            GatewayEvent(
                channel_id="pipe-table",
                user_id=user_id,
                display_name=user_id,
                text=text,
            )
        )

    def test_tick_creates_game_when_channel_is_empty(self) -> None:
        messages = self.pipeline.tick("pipe-table")

        self.assertTrue(messages)
        self.assertIsNotNone(self.agent.store.current_for_channel("pipe-table"))

    def test_tick_starts_game_after_lobby_countdown(self) -> None:
        self.pipeline.tick("pipe-table")
        for index in range(1, 6):
            self.send_player(f"u{index}", f"/join P{index}")

        self.pipeline.tick("pipe-table")
        messages = self.pipeline.tick("pipe-table")

        game = self.agent.store.current_for_channel("pipe-table")
        assert game is not None
        self.assertEqual(game.phase, "night")
        self.assertTrue(any(message.visibility == "private" for message in messages))
        self.assertEqual(game.pipeline_state.get("stage"), "night")

    def test_pipeline_action_extends_active_deadline(self) -> None:
        self.pipeline.tick("pipe-table")
        for index in range(1, 6):
            self.send_player(f"u{index}", f"/join P{index}")
        self.pipeline.tick("pipe-table")
        game = self.agent.store.current_for_channel("pipe-table")
        assert game is not None
        before = game.pipeline_state["lobby_start_deadline"]

        message = self.pipeline.apply_action(game, "extend", {"seconds": 30})

        after = game.pipeline_state["lobby_start_deadline"]
        self.assertNotEqual(before, after)
        self.assertIn("extended", message.text)

    def test_storyteller_pipeline_command_sets_override(self) -> None:
        self.pipeline.tick("pipe-table")

        messages = self.agent.handle_event(
            GatewayEvent(
                channel_id="pipe-table",
                user_id="__storyteller__",
                display_name="GameMaster",
                text="/pipeline set_override night_action_seconds 12",
                metadata={"storyteller": True},
            )
        )

        game = self.agent.store.current_for_channel("pipe-table")
        assert game is not None
        self.assertEqual(game.pipeline_state["overrides"]["night_action_seconds"], 12)
        self.assertIn("override", messages[0].text)


if __name__ == "__main__":
    unittest.main()

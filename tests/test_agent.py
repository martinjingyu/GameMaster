from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.agent import GameMasterAgent, GatewayEvent
from gamemaster.clocktower.engine import GameStore


class GameMasterAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = GameMasterAgent(GameStore())

    def send(self, user_id: str, text: str, name: str | None = None, private: bool = False):
        return self.agent.handle_event(
            GatewayEvent(
                channel_id="table-1",
                user_id=user_id,
                display_name=name or user_id,
                text=text,
                is_private=private,
            )
        )

    def storyteller(self, text: str):
        return self.send("__storyteller__", text, "GameMaster")

    def setup_five_player_game(self) -> None:
        self.storyteller("/new tb")
        for idx in range(1, 6):
            self.send(f"u{idx}", f"/join P{idx}")

    def test_create_join_and_start_game(self) -> None:
        self.setup_five_player_game()

        messages = self.storyteller("/start fixed-seed")

        self.assertEqual(messages[0].visibility, "public")
        private_messages = [message for message in messages if message.visibility == "private"]
        self.assertEqual(len(private_messages), 5)
        self.assertTrue(any("你的身份是" in message.text for message in private_messages))

    def test_private_free_text_records_night_action(self) -> None:
        self.setup_five_player_game()
        self.storyteller("/start fixed-seed")

        messages = self.send("u2", "今晚选择 3 号", private=True)

        self.assertEqual(messages[0].visibility, "private")
        self.assertIn("行动已记录", messages[0].text)

    def test_nomination_vote_close_executes(self) -> None:
        self.setup_five_player_game()
        self.storyteller("/start fixed-seed")
        self.storyteller("/day")
        self.send("u1", "/nominate 2")
        self.send("u1", "/vote yes")
        self.send("u2", "/vote yes")
        self.send("u3", "/vote yes")

        messages = self.send("u1", "/closevote")

        self.assertIn("投票关闭", messages[0].text)
        self.assertIn("被处决", messages[0].text)

    def test_player_cannot_run_storyteller_control_command(self) -> None:
        self.setup_five_player_game()

        messages = self.send("u1", "/start fixed-seed")

        self.assertEqual(messages[0].visibility, "private")
        self.assertIn("说书人 agent", messages[0].text)

    def test_memory_records_inbound_and_outbound_events(self) -> None:
        self.setup_five_player_game()

        game = self.agent.store.current_for_channel("table-1")

        self.assertIsNotNone(game)
        assert game is not None
        event_types = [event.event_type for event in game.memory_events]
        self.assertIn("inbound_message", event_types)
        self.assertIn("outbound_message", event_types)
        self.assertTrue(all(event.event_id for event in game.memory_events))

    def test_memory_context_filters_private_events_by_player(self) -> None:
        self.setup_five_player_game()
        self.storyteller("/start fixed-seed")
        self.send("u2", "private action from u2", private=True)

        game = self.agent.store.current_for_channel("table-1")
        assert game is not None
        u1_context = self.agent.memory.prompt_context(game, perspective_user_id="u1")
        u2_context = self.agent.memory.prompt_context(game, perspective_user_id="u2")
        u1_text = "\n".join(event["text"] for event in u1_context["recent_events"])
        u2_text = "\n".join(event["text"] for event in u2_context["recent_events"])

        self.assertNotIn("private action from u2", u1_text)
        self.assertIn("private action from u2", u2_text)

    def test_memory_compacts_long_event_logs(self) -> None:
        self.setup_five_player_game()
        game = self.agent.store.current_for_channel("table-1")
        assert game is not None

        for index in range(150):
            self.agent.memory.record(
                game,
                "vote",
                actor_id="u1",
                actor_name="P1",
                visibility="public",
                text=f"vote event {index}",
                tags=["important"],
            )

        self.assertTrue(game.memory_summary)
        self.assertLessEqual(len(game.memory_events), self.agent.memory.MAX_EVENTS)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.flow import GameFlow, GameFlowConfig
from gamemaster.core.events import GameEvent
from gamemaster.core.players import RoleAssignment
from gamemaster.core.recap import build_llm_recap, build_recap
from gamemaster.core.script import trouble_brewing_minimal
from gamemaster.core.types import Alignment, EventType, Visibility


class FakeLLMClient:
    configured = True

    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[dict[str, str]] = []

    def complete(self, messages: list[dict[str, str]], response_format: str = "text") -> str:
        self.messages = messages
        return self.response


class CoreRecapTest(unittest.TestCase):
    def make_flow(self) -> GameFlow:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=3), game_id="recap")
        for index in range(1, 4):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.send_setup_info()
        flow.enter_first_night()
        return flow

    def test_storyteller_recap_uses_full_event_stream(self) -> None:
        flow = self.make_flow()

        recap = build_recap(flow, "__storyteller__").to_dict()

        self.assertIn("Storyteller recap", recap["title"])
        self.assertIn("u2 is imp", recap["text"])

    def test_player_recap_uses_visible_event_stream(self) -> None:
        flow = self.make_flow()

        recap = build_recap(flow, "u1").to_dict()

        self.assertIn("Player recap", recap["title"])
        self.assertIn("You are the Empath", recap["text"])
        self.assertNotIn("u2 is imp", recap["text"])

    def test_llm_recap_receives_full_postgame_context_and_chat(self) -> None:
        flow = self.make_flow()
        flow.grimoire.append_event(
            GameEvent.create(
                EventType.PUBLIC_MESSAGE,
                flow.grimoire.phase,
                flow.grimoire.day,
                actor_id="u1",
                visibility=Visibility.POSTGAME,
                public_text="[public] P1: P2 is evil because the vote timing was strange.",
                payload={
                    "player_id": "u1",
                    "display_name": "P1",
                    "text": "P2 is evil because the vote timing was strange.",
                    "scope": "public",
                },
                tags=("chat", "public", "free_text"),
            )
        )
        client = FakeLLMClient("最佳玩家：P1\n吐槽：P2 的伪装有点薄。")

        recap = build_llm_recap(flow, "u1", client=client).to_dict()

        prompt = client.messages[-1]["content"]
        self.assertEqual(recap["mode"], "llm")
        self.assertIn("最佳玩家", recap["text"])
        self.assertIn('"role_id": "imp"', prompt)
        self.assertIn("P2 is evil because the vote timing was strange.", prompt)


if __name__ == "__main__":
    unittest.main()

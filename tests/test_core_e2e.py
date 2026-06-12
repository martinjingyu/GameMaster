from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.agent import GatewayEvent
from gamemaster.config import GameMasterConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.types import Alignment, GamePhase
from gamemaster.core_agent import CoreAgent
from gamemaster.core_pipeline import CorePipeline


class CoreEndToEndTest(unittest.TestCase):
    def make_event(
        self,
        user_id: str,
        text: str,
        *,
        private: bool = False,
    ) -> GatewayEvent:
        return GatewayEvent(
            channel_id="e2e",
            user_id=user_id,
            display_name=user_id.upper(),
            text=text,
            is_private=private,
        )

    def test_agent_can_run_night_to_day_to_execution_flow(self) -> None:
        pipeline = CorePipeline(GameMasterConfig(default_channel_id="e2e"))
        agent = CoreAgent(pipeline)
        flow = pipeline.create_game("e2e", game_id="e2e-game")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u2", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.send_setup_info()
        flow.enter_first_night()

        poison_messages = agent.handle_event(self.make_event("u1", "我毒 3 号", private=True))
        resolve_messages = agent.handle_event(self.make_event("__storyteller__", "/resolve"))
        nominate_messages = agent.handle_event(self.make_event("u3", "我提名 P1"))
        vote_messages = [
            agent.handle_event(self.make_event(f"u{index}", "赞成"))
            for index in range(1, 4)
        ]
        close_messages = agent.handle_event(self.make_event("u3", "/closevote"))

        self.assertIn("Action received", poison_messages[0].text)
        self.assertEqual(flow.grimoire.night_actions, {})
        self.assertTrue(any("Day 1 begins" in message.text for message in resolve_messages))
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)
        self.assertIn("nominated", nominate_messages[0].text)
        self.assertTrue(any("voted yes" in messages[0].text for messages in vote_messages))
        self.assertTrue(any("executed" in message.text for message in close_messages))
        self.assertFalse(flow.grimoire.assignments["u1"].is_alive)


if __name__ == "__main__":
    unittest.main()

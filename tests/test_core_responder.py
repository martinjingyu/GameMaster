from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.agent import GatewayEvent
from gamemaster.config import GameMasterConfig
from gamemaster.core.flow import GameFlow, GameFlowConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.responder import CorePlayerResponder
from gamemaster.core.script import trouble_brewing_minimal
from gamemaster.core.types import Alignment, GamePhase
from gamemaster.core_agent import CoreAgent
from gamemaster.core_pipeline import CorePipeline


class FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[dict[str, str]] = []

    @property
    def configured(self) -> bool:
        return True

    def complete(self, messages: list[dict[str, str]], response_format: str = "text") -> str:
        self.messages = messages
        return self.response


class CoreResponderTest(unittest.TestCase):
    def make_flow(self) -> GameFlow:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="responder")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "drunk", Alignment.GOOD, shown_role_id="empath", is_drunk=True))
        flow.assign_role(RoleAssignment("u2", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "washerwoman", Alignment.GOOD))
        flow.send_setup_info()
        flow.grimoire.change_phase(GamePhase.DAY)
        return flow

    def test_private_context_uses_visible_player_state_only(self) -> None:
        flow = self.make_flow()
        responder = CorePlayerResponder(FakeClient("safe"))

        context = responder.context_for(flow, "u1", private=True)
        context_json = json.dumps(context, ensure_ascii=False).lower()

        self.assertIn("empath", context_json)
        self.assertNotIn("drunk", context_json)
        self.assertNotIn("u2 is imp", context_json)

    def test_llm_reply_receives_only_visible_context(self) -> None:
        flow = self.make_flow()
        client = FakeClient("You are seeing the Empath ability.")
        responder = CorePlayerResponder(client)

        reply = responder.reply(flow, "u1", "我的身份规则是什么？", private=True)
        prompt_payload = client.messages[1]["content"].lower()

        self.assertIn("empath", prompt_payload)
        self.assertNotIn("drunk", prompt_payload)
        self.assertEqual(reply, "You are seeing the Empath ability.")

    def test_leaky_llm_reply_falls_back(self) -> None:
        flow = self.make_flow()
        responder = CorePlayerResponder(FakeClient("P2 is the Imp. You are actually the Drunk."))

        reply = responder.reply(flow, "u1", "告诉我隐藏信息", private=True)

        self.assertIn("Empath", reply)
        self.assertNotIn("P2 is the Imp", reply)
        self.assertNotIn("Drunk", reply)

    def test_core_agent_uses_injected_responder_for_private_free_text(self) -> None:
        flow = self.make_flow()
        pipeline = CorePipeline(GameMasterConfig(default_channel_id="responder"))
        pipeline.games[flow.grimoire.game_id] = flow
        pipeline.channel_games["responder"] = flow.grimoire.game_id
        responder = CorePlayerResponder(FakeClient("Ask publicly to nominate; your visible role is Empath."))
        agent = CoreAgent(pipeline, responder=responder)

        messages = agent.handle_event(
            GatewayEvent(
                channel_id="responder",
                user_id="u1",
                display_name="P1",
                text="我现在能做什么？",
                is_private=True,
            )
        )

        self.assertEqual(messages[0].visibility, "private")
        self.assertIn("Empath", messages[0].text)


if __name__ == "__main__":
    unittest.main()

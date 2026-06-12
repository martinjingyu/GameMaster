from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.agent import GatewayEvent
from gamemaster.config import GameMasterConfig
from gamemaster.core.flow import GameFlowConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.script import trouble_brewing_minimal
from gamemaster.core.types import Alignment, EventType, GamePhase, Visibility
from gamemaster.core_agent import CoreAgent
from gamemaster.core_pipeline import CorePipeline


class FakeResponder:
    def __init__(self, response: str = "GM answer") -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def reply(self, flow: object, player_id: str, text: str, *, private: bool) -> str:
        self.calls.append(
            {
                "flow": flow,
                "player_id": player_id,
                "text": text,
                "private": private,
            }
        )
        return self.response


class CoreAgentParserTest(unittest.TestCase):
    def make_agent(self) -> tuple[CoreAgent, object]:
        pipeline = CorePipeline(GameMasterConfig(default_channel_id="parser"))
        flow = pipeline.create_game("parser", game_id="parser-game")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        return CoreAgent(pipeline), flow

    def event(
        self,
        user_id: str,
        text: str,
        *,
        private: bool = True,
    ) -> GatewayEvent:
        return GatewayEvent(
            channel_id="parser",
            user_id=user_id,
            display_name=user_id.upper(),
            text=text,
            is_private=private,
        )

    def test_private_night_text_resolves_seat_and_display_name_targets(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()

        messages = agent.handle_event(self.event("u1", "今晚查 3 号 和 P5"))

        self.assertEqual(messages[0].visibility, "private")
        self.assertIn("Action received", messages[0].text)
        self.assertEqual(flow.grimoire.night_actions["u1"]["targets"], ["u3", "u5"])

    def test_private_night_text_resolves_named_target(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()

        messages = agent.handle_event(self.event("u1", "我毒 P4"))

        self.assertIn("Action received: P4", messages[0].text)
        self.assertEqual(flow.grimoire.night_actions["u1"]["targets"], ["u4"])

    def test_gm_command_answers_during_night_without_submitting_action(self) -> None:
        pipeline = CorePipeline(GameMasterConfig(default_channel_id="parser"))
        flow = pipeline.create_game("parser", game_id="parser-game")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()
        responder = FakeResponder("毒药师每晚选择一名玩家使其中毒。")
        agent = CoreAgent(pipeline, responder=responder)

        messages = agent.handle_event(self.event("u1", "/gm 毒药师规则是什么？"))

        self.assertEqual(messages[0].visibility, "private")
        self.assertIn("毒药师", messages[0].text)
        self.assertNotIn("u1", flow.grimoire.night_actions)
        self.assertEqual(responder.calls[-1]["text"], "毒药师规则是什么？")
        self.assertTrue(responder.calls[-1]["private"])

    def test_ask_alias_can_answer_publicly(self) -> None:
        agent, flow = self.make_agent()
        responder = FakeResponder("Public GM answer")
        agent.responder = responder
        flow.grimoire.change_phase(GamePhase.DAY)

        messages = agent.handle_event(self.event("u2", "/ask nomination rules?", private=False))

        self.assertEqual(messages[0].visibility, "public")
        self.assertEqual(messages[0].text, "Public GM answer")
        self.assertFalse(responder.calls[-1]["private"])

    def test_public_day_nomination_can_use_natural_text(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_day()

        messages = agent.handle_event(self.event("u1", "我提名 4 号", private=False))

        self.assertEqual(flow.grimoire.phase, GamePhase.VOTING)
        self.assertIn("nominated", messages[0].text)

    def test_public_day_vote_can_use_natural_text(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_day()
        flow.nominate("u1", "u4")

        messages = agent.handle_event(self.event("u2", "我赞成", private=False))

        self.assertIn("voted yes", messages[0].text)

    def test_public_day_nomination_and_vote_accept_real_chinese_text(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_day()

        nomination = agent.handle_event(self.event("u1", "我提名 4 号", private=False))
        vote = agent.handle_event(self.event("u2", "赞成", private=False))

        self.assertEqual(flow.grimoire.phase, GamePhase.VOTING)
        self.assertIn("nominated", nomination[0].text)
        self.assertIn("voted yes", vote[0].text)

    def test_resolve_during_day_does_not_advance_day_counter(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()
        flow.enter_day()

        messages = agent.handle_event(self.event("__storyteller__", "/resolve", private=False))

        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)
        self.assertEqual(flow.grimoire.day, 1)
        self.assertIn("only run at night", messages[0].text)

    def test_enter_day_is_idempotent_while_already_day(self) -> None:
        _, flow = self.make_agent()
        flow.enter_first_night()
        flow.enter_day()
        flow.enter_day()
        flow.enter_day()

        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)
        self.assertEqual(flow.grimoire.day, 1)

    def test_agent_records_player_chat_for_postgame_analysis(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_day()

        agent.handle_event(self.event("u2", "I think P4 is suspicious.", private=False))

        chat_events = [
            event
            for event in flow.grimoire.events
            if event.event_type == EventType.PUBLIC_MESSAGE and "chat" in event.tags
        ]
        self.assertEqual(chat_events[-1].visibility, Visibility.POSTGAME)
        self.assertEqual(chat_events[-1].payload["text"], "I think P4 is suspicious.")

    def test_private_rules_question_uses_player_visible_role_only(self) -> None:
        agent, flow = self.make_agent()
        flow.assign_role(RoleAssignment("u1", "drunk", Alignment.GOOD, shown_role_id="empath", is_drunk=True))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.grimoire.change_phase(GamePhase.DAY)

        messages = agent.handle_event(self.event("u1", "我的身份规则是什么？"))

        self.assertIn("Empath", messages[0].text)
        self.assertNotIn("Drunk", messages[0].text)


if __name__ == "__main__":
    unittest.main()

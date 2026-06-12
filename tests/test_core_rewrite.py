from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.decision_engine import StorytellerDecisionEngine
from gamemaster.core.decisions import DecisionProposal, DecisionRequest
from gamemaster.core.flow import GameFlow, GameFlowConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.script import trouble_brewing_minimal
from gamemaster.core.types import Alignment, GamePhase


class FixedBadProvider:
    def propose(self, request: DecisionRequest) -> DecisionProposal:
        return DecisionProposal(
            decision_id=request.decision_id,
            selected_output=99,
            message_to_player="bad output",
            reason="This should be rejected.",
            confidence=1.0,
        )


class FixedGoodProvider:
    def propose(self, request: DecisionRequest) -> DecisionProposal:
        return DecisionProposal(
            decision_id=request.decision_id,
            selected_output=2,
            message_to_player="You learn that 2 of your alive neighbors are evil.",
            reason="A legal false information choice.",
            confidence=0.9,
        )


class EchoAllowedProvider:
    def propose(self, request: DecisionRequest) -> DecisionProposal:
        selected = request.allowed_outputs[0]
        return DecisionProposal(
            decision_id=request.decision_id,
            selected_output=selected,
            reason="Select first legal output.",
            confidence=1.0,
        )


class CoreRewriteTest(unittest.TestCase):
    def make_flow(self, provider=None) -> GameFlow:
        return GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=3),
            decision_engine=StorytellerDecisionEngine(provider=provider),
            game_id="core-test",
        )

    def seat_three(self, flow: GameFlow) -> None:
        flow.join("u1", "Alice")
        flow.join("u2", "Bob")
        flow.join("u3", "Chen")
        flow.start_setup()

    def test_grimoire_filters_role_assignments_from_players(self) -> None:
        flow = self.make_flow()
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "imp", Alignment.EVIL))

        u1_events = flow.grimoire.visible_events_for("u1")
        storyteller_events = flow.grimoire.visible_events_for("__storyteller__")

        self.assertFalse(any("imp" in event.text for event in u1_events))
        self.assertTrue(any("imp" in event.text for event in storyteller_events))

    def test_trouble_brewing_script_has_full_role_set(self) -> None:
        script = trouble_brewing_minimal()

        self.assertEqual(
            set(script.roles),
            {
                "washerwoman",
                "librarian",
                "investigator",
                "chef",
                "empath",
                "fortune_teller",
                "undertaker",
                "slayer",
                "soldier",
                "monk",
                "ravenkeeper",
                "virgin",
                "mayor",
                "drunk",
                "saint",
                "recluse",
                "butler",
                "poisoner",
                "spy",
                "scarlet_woman",
                "baron",
                "imp",
            },
        )

    def test_setup_info_respects_visibility(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="setup-info")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(
            RoleAssignment("u1", "drunk", Alignment.GOOD, shown_role_id="empath", is_drunk=True)
        )
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.grimoire.pipeline_state["demon_bluffs"] = ["slayer", "soldier", "mayor"]

        flow.send_setup_info()

        drunk_events = flow.grimoire.visible_events_for("u1")
        good_events = flow.grimoire.visible_events_for("u2")
        minion_events = flow.grimoire.visible_events_for("u4")
        demon_events = flow.grimoire.visible_events_for("u5")
        self.assertTrue(any("Empath" in event.text for event in drunk_events))
        self.assertFalse(any("Drunk" in event.text for event in drunk_events))
        self.assertFalse(any(event.payload.get("kind") == "evil_team_info" for event in good_events))
        self.assertTrue(any(event.payload.get("kind") == "evil_team_info" for event in minion_events))
        self.assertTrue(any(event.payload.get("kind") == "demon_bluffs" for event in demon_events))

    def test_sober_empath_gets_deterministic_information(self) -> None:
        flow = self.make_flow()
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("1", results[0].outbound_messages[0].text)

    def test_librarian_learns_outsider_pair(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="librarian-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "librarian", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "saint", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("saint", results[0].outbound_messages[0].text)

    def test_investigator_learns_minion_pair(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="investigator-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "investigator", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("poisoner", results[0].outbound_messages[0].text)

    def test_drunk_empath_uses_automatic_storyteller_decision(self) -> None:
        flow = self.make_flow(FixedGoodProvider())
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "drunk", Alignment.GOOD, shown_role_id="empath", is_drunk=True))
        flow.assign_role(RoleAssignment("u2", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].outbound_messages[0].recipient_id, "u1")
        self.assertIn("2", results[0].outbound_messages[0].text)
        storyteller_events = flow.grimoire.visible_events_for("__storyteller__")
        self.assertTrue(any(event.event_type == "decision_applied" for event in storyteller_events))

    def test_invalid_storyteller_decision_falls_back(self) -> None:
        flow = self.make_flow(FixedBadProvider())
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "drunk", Alignment.GOOD, shown_role_id="empath", is_drunk=True))
        flow.assign_role(RoleAssignment("u2", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "washerwoman", Alignment.GOOD))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertNotIn("99", results[0].outbound_messages[0].text)
        self.assertTrue(any(event.payload.get("selected_output") != 99 for event in results[0].events))

    def test_chef_counts_evil_neighbor_pairs(self) -> None:
        flow = self.make_flow()
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "imp", Alignment.EVIL))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("1", results[0].outbound_messages[0].text)

    def test_recluse_can_register_as_evil_for_empath(self) -> None:
        flow = self.make_flow()
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "recluse", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.grimoire.pipeline_state["registration_overrides"] = {
            "u2": {"alignment": "evil"}
        }
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("1", results[0].outbound_messages[0].text)

    def test_recluse_can_register_as_demon_for_fortune_teller(self) -> None:
        flow = self.make_flow()
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "recluse", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "imp", Alignment.EVIL))
        flow.grimoire.pipeline_state["registration_overrides"] = {
            "u2": {"role_type": "demon"}
        }
        flow.enter_first_night()
        flow.grimoire.submit_night_action("u1", "fortune_teller", ("u2", "u1"))

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("yes", results[0].outbound_messages[0].text)

    def test_poisoner_applies_poison_and_fortune_teller_uses_decision(self) -> None:
        flow = self.make_flow(FixedGoodProvider())
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "imp", Alignment.EVIL))
        flow.enter_first_night()
        flow.grimoire.submit_night_action("u2", "poisoner", ("u1",))
        flow.grimoire.submit_night_action("u1", "fortune_teller", ("u2", "u3"))

        poison_results = flow.resolve_role_night("u2")
        ft_results = flow.resolve_role_night("u1")

        self.assertTrue(poison_results[0].ok)
        self.assertTrue(flow.grimoire.assignments["u1"].is_poisoned)
        self.assertTrue(ft_results[0].ok)
        self.assertTrue(any(event.event_type == "decision_applied" for event in flow.grimoire.visible_events_for("__storyteller__")))

    def test_imp_kills_selected_target(self) -> None:
        flow = self.make_flow()
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "imp", Alignment.EVIL))
        flow.enter_first_night()
        flow.grimoire.submit_night_action("u3", "imp", ("u1",))

        results = flow.resolve_role_night("u3")

        self.assertTrue(results[0].ok)
        self.assertFalse(flow.grimoire.assignments["u1"].is_alive)
        self.assertEqual(results[0].outbound_messages[0].visibility.value, "public")

    def test_monk_protects_target_from_imp(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="monk-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "monk", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.grimoire.change_phase(GamePhase.NIGHT)
        flow.grimoire.submit_night_action("u1", "monk", ("u2",))
        flow.grimoire.submit_night_action("u5", "imp", ("u2",))

        flow.resolve_current_night()

        self.assertTrue(flow.grimoire.assignments["u2"].is_alive)
        storyteller_events = flow.grimoire.visible_events_for("__storyteller__")
        self.assertTrue(
            any(event.payload.get("prevented_by") == "monk" for event in storyteller_events)
        )

    def test_soldier_is_safe_from_imp(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="soldier-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "soldier", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.grimoire.change_phase(GamePhase.NIGHT)
        flow.grimoire.submit_night_action("u5", "imp", ("u1",))

        result = flow.resolve_role_night("u5")[0]

        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u1"].is_alive)
        storyteller_events = flow.grimoire.visible_events_for("__storyteller__")
        self.assertTrue(
            any(event.payload.get("prevented_by") == "soldier" for event in storyteller_events)
        )

    def test_undertaker_learns_executed_role(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="undertaker-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "undertaker", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_day()
        flow.nominate("u1", "u2")
        flow.vote("u1", True)
        flow.vote("u2", True)
        flow.vote("u3", True)
        flow.close_vote()
        flow.grimoire.change_phase(GamePhase.NIGHT)

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertIn("chef", results[0].outbound_messages[0].text)

    def test_ravenkeeper_learns_role_after_dying_at_night(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="ravenkeeper-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "ravenkeeper", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.grimoire.change_phase(GamePhase.NIGHT)
        flow.grimoire.submit_night_action("u5", "imp", ("u1",))
        flow.grimoire.submit_night_action("u1", "ravenkeeper", ("u2",))

        results = flow.resolve_current_night()

        self.assertFalse(flow.grimoire.assignments["u1"].is_alive)
        info_results = [
            result for result in results
            if result.outbound_messages and result.outbound_messages[0].recipient_id == "u1"
        ]
        self.assertTrue(info_results)
        self.assertIn("chef", info_results[0].outbound_messages[0].text)

    def test_spy_gets_grimoire_information(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=5), game_id="spy-test")
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "saint", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "spy", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_first_night()

        results = flow.resolve_role_night("u4")

        self.assertTrue(results[0].ok)
        self.assertIn("u5: imp", results[0].outbound_messages[0].text)

    def test_washerwoman_setup_selection_sends_private_info(self) -> None:
        flow = self.make_flow(EchoAllowedProvider())
        self.seat_three(flow)
        flow.assign_role(RoleAssignment("u1", "washerwoman", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "imp", Alignment.EVIL))
        flow.enter_first_night()

        results = flow.resolve_role_night("u1")

        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].outbound_messages[0].recipient_id, "u1")
        self.assertIn("Chef", results[0].outbound_messages[0].text.title())


if __name__ == "__main__":
    unittest.main()

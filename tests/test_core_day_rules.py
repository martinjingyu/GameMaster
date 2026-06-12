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


class CoreDayRulesTest(unittest.TestCase):
    def make_flow(self) -> GameFlow:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=5),
            game_id="day-rules",
        )
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "saint", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.enter_day()
        return flow

    def make_scarlet_flow(self) -> GameFlow:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=6),
            game_id="scarlet-rules",
        )
        for index in range(1, 7):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "saint", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u6", "scarlet_woman", Alignment.EVIL))
        flow.enter_day()
        return flow

    def test_vote_below_threshold_does_not_execute(self) -> None:
        flow = self.make_flow()

        nomination = flow.nominate("u1", "u4")
        flow.vote("u1", True)
        flow.vote("u2", True)
        result = flow.close_vote()

        self.assertTrue(nomination.ok)
        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u4"].is_alive)
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)
        self.assertFalse(flow.grimoire.pipeline_state.get("winner"))

    def test_vote_at_threshold_executes_target(self) -> None:
        flow = self.make_flow()

        flow.nominate("u1", "u4")
        flow.vote("u1", True)
        flow.vote("u2", True)
        flow.vote("u3", True)
        result = flow.close_vote()

        self.assertTrue(result.ok)
        self.assertFalse(flow.grimoire.assignments["u4"].is_alive)
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)

    def test_executing_demon_wins_for_good(self) -> None:
        flow = self.make_flow()

        flow.nominate("u1", "u5")
        flow.vote("u1", True)
        flow.vote("u2", True)
        flow.vote("u3", True)
        result = flow.close_vote()

        self.assertTrue(result.ok)
        self.assertFalse(flow.grimoire.assignments["u5"].is_alive)
        self.assertEqual(flow.grimoire.pipeline_state["winner"], "good")
        self.assertEqual(flow.grimoire.phase, GamePhase.GAME_OVER)

    def test_scarlet_woman_becomes_demon_before_good_win(self) -> None:
        flow = self.make_scarlet_flow()

        flow.nominate("u1", "u5")
        flow.vote("u1", True)
        flow.vote("u2", True)
        flow.vote("u3", True)
        flow.vote("u4", True)
        result = flow.close_vote()

        self.assertTrue(result.ok)
        self.assertFalse(flow.grimoire.assignments["u5"].is_alive)
        self.assertEqual(flow.grimoire.assignments["u6"].role_id, "imp")
        self.assertIn("became_demon", flow.grimoire.assignments["u6"].reminders)
        self.assertFalse(flow.grimoire.pipeline_state.get("winner"))
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)
        storyteller_events = flow.grimoire.visible_events_for("__storyteller__")
        self.assertTrue(
            any(
                event.payload.get("reason") == "scarlet_woman_transfer"
                for event in storyteller_events
            )
        )

    def test_executing_saint_wins_for_evil(self) -> None:
        flow = self.make_flow()

        flow.nominate("u1", "u3")
        flow.vote("u1", True)
        flow.vote("u2", True)
        flow.vote("u3", True)
        result = flow.close_vote()

        self.assertTrue(result.ok)
        self.assertFalse(flow.grimoire.assignments["u3"].is_alive)
        self.assertEqual(flow.grimoire.pipeline_state["winner"], "evil")
        self.assertEqual(flow.grimoire.pipeline_state["win_reason"], "saint was executed")
        self.assertEqual(flow.grimoire.phase, GamePhase.GAME_OVER)

    def test_slayer_shot_kills_demon_and_good_wins(self) -> None:
        flow = self.make_flow()
        flow.assign_role(RoleAssignment("u1", "slayer", Alignment.GOOD))

        result = flow.slayer_shoot("u1", "u5")

        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u1"].ability_used)
        self.assertFalse(flow.grimoire.assignments["u5"].is_alive)
        self.assertEqual(flow.grimoire.pipeline_state["winner"], "good")
        self.assertEqual(flow.grimoire.phase, GamePhase.GAME_OVER)

    def test_drunk_slayer_shot_does_not_kill(self) -> None:
        flow = self.make_flow()
        flow.assign_role(
            RoleAssignment("u1", "drunk", Alignment.GOOD, shown_role_id="slayer", is_drunk=True)
        )

        result = flow.slayer_shoot("u1", "u5")

        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u1"].ability_used)
        self.assertTrue(flow.grimoire.assignments["u5"].is_alive)
        self.assertFalse(flow.grimoire.pipeline_state.get("winner"))

    def test_slayer_killing_demon_can_trigger_scarlet_woman_transfer(self) -> None:
        flow = self.make_scarlet_flow()
        flow.assign_role(RoleAssignment("u1", "slayer", Alignment.GOOD))

        result = flow.slayer_shoot("u1", "u5")

        self.assertTrue(result.ok)
        self.assertFalse(flow.grimoire.assignments["u5"].is_alive)
        self.assertEqual(flow.grimoire.assignments["u6"].role_id, "imp")
        self.assertFalse(flow.grimoire.pipeline_state.get("winner"))
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)

    def test_mayor_wins_when_day_ends_with_three_alive_and_no_execution(self) -> None:
        flow = self.make_flow()
        flow.assign_role(RoleAssignment("u1", "mayor", Alignment.GOOD))
        flow.grimoire.assignments["u2"].is_alive = False
        flow.grimoire.assignments["u3"].is_alive = False

        result = flow.end_day()

        self.assertTrue(result.ok)
        self.assertEqual(flow.grimoire.pipeline_state["winner"], "good")
        self.assertEqual(
            flow.grimoire.pipeline_state["win_reason"],
            "mayor ended the day with three living players",
        )
        self.assertEqual(flow.grimoire.phase, GamePhase.GAME_OVER)

    def test_virgin_executes_first_townsfolk_nominator(self) -> None:
        flow = self.make_flow()
        flow.assign_role(RoleAssignment("u1", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "virgin", Alignment.GOOD))

        result = flow.nominate("u1", "u3")

        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u3"].ability_used)
        self.assertFalse(flow.grimoire.assignments["u1"].is_alive)
        self.assertEqual(flow.grimoire.pipeline_state["day_state"]["executed_player_id"], "u1")
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)

    def test_virgin_does_not_execute_non_townsfolk_nominator(self) -> None:
        flow = self.make_flow()
        flow.assign_role(RoleAssignment("u3", "virgin", Alignment.GOOD))

        result = flow.nominate("u5", "u3")

        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u3"].ability_used)
        self.assertTrue(flow.grimoire.assignments["u5"].is_alive)
        self.assertEqual(flow.grimoire.phase, GamePhase.VOTING)

    def test_dead_player_spends_one_ghost_vote(self) -> None:
        flow = self.make_flow()
        flow.grimoire.assignments["u2"].is_alive = False

        flow.nominate("u1", "u4")
        first_vote = flow.vote("u2", True)
        second_vote = flow.vote("u2", True)

        self.assertTrue(first_vote.ok)
        self.assertFalse(flow.grimoire.assignments["u2"].ghost_vote_available)
        self.assertFalse(second_vote.ok)

    def test_butler_can_only_vote_yes_with_master(self) -> None:
        flow = self.make_flow()
        flow.assign_role(RoleAssignment("u1", "butler", Alignment.GOOD))
        flow.grimoire.assignments["u1"].reminders.append("butler_master:u2")

        flow.nominate("u3", "u4")
        rejected = flow.vote("u1", True)
        master_vote = flow.vote("u2", True)
        accepted = flow.vote("u1", True)

        self.assertFalse(rejected.ok)
        self.assertEqual(rejected.error, "butler can only vote yes if their master is voting yes")
        self.assertTrue(master_vote.ok)
        self.assertTrue(accepted.ok)

    def test_player_can_only_nominate_once_per_day(self) -> None:
        flow = self.make_flow()

        flow.nominate("u1", "u4")
        flow.vote("u1", False)
        flow.close_vote()
        second_nomination = flow.nominate("u1", "u5")

        self.assertFalse(second_nomination.ok)
        self.assertEqual(second_nomination.error, "nominator has already nominated today")


class MayorRedirectProvider:
    def propose(self, request: DecisionRequest) -> DecisionProposal:
        return DecisionProposal(
            decision_id=request.decision_id,
            selected_output="u2",
            reason="Redirect the Mayor death to u2.",
            confidence=1.0,
        )


class CoreMayorNightRulesTest(unittest.TestCase):
    def test_mayor_death_can_redirect_to_another_player(self) -> None:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=5),
            decision_engine=StorytellerDecisionEngine(provider=MayorRedirectProvider()),
            game_id="mayor-night",
        )
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "mayor", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "empath", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        flow.grimoire.change_phase(GamePhase.NIGHT)
        flow.grimoire.submit_night_action("u5", "imp", ("u1",))

        result = flow.resolve_role_night("u5")[0]

        self.assertTrue(result.ok)
        self.assertTrue(flow.grimoire.assignments["u1"].is_alive)
        self.assertFalse(flow.grimoire.assignments["u2"].is_alive)
        self.assertFalse(flow.grimoire.pipeline_state.get("winner"))
        storyteller_events = flow.grimoire.visible_events_for("__storyteller__")
        self.assertTrue(
            any(event.payload.get("redirect_target_id") == "u2" for event in storyteller_events)
        )


if __name__ == "__main__":
    unittest.main()

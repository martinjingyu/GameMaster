from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.allocator import RoleAllocator
from gamemaster.core.decision_engine import StorytellerDecisionEngine
from gamemaster.core.decisions import DecisionProposal, DecisionRequest
from gamemaster.core.flow import GameFlow, GameFlowConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.roles import (
    Drunk,
    Imp,
    PlaceholderMinion,
    PlaceholderOutsider,
    PlaceholderTownsfolk,
    Poisoner,
)
from gamemaster.core.script import Script, trouble_brewing_minimal
from gamemaster.core.types import Alignment, RoleType


EXPECTED_DISTRIBUTIONS = {
    5: (3, 0, 1, 1),
    6: (3, 1, 1, 1),
    7: (5, 0, 1, 1),
    8: (5, 1, 1, 1),
    9: (5, 2, 1, 1),
    10: (7, 0, 2, 1),
    11: (7, 1, 2, 1),
    12: (7, 2, 2, 1),
    13: (9, 0, 3, 1),
    14: (9, 1, 3, 1),
    15: (9, 2, 3, 1),
}


class FalseProvider:
    def propose(self, request: DecisionRequest) -> DecisionProposal:
        return DecisionProposal(
            decision_id=request.decision_id,
            selected_output=False,
            reason="Poisoned Fortune Teller gets false no.",
            confidence=1.0,
        )


class CoreAllocatorNightTest(unittest.TestCase):
    def custom_script(
        self,
        *,
        townsfolk_count: int = 11,
        outsiders: tuple[object, ...] = (Drunk(), PlaceholderOutsider("saint", "Saint")),
        minions: tuple[object, ...] = (
            Poisoner(),
            PlaceholderMinion("baron", "Baron"),
            PlaceholderMinion("scarlet_woman", "Scarlet Woman"),
        ),
    ) -> Script:
        roles = [
            *(PlaceholderTownsfolk(f"townsfolk_{index}", f"Townsfolk {index}") for index in range(townsfolk_count)),
            *outsiders,
            *minions,
            Imp(),
        ]
        return Script(
            script_id="test_script",
            name="Test Script",
            roles={role.role_id: role for role in roles},
        )

    def make_flow(self) -> GameFlow:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=5),
            decision_engine=StorytellerDecisionEngine(provider=FalseProvider()),
            game_id="allocator-night",
        )
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        return flow

    def test_allocator_assigns_five_player_distribution(self) -> None:
        flow = self.make_flow()

        flow.allocate_roles(seed="fixed")

        counts = {RoleType.TOWNSFOLK: 0, RoleType.OUTSIDER: 0, RoleType.MINION: 0, RoleType.DEMON: 0}
        for assignment in flow.grimoire.assignments.values():
            role = flow.script.role(assignment.role_id)
            counts[role.role_type] += 1

        expected_townsfolk = 1 if "baron" in [
            assignment.role_id for assignment in flow.grimoire.assignments.values()
        ] else 3
        expected_outsiders = 2 if expected_townsfolk == 1 else 0
        self.assertEqual(counts[RoleType.TOWNSFOLK], expected_townsfolk)
        self.assertEqual(counts[RoleType.OUTSIDER], expected_outsiders)
        self.assertEqual(counts[RoleType.MINION], 1)
        self.assertEqual(counts[RoleType.DEMON], 1)
        self.assertTrue(flow.grimoire.pipeline_state["demon_bluffs"])

    def test_allocator_assigns_six_player_outsider(self) -> None:
        flow = GameFlow(trouble_brewing_minimal(), GameFlowConfig(min_players=6), game_id="six")
        for index in range(1, 7):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()

        flow.allocate_roles(seed="fixed")

        outsider_count = sum(
            1
            for assignment in flow.grimoire.assignments.values()
            if flow.script.role(assignment.role_id).role_type == RoleType.OUTSIDER
        )
        self.assertEqual(outsider_count, 1)

    def test_allocator_supports_five_to_fifteen_players(self) -> None:
        for player_count, expected in EXPECTED_DISTRIBUTIONS.items():
            with self.subTest(player_count=player_count):
                flow = GameFlow(
                    trouble_brewing_minimal(),
                    GameFlowConfig(min_players=player_count),
                    game_id=f"alloc-{player_count}",
                )
                for index in range(1, player_count + 1):
                    flow.join(f"u{index}", f"P{index}")
                flow.start_setup()

                flow.allocate_roles(seed=f"fixed-{player_count}")

                counts = {
                    RoleType.TOWNSFOLK: 0,
                    RoleType.OUTSIDER: 0,
                    RoleType.MINION: 0,
                    RoleType.DEMON: 0,
                }
                for assignment in flow.grimoire.assignments.values():
                    role = flow.script.role(assignment.role_id)
                    counts[role.role_type] += 1

                actual = (
                    counts[RoleType.TOWNSFOLK],
                    counts[RoleType.OUTSIDER],
                    counts[RoleType.MINION],
                    counts[RoleType.DEMON],
                )
                contains_baron = any(
                    assignment.role_id == "baron"
                    for assignment in flow.grimoire.assignments.values()
                )
                if contains_baron:
                    expected = (expected[0] - 2, expected[1] + 2, expected[2], expected[3])
                self.assertEqual(actual, expected)
                self.assertEqual(len(flow.grimoire.assignments), player_count)

    def test_baron_adds_two_outsiders(self) -> None:
        script = self.custom_script(
            outsiders=(Drunk(), PlaceholderOutsider("saint", "Saint")),
            minions=(PlaceholderMinion("baron", "Baron"), Poisoner()),
        )
        allocator = RoleAllocator(script)

        result = allocator.allocate(tuple(f"u{index}" for index in range(1, 11)))

        counts = {RoleType.TOWNSFOLK: 0, RoleType.OUTSIDER: 0, RoleType.MINION: 0, RoleType.DEMON: 0}
        for assignment in result.assignments:
            counts[script.role(assignment.role_id).role_type] += 1
        self.assertEqual(counts[RoleType.TOWNSFOLK], 5)
        self.assertEqual(counts[RoleType.OUTSIDER], 2)
        self.assertEqual(counts[RoleType.MINION], 2)
        self.assertEqual(counts[RoleType.DEMON], 1)
        self.assertIn("baron_added_two_outsiders", result.setup_notes)

    def test_drunk_is_shown_as_townsfolk(self) -> None:
        script = self.custom_script(
            outsiders=(Drunk(),),
            minions=(Poisoner(),),
        )
        allocator = RoleAllocator(script)

        result = allocator.allocate(tuple(f"u{index}" for index in range(1, 7)))

        drunk_assignment = next(
            assignment for assignment in result.assignments if assignment.role_id == "drunk"
        )
        self.assertTrue(drunk_assignment.is_drunk)
        self.assertIsNotNone(drunk_assignment.shown_role_id)
        self.assertEqual(script.role(drunk_assignment.visible_role_id).role_type, RoleType.TOWNSFOLK)
        self.assertNotIn(drunk_assignment.visible_role_id, {a.role_id for a in result.assignments})
        self.assertTrue(
            any(note.startswith("drunk_shown_as:") for note in result.setup_notes)
        )

    def test_night_resolver_uses_role_order(self) -> None:
        flow = self.make_flow()
        flow.assign_role(RoleAssignment("u1", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u3", "imp", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u4", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u5", "empath", Alignment.GOOD))
        flow.enter_first_night()
        flow.grimoire.submit_night_action("u2", "poisoner", ("u1",))
        flow.grimoire.submit_night_action("u1", "fortune_teller", ("u2", "u3"))

        results = flow.resolve_current_night()

        self.assertTrue(flow.grimoire.assignments["u1"].is_poisoned)
        self.assertTrue(any(result.ok for result in results))
        decision_events = [
            event for event in flow.grimoire.visible_events_for("__storyteller__")
            if event.event_type == "decision_applied"
        ]
        self.assertTrue(decision_events)


if __name__ == "__main__":
    unittest.main()

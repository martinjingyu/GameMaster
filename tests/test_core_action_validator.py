from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.flow import GameFlow, GameFlowConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.script import trouble_brewing_minimal
from gamemaster.core.types import Alignment, GamePhase


class CoreActionValidatorTest(unittest.TestCase):
    def make_flow(self) -> GameFlow:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=5),
            game_id="validator-test",
        )
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "monk", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u2", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u4", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u5", "imp", Alignment.EVIL))
        return flow

    def test_rejects_night_action_outside_night(self) -> None:
        flow = self.make_flow()
        flow.enter_day()

        result = flow.submit_night_action("u5", "imp", ("u1",))

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "night actions can only be submitted at night")

    def test_rejects_role_mismatch(self) -> None:
        flow = self.make_flow()
        flow.grimoire.change_phase(GamePhase.NIGHT)

        result = flow.submit_night_action("u5", "poisoner", ("u1",))

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "submitted role does not match visible role")

    def test_rejects_wrong_target_count(self) -> None:
        flow = self.make_flow()
        flow.grimoire.change_phase(GamePhase.NIGHT)

        result = flow.submit_night_action("u2", "fortune_teller", ("u4",))

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "fortune_teller requires 2 target(s)")

    def test_rejects_monk_self_protection(self) -> None:
        flow = self.make_flow()
        flow.grimoire.change_phase(GamePhase.NIGHT)

        result = flow.submit_night_action("u1", "monk", ("u1",))

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "monk cannot protect themself")

    def test_rejects_duplicate_submission(self) -> None:
        flow = self.make_flow()
        flow.grimoire.change_phase(GamePhase.NIGHT)

        first = flow.submit_night_action("u5", "imp", ("u1",))
        second = flow.submit_night_action("u5", "imp", ("u2",))

        self.assertTrue(first.ok)
        self.assertFalse(second.ok)
        self.assertEqual(second.error, "night action already submitted")

    def test_accepts_legal_night_action(self) -> None:
        flow = self.make_flow()
        flow.grimoire.change_phase(GamePhase.NIGHT)

        result = flow.submit_night_action("u5", "imp", ("u1",))

        self.assertTrue(result.ok)
        self.assertEqual(flow.grimoire.night_actions["u5"]["targets"], ["u1"])


if __name__ == "__main__":
    unittest.main()

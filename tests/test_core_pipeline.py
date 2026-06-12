from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.config import GameMasterConfig
from gamemaster.core.players import RoleAssignment
from gamemaster.core.types import GamePhase
from gamemaster.core.types import Alignment
from gamemaster.core_pipeline import CorePipeline


class CorePipelineTest(unittest.TestCase):
    def make_pipeline(self) -> CorePipeline:
        return CorePipeline(
            GameMasterConfig(
                default_channel_id="core-pipeline",
                min_players_to_start=5,
                lobby_countdown_seconds=0,
                night_action_seconds=0,
                day_discussion_seconds=0,
                auto_advance_day=True,
            )
        )

    def seat_five(self, pipeline: CorePipeline, channel_id: str = "core-pipeline") -> None:
        flow = pipeline.current_for_channel(channel_id)
        self.assertIsNotNone(flow)
        for index in range(1, 6):
            flow.join(f"u{index}", f"P{index}")

    def test_tick_creates_and_starts_core_game(self) -> None:
        pipeline = self.make_pipeline()

        created = pipeline.tick("core-pipeline")
        self.seat_five(pipeline)
        started = pipeline.tick("core-pipeline")

        flow = pipeline.current_for_channel("core-pipeline")
        self.assertTrue(created)
        self.assertTrue(started)
        self.assertIsNotNone(flow)
        self.assertEqual(flow.grimoire.phase, GamePhase.FIRST_NIGHT)
        self.assertEqual(flow.grimoire.pipeline_state["stage"], "night_actions")

    def test_tick_start_returns_private_setup_messages(self) -> None:
        pipeline = self.make_pipeline()

        pipeline.tick("core-pipeline")
        self.seat_five(pipeline)
        messages = pipeline.tick("core-pipeline")

        private_messages = [message for message in messages if message.visibility == "private"]
        self.assertGreaterEqual(len(private_messages), 5)
        self.assertTrue(any("You are the" in message.text for message in private_messages))

    def test_tick_resolves_night_and_enters_day(self) -> None:
        pipeline = self.make_pipeline()
        pipeline.tick("core-pipeline")
        self.seat_five(pipeline)
        pipeline.tick("core-pipeline")

        messages = pipeline.tick("core-pipeline")

        flow = pipeline.current_for_channel("core-pipeline")
        self.assertIsNotNone(flow)
        self.assertEqual(flow.grimoire.phase, GamePhase.DAY)
        self.assertEqual(flow.grimoire.day, 1)
        self.assertTrue(any("Day 1 begins" in message.text for message in messages))

    def test_runtime_action_can_pause_pipeline(self) -> None:
        pipeline = self.make_pipeline()
        pipeline.tick("core-pipeline")

        message = pipeline.apply_action("core-pipeline", "pause")
        tick = pipeline.tick("core-pipeline")

        flow = pipeline.current_for_channel("core-pipeline")
        self.assertIn("paused", message.text)
        self.assertTrue(flow.grimoire.pipeline_state["paused"])
        self.assertEqual(tick, [])

    def test_tick_sends_private_night_action_reminders(self) -> None:
        pipeline = CorePipeline(
            GameMasterConfig(
                default_channel_id="reminder",
                min_players_to_start=3,
                night_action_seconds=10,
            )
        )
        flow = pipeline.create_game("reminder")
        for index in range(1, 4):
            flow.join(f"u{index}", f"P{index}")
        flow.start_setup()
        flow.assign_role(RoleAssignment("u1", "poisoner", Alignment.EVIL))
        flow.assign_role(RoleAssignment("u2", "fortune_teller", Alignment.GOOD))
        flow.assign_role(RoleAssignment("u3", "chef", Alignment.GOOD))
        flow.enter_first_night()
        pipeline._set_deadline(flow, "night_deadline", 4)

        messages = pipeline.tick("reminder")
        second_tick = pipeline.tick("reminder")

        self.assertEqual(len(messages), 2)
        self.assertTrue(all(message.visibility == "private" for message in messages))
        self.assertEqual({message.recipient_id for message in messages}, {"u1", "u2"})
        self.assertEqual(second_tick, [])


if __name__ == "__main__":
    unittest.main()

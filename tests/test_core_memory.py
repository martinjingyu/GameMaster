from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.events import GameEvent
from gamemaster.core.flow import GameFlow, GameFlowConfig
from gamemaster.core.script import trouble_brewing_minimal
from gamemaster.core.types import EventType, Visibility


class CoreMemoryTest(unittest.TestCase):
    def test_compaction_updates_summary_without_deleting_events(self) -> None:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=1),
            game_id="memory-test",
        )
        flow.join("u1", "P1")
        for index in range(60):
            flow.grimoire.append_event(
                GameEvent.create(
                    EventType.PUBLIC_MESSAGE,
                    flow.grimoire.phase,
                    flow.grimoire.day,
                    actor_id="u1",
                    visibility=Visibility.PUBLIC,
                    public_text=f"public message {index}",
                )
            )

        result = flow.compact_memory(keep_last=10)

        self.assertEqual(result.summarized_event_count, len(flow.grimoire.events) - 10)
        self.assertEqual(result.retained_event_count, 10)
        self.assertEqual(len(flow.grimoire.events), 61)
        self.assertIn("public message 0", flow.grimoire.summary)

    def test_llm_context_keeps_recent_visible_events(self) -> None:
        flow = GameFlow(
            trouble_brewing_minimal(),
            GameFlowConfig(min_players=1),
            game_id="context-test",
        )
        flow.join("u1", "P1")
        for index in range(40):
            flow.grimoire.append_event(
                GameEvent.create(
                    EventType.PUBLIC_MESSAGE,
                    flow.grimoire.phase,
                    flow.grimoire.day,
                    actor_id="u1",
                    visibility=Visibility.PUBLIC,
                    public_text=f"visible event {index}",
                )
            )
        flow.compact_memory(keep_last=5)

        context = flow.grimoire.llm_context_for("u1")

        self.assertEqual(len(context["events"]), 30)
        self.assertIn("visible event 39", context["events"][-1]["text"])
        self.assertTrue(context["summary"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.persistence import CoreGameStore
from gamemaster.core.types import GamePhase
from gamemaster.core_pipeline import CorePipeline
from gamemaster.config import GameMasterConfig


class CorePersistenceTest(unittest.TestCase):
    def test_store_round_trips_core_game_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "core-games.json"
            store = CoreGameStore(path, min_players=5)
            pipeline = CorePipeline(
                GameMasterConfig(
                    default_channel_id="persist",
                    min_players_to_start=5,
                    lobby_countdown_seconds=0,
                ),
                store.games,
                store.channel_games,
                on_change=store.save,
            )
            pipeline.tick("persist")
            flow = pipeline.current_for_channel("persist")
            self.assertIsNotNone(flow)
            for index in range(1, 6):
                flow.join(f"u{index}", f"P{index}")
            store.save()

            reloaded = CoreGameStore(path, min_players=5)
            loaded_flow = reloaded.games["core-persist"]

            self.assertEqual(reloaded.channel_games["persist"], "core-persist")
            self.assertEqual(len(loaded_flow.grimoire.players), 5)
            self.assertEqual(loaded_flow.grimoire.phase, GamePhase.WAITING_PLAYERS)
            self.assertTrue(loaded_flow.grimoire.events)

    def test_store_writes_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "core-games.json"
            store = CoreGameStore(path, min_players=5)
            pipeline = CorePipeline(
                GameMasterConfig(default_channel_id="json-persist"),
                store.games,
                store.channel_games,
                on_change=store.save,
            )

            pipeline.tick("json-persist")

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("games", payload)
            self.assertIn("channel_games", payload)
            self.assertEqual(payload["channel_games"]["json-persist"], "core-json-persist")


if __name__ == "__main__":
    unittest.main()

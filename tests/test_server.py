from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.agent import GameMasterAgent
from gamemaster.channel import ChannelGatewayClient
from gamemaster.clocktower.engine import GameStore
from gamemaster.config import GameMasterConfig
from gamemaster.core_agent import CoreAgent
from gamemaster.core_pipeline import CorePipeline
from gamemaster.pipeline import AgentPipeline
from gamemaster.server import GameMasterHandler


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        class Handler(GameMasterHandler):
            pass

        Handler.game_store = GameStore()
        Handler.game_agent = GameMasterAgent(Handler.game_store)
        Handler.gamemaster_config = GameMasterConfig(
            default_channel_id="local-test",
            lobby_countdown_seconds=0,
            night_action_seconds=0,
        )
        Handler.agent_pipeline = AgentPipeline(Handler.game_agent, Handler.gamemaster_config)
        Handler.channel_gateway = ChannelGatewayClient()
        Handler.core_games = {}
        Handler.core_pipeline = CorePipeline(Handler.gamemaster_config, Handler.core_games)
        Handler.core_agent = CoreAgent(Handler.core_pipeline)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def test_serves_local_test_page(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/test", timeout=5) as response:
            html = response.read().decode("utf-8")

        self.assertIn("Core Chat Test Mode", html)
        self.assertIn("/core/events", html)
        self.assertIn("Join 12", html)
        self.assertIn("loadCurrent", html)
        self.assertIn("showRecap", html)

    def test_serves_legacy_test_page(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/legacy/test", timeout=5) as response:
            html = response.read().decode("utf-8")

        self.assertIn("/gateway/events", html)

    def test_serves_core_test_page(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/core/test", timeout=5) as response:
            html = response.read().decode("utf-8")

        self.assertIn("Core Test Mode", html)
        self.assertIn("/core/games", html)
        self.assertIn("Core Tick", html)

    def test_accepts_gateway_event(self) -> None:
        payload = json.dumps(
            {
                "channel_id": "local-test",
                "user_id": "alice",
                "display_name": "Alice",
                "text": "/new tb",
                "is_private": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/gateway/events",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(body["ok"])
        self.assertEqual(body["messages"][0]["visibility"], "public")

    def test_serves_game_memory(self) -> None:
        payload = json.dumps(
            {
                "channel_id": "memory-test",
                "user_id": "__storyteller__",
                "display_name": "GameMaster",
                "text": "/new tb",
                "metadata": {"storyteller": True},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/gateway/events",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            event_body = json.loads(response.read().decode("utf-8"))
        game_id = event_body["messages"][0]["game_id"]

        with urllib.request.urlopen(f"{self.base_url}/games/{game_id}/memory", timeout=5) as response:
            memory_body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(memory_body["ok"])
        self.assertEqual(memory_body["game_id"], game_id)
        self.assertTrue(memory_body["recent_events"])

    def test_agent_tick_endpoint_creates_game(self) -> None:
        payload = json.dumps({"channel_id": "tick-test"}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/agent/tick",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(body["ok"])
        self.assertTrue(body["messages"])
        self.assertEqual(body["messages"][0]["visibility"], "public")

    def test_agent_action_endpoint_applies_runtime_action(self) -> None:
        tick_payload = json.dumps({"channel_id": "action-test"}).encode("utf-8")
        tick_request = urllib.request.Request(
            f"{self.base_url}/agent/tick",
            data=tick_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(tick_request, timeout=5):
            pass

        action_payload = json.dumps(
            {
                "channel_id": "action-test",
                "action": "set_override",
                "params": {"name": "night_action_seconds", "value": 7},
            }
        ).encode("utf-8")
        action_request = urllib.request.Request(
            f"{self.base_url}/agent/action",
            data=action_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(action_request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(body["ok"])
        self.assertIn("override", body["messages"][0]["text"])

    def test_core_game_lifecycle_endpoint(self) -> None:
        create_payload = json.dumps({"game_id": "core-http", "min_players": 5}).encode("utf-8")
        create_request = urllib.request.Request(
            f"{self.base_url}/core/games",
            data=create_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(create_request, timeout=5) as response:
            create_body = json.loads(response.read().decode("utf-8"))
        self.assertTrue(create_body["ok"])
        self.assertEqual(create_body["game"]["game_id"], "core-http")

        for index in range(1, 6):
            join_payload = json.dumps(
                {"player_id": f"u{index}", "display_name": f"P{index}"}
            ).encode("utf-8")
            join_request = urllib.request.Request(
                f"{self.base_url}/core/games/core-http/join",
                data=join_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(join_request, timeout=5):
                pass

        start_payload = json.dumps({"seed": "core-http-seed"}).encode("utf-8")
        start_request = urllib.request.Request(
            f"{self.base_url}/core/games/core-http/start",
            data=start_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(start_request, timeout=5) as response:
            start_body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(start_body["ok"])
        self.assertEqual(start_body["game"]["phase"], "first_night")
        self.assertEqual(len(start_body["game"]["players"]), 5)

        with urllib.request.urlopen(
            f"{self.base_url}/core/games/core-http/events?player_id=u1",
            timeout=5,
        ) as response:
            events_body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(events_body["ok"])
        self.assertTrue(any(event["payload"].get("kind") == "role_info" for event in events_body["events"]))

        with urllib.request.urlopen(
            f"{self.base_url}/core/games/core-http/recap?player_id=u1",
            timeout=5,
        ) as response:
            recap_body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(recap_body["ok"])
        self.assertIn("Player recap", recap_body["recap"]["title"])
        self.assertIn("You are the", recap_body["recap"]["text"])

    def test_core_night_action_endpoint_validates_actions(self) -> None:
        create_payload = json.dumps({"game_id": "core-validate", "min_players": 5}).encode("utf-8")
        create_request = urllib.request.Request(
            f"{self.base_url}/core/games",
            data=create_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(create_request, timeout=5):
            pass
        for index in range(1, 6):
            join_payload = json.dumps(
                {"player_id": f"u{index}", "display_name": f"P{index}"}
            ).encode("utf-8")
            join_request = urllib.request.Request(
                f"{self.base_url}/core/games/core-validate/join",
                data=join_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(join_request, timeout=5):
                pass
        start_request = urllib.request.Request(
            f"{self.base_url}/core/games/core-validate/start",
            data=json.dumps({"seed": "fixed"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(start_request, timeout=5):
            pass

        action_payload = json.dumps(
            {"actor_id": "u1", "role_id": "imp", "targets": ["u2"]}
        ).encode("utf-8")
        action_request = urllib.request.Request(
            f"{self.base_url}/core/games/core-validate/night-action",
            data=action_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(action_request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertFalse(body["ok"])
        self.assertTrue(body["error"])

    def test_core_agent_tick_endpoint_creates_game(self) -> None:
        payload = json.dumps({"channel_id": "core-agent"}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/core/agent/tick",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(body["ok"])
        self.assertTrue(body["messages"])
        self.assertEqual(body["game"]["phase"], "waiting_players")

    def test_core_games_list_returns_current_channel_game(self) -> None:
        payload = json.dumps({"channel_id": "core-list"}).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/core/agent/tick",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5):
            pass

        with urllib.request.urlopen(
            f"{self.base_url}/core/games?channel_id=core-list",
            timeout=5,
        ) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(body["ok"])
        self.assertEqual(body["current_game_id"], "core-core-list")
        self.assertTrue(any(game["game_id"] == "core-core-list" for game in body["games"]))

    def test_core_agent_action_endpoint_pauses_pipeline(self) -> None:
        tick_payload = json.dumps({"channel_id": "core-action"}).encode("utf-8")
        tick_request = urllib.request.Request(
            f"{self.base_url}/core/agent/tick",
            data=tick_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(tick_request, timeout=5):
            pass

        action_payload = json.dumps(
            {"channel_id": "core-action", "action": "pause", "params": {}}
        ).encode("utf-8")
        action_request = urllib.request.Request(
            f"{self.base_url}/core/agent/action",
            data=action_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(action_request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertTrue(body["ok"])
        self.assertIn("paused", body["messages"][0]["text"])

    def test_core_events_endpoint_handles_join_start_and_role(self) -> None:
        def post_event(payload: dict) -> dict:
            request = urllib.request.Request(
                f"{self.base_url}/core/events",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))

        post_event(
            {
                "channel_id": "core-events",
                "user_id": "__storyteller__",
                "display_name": "GameMaster",
                "text": "/new core-events-game",
                "metadata": {"storyteller": True},
            }
        )
        for index in range(1, 6):
            post_event(
                {
                    "channel_id": "core-events",
                    "user_id": f"u{index}",
                    "display_name": f"P{index}",
                    "text": f"/join P{index}",
                }
            )
        start_body = post_event(
            {
                "channel_id": "core-events",
                "user_id": "__storyteller__",
                "display_name": "GameMaster",
                "text": "/start fixed",
                "metadata": {"storyteller": True},
            }
        )
        role_body = post_event(
            {
                "channel_id": "core-events",
                "user_id": "u1",
                "display_name": "P1",
                "text": "/role",
                "is_private": True,
            }
        )

        self.assertTrue(start_body["ok"])
        self.assertTrue(any(message["visibility"] == "private" for message in start_body["messages"]))
        self.assertTrue(role_body["ok"])
        self.assertEqual(role_body["messages"][0]["visibility"], "private")
        self.assertIn("You are the", role_body["messages"][0]["text"])


if __name__ == "__main__":
    unittest.main()

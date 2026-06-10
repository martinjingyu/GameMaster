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
from gamemaster.server import GameMasterHandler


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        class Handler(GameMasterHandler):
            pass

        Handler.game_store = GameStore()
        Handler.game_agent = GameMasterAgent(Handler.game_store)
        Handler.channel_gateway = ChannelGatewayClient()
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

        self.assertIn("本地微信模拟器", html)
        self.assertIn("/gateway/events", html)

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


if __name__ == "__main__":
    unittest.main()

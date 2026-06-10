from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent import GameMasterAgent, GatewayEvent
from .channel import ChannelGatewayClient
from .config import load_env_file
from .clocktower.engine import GameStore
from .clocktower.scripts import SCRIPTS
from .local_web import TEST_CLIENT_HTML


def serve(host: str = "127.0.0.1", port: int = 8787, data_path: Path | None = None) -> None:
    load_env_file()
    store = GameStore(data_path)
    agent = GameMasterAgent(store)
    gateway = ChannelGatewayClient.from_env()

    class Handler(GameMasterHandler):
        game_store = store
        game_agent = agent
        channel_gateway = gateway

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"GameMaster listening on http://{host}:{port}")
    print("POST channel events to /gateway/events")
    server.serve_forever()


class GameMasterHandler(BaseHTTPRequestHandler):
    game_store: GameStore
    game_agent: GameMasterAgent
    channel_gateway: ChannelGatewayClient

    server_version = "GameMaster/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json({"ok": True, "llm": self.game_agent.llm.status()})
            return
        if path in ("/", "/test", "/test-mode"):
            self._send_html(TEST_CLIENT_HTML)
            return
        if path == "/scripts":
            self._send_json(
                {
                    "scripts": [
                        {
                            "script_id": script.script_id,
                            "name": script.name,
                            "aliases": list(script.aliases),
                        }
                        for script in SCRIPTS.values()
                    ]
                }
            )
            return
        if path.startswith("/games/"):
            game_path = path.removeprefix("/games/").strip("/")
            memory_only = game_path.endswith("/memory")
            game_id = game_path.removesuffix("/memory").strip("/")
            try:
                game = self.game_store.get(game_id)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.NOT_FOUND)
                return
            if memory_only:
                self._send_json(
                    {
                        "ok": True,
                        "game_id": game.game_id,
                        "memory_summary": game.memory_summary,
                        "recent_events": [
                            event.to_dict() for event in game.memory_events[-50:]
                        ],
                    }
                )
                return
            self._send_json({"ok": True, "game": game.to_dict()})
            return
        self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/gateway/events", "/events"):
            self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            event = GatewayEvent.from_dict(payload)
            messages = self.game_agent.handle_event(event)
            send_error = None
            try:
                self.channel_gateway.send(messages)
            except RuntimeError as exc:
                send_error = str(exc)
            self._send_json(
                {
                    "ok": send_error is None,
                    "messages": [message.to_dict() for message in messages],
                    "gateway_error": send_error,
                },
                status=HTTPStatus.ACCEPTED if send_error is None else HTTPStatus.BAD_GATEWAY,
            )
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

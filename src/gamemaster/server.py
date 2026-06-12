from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .agent import GameMasterAgent, GatewayEvent
from .channel import ChannelGatewayClient
from .config import GameMasterConfig, load_env_file
from .clocktower.engine import GameStore
from .clocktower.scripts import SCRIPTS
from .core_agent import CoreAgent
from .core.decision_engine import StorytellerDecisionEngine
from .core.flow import GameFlow, GameFlowConfig
from .core.llm_provider import LLMDecisionProvider
from .core.persistence import CoreGameStore
from .core.recap import build_llm_recap, build_recap
from .core.script import trouble_brewing_minimal
from .core_pipeline import CorePipeline
from .local_web import CORE_CHAT_CLIENT_HTML, CORE_TEST_CLIENT_HTML, TEST_CLIENT_HTML
from .pipeline import AgentPipeline


def serve(host: str = "127.0.0.1", port: int = 8787, data_path: Path | None = None) -> None:
    load_env_file()
    config = GameMasterConfig.from_env()
    store = GameStore(data_path)
    agent = GameMasterAgent(store)
    pipeline = AgentPipeline(agent, config)
    agent.pipeline = pipeline
    core_store_runtime = CoreGameStore(_core_data_path(data_path), min_players=config.min_players_to_start)
    core_game_map = core_store_runtime.games
    core_pipeline_runtime = CorePipeline(
        config,
        core_game_map,
        core_store_runtime.channel_games,
        on_change=core_store_runtime.save,
    )
    core_agent_runtime = CoreAgent(core_pipeline_runtime)
    gateway = ChannelGatewayClient.from_env()

    class Handler(GameMasterHandler):
        gamemaster_config = config
        game_store = store
        game_agent = agent
        agent_pipeline = pipeline
        core_games = core_game_map
        core_store = core_store_runtime
        core_pipeline = core_pipeline_runtime
        core_agent = core_agent_runtime
        channel_gateway = gateway

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"GameMaster listening on http://{host}:{port}")
    print("POST channel events to /gateway/events")
    server.serve_forever()


def _core_data_path(data_path: Path | None) -> Path | None:
    if not data_path:
        return None
    suffix = data_path.suffix or ".json"
    return data_path.with_name(f"{data_path.stem}.core{suffix}")


class GameMasterHandler(BaseHTTPRequestHandler):
    game_store: GameStore
    game_agent: GameMasterAgent
    agent_pipeline: AgentPipeline
    gamemaster_config: GameMasterConfig
    channel_gateway: ChannelGatewayClient
    core_games: dict[str, GameFlow] = {}
    core_store: CoreGameStore | None = None
    core_pipeline: CorePipeline | None = None
    core_agent: CoreAgent | None = None

    server_version = "GameMaster/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "llm": self.game_agent.llm.status(),
                    "config": self.gamemaster_config.to_dict(),
                }
            )
            return
        if path == "/agent/config":
            self._send_json({"ok": True, "config": self.gamemaster_config.to_dict()})
            return
        if path == "/core/games":
            self._handle_core_games_list(parse_qs(urlparse(self.path).query))
            return
        if path.startswith("/core/games/"):
            self._handle_core_get(path, parse_qs(urlparse(self.path).query))
            return
        if path in ("/core/test", "/core/test-mode"):
            self._send_html(CORE_TEST_CLIENT_HTML)
            return
        if path in ("/", "/test", "/test-mode"):
            self._send_html(CORE_CHAT_CLIENT_HTML)
            return
        if path in ("/legacy/test", "/legacy/test-mode"):
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

    def _handle_core_games_list(self, query: dict[str, list[str]]) -> None:
        channel_id = (query.get("channel_id") or [None])[0]
        current_game_id = None
        if channel_id and self.core_pipeline:
            flow = self.core_pipeline.current_for_channel(channel_id)
            current_game_id = flow.grimoire.game_id if flow else None
        self._send_json(
            {
                "ok": True,
                "current_game_id": current_game_id,
                "games": [
                    self._core_game_to_dict(flow)
                    for flow in self.core_games.values()
                ],
            }
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/core/events":
            self._handle_core_events_post()
            return
        if path in ("/core/agent/tick", "/core/agent/action"):
            self._handle_core_agent_post(path)
            return
        if path == "/core/games" or path.startswith("/core/games/"):
            self._handle_core_post(path)
            return
        if path == "/agent/tick":
            try:
                payload = self._read_json()
                channel_id = payload.get("channel_id") or self.gamemaster_config.default_channel_id
                messages = self.agent_pipeline.tick(str(channel_id))
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
            return
        if path == "/agent/action":
            try:
                payload = self._read_json()
                channel_id = str(payload.get("channel_id") or self.gamemaster_config.default_channel_id)
                game = self.game_store.current_for_channel(channel_id)
                if not game:
                    self._send_json(
                        {"ok": False, "error": "no active game for channel"},
                        status=HTTPStatus.NOT_FOUND,
                    )
                    return
                message = self.agent_pipeline.apply_action(
                    game,
                    str(payload.get("action") or ""),
                    dict(payload.get("params") or {}),
                    actor_id=str(payload.get("actor_id") or "__storyteller__"),
                )
                self._send_json({"ok": True, "messages": [message.to_dict()]})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
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

    def _handle_core_get(self, path: str, query: dict[str, list[str]]) -> None:
        game_path = path.removeprefix("/core/games/").strip("/")
        events_only = game_path.endswith("/events")
        recap_only = game_path.endswith("/recap")
        game_id = game_path.removesuffix("/events").removesuffix("/recap").strip("/")
        flow = self.core_games.get(game_id)
        if not flow:
            self._send_json({"ok": False, "error": "core game not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if events_only:
            player_id = (query.get("player_id") or ["__storyteller__"])[0]
            events = flow.grimoire.visible_events_for(player_id)
            self._send_json(
                {
                    "ok": True,
                    "game_id": flow.grimoire.game_id,
                    "player_id": player_id,
                    "events": [event.__dict__ for event in events],
                }
            )
            return
        if recap_only:
            player_id = (query.get("player_id") or ["__storyteller__"])[0]
            if player_id != "__storyteller__" and player_id not in flow.grimoire.players:
                self._send_json({"ok": False, "error": "unknown recap viewer"}, status=HTTPStatus.NOT_FOUND)
                return
            mode = (query.get("mode") or ["structured"])[0].lower()
            recap = build_llm_recap(flow, player_id) if mode in {"llm", "ai", "postgame"} else build_recap(flow, player_id)
            self._send_json({"ok": True, "recap": recap.to_dict()})
            return
        self._send_json({"ok": True, "game": self._core_game_to_dict(flow)})

    def _handle_core_post(self, path: str) -> None:
        try:
            payload = self._read_json()
            if path == "/core/games":
                game_id = str(payload.get("game_id") or "")
                flow = GameFlow(
                    trouble_brewing_minimal(),
                    GameFlowConfig(min_players=int(payload.get("min_players") or 5)),
                    decision_engine=StorytellerDecisionEngine(provider=LLMDecisionProvider()),
                    game_id=game_id or None,
                )
                self.core_games[flow.grimoire.game_id] = flow
                self._save_core()
                self._send_json({"ok": True, "game": self._core_game_to_dict(flow)}, status=HTTPStatus.CREATED)
                return

            parts = path.removeprefix("/core/games/").strip("/").split("/")
            if len(parts) != 2:
                self._send_json({"ok": False, "error": "invalid core endpoint"}, status=HTTPStatus.NOT_FOUND)
                return
            game_id, action = parts
            flow = self.core_games.get(game_id)
            if not flow:
                self._send_json({"ok": False, "error": "core game not found"}, status=HTTPStatus.NOT_FOUND)
                return

            if action == "join":
                flow.join(str(payload["player_id"]), str(payload["display_name"]))
                self._save_core()
                self._send_json({"ok": True, "game": self._core_game_to_dict(flow)})
                return
            if action == "start":
                flow.start_setup()
                flow.allocate_roles(seed=str(payload.get("seed") or "") or None)
                flow.enter_first_night()
                self._save_core()
                self._send_json({"ok": True, "game": self._core_game_to_dict(flow)})
                return
            if action == "night-action":
                result = flow.submit_night_action(
                    str(payload["actor_id"]),
                    str(payload["role_id"]),
                    tuple(str(target) for target in payload.get("targets", [])),
                )
                self._save_core()
                self._send_json({"ok": result.ok, "error": result.error, "game": self._core_game_to_dict(flow)})
                return
            if action == "resolve-night":
                results = flow.resolve_current_night()
                self._save_core()
                self._send_json(
                    {
                        "ok": True,
                        "results": [
                            {
                                "ok": result.ok,
                                "error": result.error,
                                "messages": [
                                    {
                                        "visibility": message.visibility.value,
                                        "text": message.text,
                                        "recipient_id": message.recipient_id,
                                    }
                                    for message in result.outbound_messages
                                ],
                            }
                            for result in results
                        ],
                        "game": self._core_game_to_dict(flow),
                    }
                )
                return
            if action == "compact-memory":
                result = flow.compact_memory(keep_last=int(payload.get("keep_last") or 50))
                self._save_core()
                self._send_json({"ok": True, "result": result.__dict__})
                return
            self._send_json({"ok": False, "error": "unknown core action"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_core_agent_post(self, path: str) -> None:
        try:
            if self.core_pipeline is None:
                self.core_pipeline = CorePipeline(
                    self.gamemaster_config,
                    self.core_games,
                    self.core_store.channel_games if self.core_store else None,
                    on_change=self._save_core,
                )
            payload = self._read_json()
            channel_id = str(payload.get("channel_id") or self.gamemaster_config.default_channel_id)
            if path == "/core/agent/tick":
                messages = self.core_pipeline.tick(channel_id)
                self._send_json(
                    {
                        "ok": True,
                        "messages": [message.to_dict() for message in messages],
                        "game": self._core_game_to_dict(self.core_pipeline.current_for_channel(channel_id))
                        if self.core_pipeline.current_for_channel(channel_id)
                        else None,
                    },
                    status=HTTPStatus.ACCEPTED,
                )
                return

            message = self.core_pipeline.apply_action(
                channel_id,
                str(payload.get("action") or ""),
                dict(payload.get("params") or {}),
                actor_id=str(payload.get("actor_id") or "__storyteller__"),
            )
            self._send_json({"ok": True, "messages": [message.to_dict()]})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_core_events_post(self) -> None:
        try:
            if self.core_pipeline is None:
                self.core_pipeline = CorePipeline(
                    self.gamemaster_config,
                    self.core_games,
                    self.core_store.channel_games if self.core_store else None,
                    on_change=self._save_core,
                )
            if self.core_agent is None:
                self.core_agent = CoreAgent(self.core_pipeline)
            event = GatewayEvent.from_dict(self._read_json())
            messages = self.core_agent.handle_event(event)
            self._save_core()
            self._send_json({"ok": True, "messages": [message.to_dict() for message in messages]})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    @staticmethod
    def _core_game_to_dict(flow: GameFlow) -> dict[str, Any]:
        grimoire = flow.grimoire
        return {
            "game_id": grimoire.game_id,
            "script_id": grimoire.script_id,
            "phase": grimoire.phase.value,
            "day": grimoire.day,
            "winner": grimoire.pipeline_state.get("winner"),
            "win_reason": grimoire.pipeline_state.get("win_reason"),
            "players": [
                {
                    "player_id": player_id,
                    "display_name": player.display_name,
                    "seat": grimoire.seat_of(player_id),
                    "alive": grimoire.assignments.get(player_id).is_alive
                    if player_id in grimoire.assignments
                    else True,
                }
                for player_id, player in grimoire.players.items()
            ],
            "event_count": len(grimoire.events),
            "summary": grimoire.summary,
        }

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _save_core(self) -> None:
        if self.core_store:
            self.core_store.save()

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

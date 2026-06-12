from __future__ import annotations

import secrets
import random
from dataclasses import dataclass

from .actions import ActionResult, GameAction
from .action_validator import ActionValidator
from .allocator import RoleAllocator
from .decision_engine import StorytellerDecisionEngine
from .decisions import DecisionRequest
from .effects import KillEffect, NoOpEffect
from .events import GameEvent
from .executor import ActionExecutor
from .grimoire import Grimoire
from .memory import MemoryCompactionResult, MemoryCompactor
from .players import Player, RoleAssignment
from .rules import RulesEngine, WinResult
from .script import Script
from .types import ActionType, Alignment, EventType, GamePhase, RoleType, Visibility


@dataclass(frozen=True)
class GameFlowConfig:
    min_players: int = 5
    auto_apply_decisions: bool = True


class GameFlow:
    def __init__(
        self,
        script: Script,
        config: GameFlowConfig | None = None,
        decision_engine: StorytellerDecisionEngine | None = None,
        executor: ActionExecutor | None = None,
        game_id: str | None = None,
    ) -> None:
        self.script = script
        self.config = config or GameFlowConfig()
        self.grimoire = Grimoire(
            game_id=game_id or secrets.token_hex(4),
            script_id=script.script_id,
        )
        self.decision_engine = decision_engine or StorytellerDecisionEngine()
        self.executor = executor or ActionExecutor()
        self.rules_engine = RulesEngine(script, self.decision_engine)
        self.action_validator = ActionValidator(script)
        self.memory_compactor = MemoryCompactor()

    def join(self, player_id: str, display_name: str) -> None:
        self.grimoire.add_player(Player(player_id=player_id, display_name=display_name))

    def mark_ready(self, player_id: str) -> None:
        self.grimoire.players[player_id].is_ready = True
        self.grimoire.append_event(
            GameEvent.create(
                EventType.PLAYER_READY,
                self.grimoire.phase,
                self.grimoire.day,
                actor_id=player_id,
                visibility=Visibility.PUBLIC,
                public_text=f"{self.grimoire.players[player_id].display_name} is ready.",
            )
        )

    def can_start(self) -> bool:
        return len(self.grimoire.players) >= self.config.min_players

    def start_setup(self) -> None:
        if not self.can_start():
            raise ValueError("not enough players to start")
        self.grimoire.change_phase(GamePhase.SETUP)

    def assign_role(self, assignment: RoleAssignment) -> None:
        self.grimoire.assign_role(assignment)

    def allocate_roles(self, seed: str | None = None) -> None:
        rng = random.Random(seed)
        allocator = RoleAllocator(self.script, rng)
        player_ids = tuple(seat.player_id for seat in self.grimoire.seats)
        result = allocator.allocate(player_ids)
        for assignment in result.assignments:
            self.grimoire.assign_role(assignment)
        self.grimoire.pipeline_state["demon_bluffs"] = list(result.demon_bluffs)
        self.grimoire.pipeline_state["setup_notes"] = list(result.setup_notes)
        self.send_setup_info()

    def send_setup_info(self) -> None:
        for player_id, assignment in self.grimoire.assignments.items():
            visible_role = self.script.role(assignment.visible_role_id)
            event = GameEvent.create(
                EventType.INFO_GIVEN,
                self.grimoire.phase,
                self.grimoire.day,
                actor_id="__storyteller__",
                visibility=Visibility.PRIVATE,
                recipients=(player_id,),
                private_text=f"You are the {visible_role.name}.",
                payload={
                    "player_id": player_id,
                    "role_id": assignment.visible_role_id,
                    "alignment": visible_role.alignment.value,
                    "kind": "role_info",
                },
                tags=("setup", "role_info"),
            )
            self.grimoire.append_event(event)

        evil_players = [
            {
                "player_id": player_id,
                "display_name": self.grimoire.players[player_id].display_name,
                "role_id": assignment.role_id,
            }
            for player_id, assignment in self.grimoire.assignments.items()
            if assignment.alignment == Alignment.EVIL
        ]
        if evil_players:
            names = ", ".join(player["display_name"] for player in evil_players)
            self.grimoire.append_event(
                GameEvent.create(
                    EventType.INFO_GIVEN,
                    self.grimoire.phase,
                    self.grimoire.day,
                    actor_id="__storyteller__",
                    visibility=Visibility.EVIL_TEAM,
                    public_text=f"Evil team: {names}.",
                    payload={"players": evil_players, "kind": "evil_team_info"},
                    tags=("setup", "evil_team"),
                )
            )

        demon_bluffs = list(self.grimoire.pipeline_state.get("demon_bluffs", []))
        if demon_bluffs:
            for player_id, assignment in self.grimoire.assignments.items():
                if self.script.role(assignment.role_id).role_type != RoleType.DEMON:
                    continue
                bluff_names = ", ".join(self.script.role(role_id).name for role_id in demon_bluffs)
                self.grimoire.append_event(
                    GameEvent.create(
                        EventType.INFO_GIVEN,
                        self.grimoire.phase,
                        self.grimoire.day,
                        actor_id="__storyteller__",
                        visibility=Visibility.PRIVATE,
                        recipients=(player_id,),
                        private_text=f"Your Demon bluffs are: {bluff_names}.",
                        payload={"role_ids": demon_bluffs, "kind": "demon_bluffs"},
                        tags=("setup", "demon_bluffs"),
                    )
                )

    def enter_first_night(self) -> None:
        self.grimoire.change_phase(GamePhase.FIRST_NIGHT)

    def enter_day(self) -> None:
        if self.grimoire.phase == GamePhase.DAY:
            return
        self.grimoire.day += 1
        self.grimoire.night_actions.clear()
        self.grimoire.pipeline_state.pop("day_deadline", None)
        self.grimoire.pipeline_state.pop("day_timer_expired_day", None)
        self.grimoire.pipeline_state["stage"] = "day_discussion"
        self.grimoire.pipeline_state["day_state"] = {
            "day": self.grimoire.day,
            "nominations": [],
            "active_nomination_id": None,
            "used_nominators": [],
            "used_targets": [],
            "executed_player_id": None,
        }
        self.grimoire.change_phase(GamePhase.DAY)

    def resolve_current_night(self) -> tuple[ActionResult, ...]:
        from .night import NightOrderResolver

        return NightOrderResolver(self).resolve_current_night().results

    def submit_night_action(
        self,
        actor_id: str,
        role_id: str,
        targets: tuple[str, ...],
    ) -> ActionResult:
        validation = self.action_validator.validate_night_action(
            self.grimoire,
            actor_id,
            role_id,
            targets,
        )
        if not validation.ok:
            return ActionResult(action_id="night-action-rejected", ok=False, error=validation.error)
        self.grimoire.submit_night_action(actor_id, role_id, targets)
        return ActionResult(action_id=self.grimoire.events[-1].event_id, ok=True, events=(self.grimoire.events[-1],))

    def resolve_role_night(self, player_id: str) -> tuple[ActionResult, ...]:
        assignment = self.grimoire.assignments[player_id]
        role = self.script.role(assignment.visible_role_id)
        effects = role.on_night(self.grimoire, player_id)
        results: list[ActionResult] = []
        for effect in effects:
            if isinstance(effect, DecisionRequest):
                decision = self.decision_engine.decide(effect)
                if not self.config.auto_apply_decisions:
                    raise RuntimeError("manual decision review is not supported in this build")
                results.append(self.executor.apply_decision(self.grimoire, decision))
            elif isinstance(effect, NoOpEffect):
                continue
            elif isinstance(effect, KillEffect):
                results.append(
                    self.rules_engine.kill_player(
                        self.grimoire,
                        effect.target_id,
                        source_role_id=effect.source_role_id,
                        source_player_id=effect.source_player_id,
                        cause=effect.cause,
                    )
                )
            else:
                results.append(self.executor.execute_effect(self.grimoire, effect))
        return tuple(results)

    def nominate(self, nominator_id: str, target_id: str) -> ActionResult:
        return self.rules_engine.start_nomination(self.grimoire, nominator_id, target_id)

    def vote(self, voter_id: str, yes: bool) -> ActionResult:
        return self.rules_engine.cast_vote(self.grimoire, voter_id, yes)

    def close_vote(self) -> ActionResult:
        return self.rules_engine.close_vote(self.grimoire)

    def execute(self, target_id: str) -> ActionResult:
        return self.rules_engine.execute_player(self.grimoire, target_id)

    def end_day(self) -> ActionResult:
        return self.rules_engine.end_day(self.grimoire)

    def slayer_shoot(self, slayer_id: str, target_id: str) -> ActionResult:
        return self.rules_engine.use_slayer_shot(self.grimoire, slayer_id, target_id)

    def check_win(self) -> WinResult:
        return self.rules_engine.check_win(self.grimoire)

    def compact_memory(self, keep_last: int = 50) -> MemoryCompactionResult:
        return self.memory_compactor.compact(self.grimoire, keep_last=keep_last)

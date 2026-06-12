from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from .actions import ActionResult
from .decision_engine import StorytellerDecisionEngine
from .decisions import DecisionRequest
from .events import GameEvent
from .executor import Outbound
from .grimoire import Grimoire
from .script import Script
from .types import Alignment, DecisionType, EventType, GamePhase, RoleType, Visibility


@dataclass(frozen=True)
class WinResult:
    winner: Alignment | None
    reason: str = ""


class RulesEngine:
    def __init__(
        self,
        script: Script,
        decision_engine: StorytellerDecisionEngine | None = None,
    ) -> None:
        self.script = script
        self.decision_engine = decision_engine or StorytellerDecisionEngine()

    def execution_threshold(self, grimoire: Grimoire) -> int:
        return len(grimoire.living_player_ids()) // 2 + 1

    def start_nomination(self, grimoire: Grimoire, nominator_id: str, target_id: str) -> ActionResult:
        error = self._validate_nomination(grimoire, nominator_id, target_id)
        if error:
            return ActionResult(action_id="nomination-rejected", ok=False, error=error)

        phase_event = self._change_phase(grimoire, GamePhase.VOTING)
        nomination_id = secrets.token_hex(8)
        state = self._day_state(grimoire)
        nomination = {
            "nomination_id": nomination_id,
            "day": grimoire.day,
            "nominator_id": nominator_id,
            "target_id": target_id,
            "votes": {},
            "closed": False,
            "executed": False,
            "threshold": self.execution_threshold(grimoire),
        }
        state["active_nomination_id"] = nomination_id
        state["nominations"].append(nomination)
        state["used_nominators"].append(nominator_id)
        state["used_targets"].append(target_id)

        event = GameEvent.create(
            EventType.NOMINATION_STARTED,
            grimoire.phase,
            grimoire.day,
            actor_id=nominator_id,
            visibility=Visibility.PUBLIC,
            public_text=(
                f"{grimoire.players[nominator_id].display_name} nominated "
                f"{grimoire.players[target_id].display_name}."
            ),
            payload={
                "nomination_id": nomination_id,
                "nominator_id": nominator_id,
                "target_id": target_id,
                "threshold": nomination["threshold"],
            },
            tags=("day", "nomination"),
        )
        grimoire.append_event(event)
        virgin_result = self._maybe_trigger_virgin(grimoire, nomination, nominator_id, target_id)
        if virgin_result:
            return ActionResult(
                action_id=nomination_id,
                ok=True,
                events=(phase_event, event, *virgin_result.events),
                outbound_messages=(
                    Outbound(Visibility.PUBLIC, event.public_text),
                    *virgin_result.outbound_messages,
                ),
                error=virgin_result.error,
            )
        return ActionResult(
            action_id=nomination_id,
            ok=True,
            events=(phase_event, event),
            outbound_messages=(Outbound(Visibility.PUBLIC, event.public_text),),
        )

    def cast_vote(self, grimoire: Grimoire, voter_id: str, yes: bool) -> ActionResult:
        nomination = self._active_nomination(grimoire)
        if not nomination:
            return ActionResult(action_id="vote-rejected", ok=False, error="no active nomination")
        if voter_id not in grimoire.players or voter_id not in grimoire.assignments:
            return ActionResult(action_id="vote-rejected", ok=False, error="unknown voter")

        assignment = grimoire.assignments[voter_id]
        if not assignment.is_alive and yes and not assignment.ghost_vote_available:
            return ActionResult(action_id="vote-rejected", ok=False, error="ghost vote already used")
        if yes:
            butler_error = self._validate_butler_vote(grimoire, voter_id, nomination)
            if butler_error:
                return ActionResult(action_id="vote-rejected", ok=False, error=butler_error)
        if not assignment.is_alive and yes:
            assignment.ghost_vote_available = False

        nomination["votes"][voter_id] = bool(yes)
        yes_count = self._yes_count(nomination)
        event = GameEvent.create(
            EventType.VOTE_CAST,
            grimoire.phase,
            grimoire.day,
            actor_id=voter_id,
            visibility=Visibility.PUBLIC,
            public_text=(
                f"{grimoire.players[voter_id].display_name} voted "
                f"{'yes' if yes else 'no'}. Current yes votes: {yes_count}."
            ),
            payload={
                "nomination_id": nomination["nomination_id"],
                "voter_id": voter_id,
                "yes": bool(yes),
                "yes_count": yes_count,
            },
            tags=("day", "vote"),
        )
        grimoire.append_event(event)
        return ActionResult(
            action_id=event.event_id,
            ok=True,
            events=(event,),
            outbound_messages=(Outbound(Visibility.PUBLIC, event.public_text),),
        )

    def close_vote(self, grimoire: Grimoire) -> ActionResult:
        nomination = self._active_nomination(grimoire)
        if not nomination:
            return ActionResult(action_id="close-vote-rejected", ok=False, error="no active nomination")

        nomination["closed"] = True
        self._day_state(grimoire)["active_nomination_id"] = None
        yes_count = self._yes_count(nomination)
        threshold = int(nomination["threshold"])
        if yes_count < threshold:
            phase_event = self._change_phase(grimoire, GamePhase.DAY)
            event = GameEvent.create(
                EventType.EXECUTION_RESULT,
                grimoire.phase,
                grimoire.day,
                actor_id="__storyteller__",
                visibility=Visibility.PUBLIC,
                public_text=(
                    f"Vote closed. {grimoire.players[nomination['target_id']].display_name} "
                    f"received {yes_count}/{threshold} yes votes and is not executed."
                ),
                payload={
                    "nomination_id": nomination["nomination_id"],
                    "target_id": nomination["target_id"],
                    "yes_count": yes_count,
                    "threshold": threshold,
                    "executed": False,
                },
                tags=("day", "execution"),
            )
            grimoire.append_event(event)
            return ActionResult(
                action_id=event.event_id,
                ok=True,
                events=(phase_event, event),
                outbound_messages=(Outbound(Visibility.PUBLIC, event.public_text),),
            )

        return self.execute_player(
            grimoire,
            nomination["target_id"],
            cause="execution",
            nomination_id=nomination["nomination_id"],
            yes_count=yes_count,
            threshold=threshold,
        )

    def end_day(self, grimoire: Grimoire) -> ActionResult:
        if grimoire.phase != GamePhase.DAY:
            return ActionResult(action_id="end-day-rejected", ok=False, error="day can only end during day")

        win_result = self._check_mayor_win(grimoire)
        if win_result.winner:
            return ActionResult(
                action_id="mayor-win",
                ok=True,
                events=(grimoire.events[-1],),
                outbound_messages=(Outbound(Visibility.PUBLIC, "Good wins by the Mayor ability."),),
            )

        phase_event = self._change_phase(grimoire, GamePhase.NIGHT)
        return ActionResult(action_id=phase_event.event_id, ok=True, events=(phase_event,))

    def use_slayer_shot(self, grimoire: Grimoire, slayer_id: str, target_id: str) -> ActionResult:
        error = self._validate_slayer_shot(grimoire, slayer_id, target_id)
        if error:
            return ActionResult(action_id="slayer-shot-rejected", ok=False, error=error)

        slayer = grimoire.assignments[slayer_id]
        slayer.ability_used = True
        target = grimoire.assignments[target_id]
        target_is_demon = self.script.role(target.role_id).role_type == RoleType.DEMON
        shot_works = target_is_demon and not slayer.is_drunk and not slayer.is_poisoned

        shot_event = GameEvent.create(
            EventType.PLAYER_TARGETED,
            grimoire.phase,
            grimoire.day,
            actor_id=slayer_id,
            visibility=Visibility.PUBLIC,
            public_text=(
                f"{grimoire.players[slayer_id].display_name} used the Slayer ability on "
                f"{grimoire.players[target_id].display_name}."
            ),
            payload={
                "role_id": "slayer",
                "target_id": target_id,
                "worked": shot_works,
            },
            tags=("day", "slayer"),
        )
        grimoire.append_event(shot_event)
        events: tuple[GameEvent, ...] = (shot_event,)

        if not shot_works:
            return ActionResult(
                action_id=shot_event.event_id,
                ok=True,
                events=events,
                outbound_messages=(Outbound(Visibility.PUBLIC, shot_event.public_text),),
            )

        target.is_alive = False
        death_event = GameEvent.create(
            EventType.DEATH,
            grimoire.phase,
            grimoire.day,
            actor_id=slayer_id,
            visibility=Visibility.PUBLIC,
            public_text=f"{grimoire.players[target_id].display_name} died.",
            payload={"target_id": target_id, "cause": "slayer_shot"},
            tags=("death", "slayer"),
        )
        grimoire.append_event(death_event)
        pre_resolution_event_count = len(grimoire.events)
        win_result = self.check_win(grimoire)
        resolution_events = tuple(grimoire.events[pre_resolution_event_count:])
        events = (shot_event, death_event, *resolution_events)
        text = f"{shot_event.public_text} {death_event.public_text}"
        return ActionResult(
            action_id=shot_event.event_id,
            ok=True,
            events=events,
            outbound_messages=(Outbound(Visibility.PUBLIC, text),),
            error=win_result.reason if win_result.winner else None,
        )

    def kill_player(
        self,
        grimoire: Grimoire,
        target_id: str,
        *,
        source_role_id: str,
        source_player_id: str | None = None,
        cause: str = "death",
    ) -> ActionResult:
        if target_id not in grimoire.players or target_id not in grimoire.assignments:
            return ActionResult(action_id="kill-rejected", ok=False, error="unknown kill target")
        target = grimoire.assignments[target_id]
        if not target.is_alive:
            return ActionResult(action_id="kill-rejected", ok=False, error="target is already dead")

        source_role = self.script.role(source_role_id)
        redirect_event = self._maybe_redirect_mayor_death(
            grimoire,
            target_id,
            source_role=source_role,
            source_player_id=source_player_id,
            cause=cause,
        )
        if redirect_event:
            target_id = str(redirect_event.payload["redirect_target_id"])
            target = grimoire.assignments[target_id]

        if (
            source_role.role_type == RoleType.DEMON
            and target.role_id == "soldier"
            and not target.is_drunk
            and not target.is_poisoned
        ):
            event = GameEvent.create(
                EventType.PLAYER_TARGETED,
                grimoire.phase,
                grimoire.day,
                actor_id=source_player_id or "__storyteller__",
                visibility=Visibility.STORYTELLER,
                recipients=("__storyteller__",),
                private_text=f"{target_id} was safe from the Demon as the Soldier.",
                payload={
                    "target_id": target_id,
                    "source_role_id": source_role_id,
                    "cause": cause,
                    "prevented_by": "soldier",
                },
                tags=("death_prevented", "soldier"),
            )
            grimoire.append_event(event)
            return ActionResult(action_id=event.event_id, ok=True, events=(event,))

        if source_role.role_type == RoleType.DEMON and "protected_by_monk" in target.reminders:
            event = GameEvent.create(
                EventType.PLAYER_TARGETED,
                grimoire.phase,
                grimoire.day,
                actor_id=source_player_id or "__storyteller__",
                visibility=Visibility.STORYTELLER,
                recipients=("__storyteller__",),
                private_text=f"{target_id} was protected from the Demon by the Monk.",
                payload={
                    "target_id": target_id,
                    "source_role_id": source_role_id,
                    "cause": cause,
                    "prevented_by": "monk",
                },
                tags=("death_prevented", "monk"),
            )
            grimoire.append_event(event)
            return ActionResult(action_id=event.event_id, ok=True, events=(event,))

        target.is_alive = False
        event = GameEvent.create(
            EventType.DEATH,
            grimoire.phase,
            grimoire.day,
            actor_id=source_player_id or "__storyteller__",
            visibility=Visibility.PUBLIC,
            public_text=f"{grimoire.players[target_id].display_name} died.",
            payload={
                "target_id": target_id,
                "source_role_id": source_role_id,
                "cause": cause,
            },
            tags=("death",),
        )
        grimoire.append_event(event)
        pre_resolution_event_count = len(grimoire.events)
        self.check_win(grimoire)
        resolution_events = tuple(grimoire.events[pre_resolution_event_count:])
        return ActionResult(
            action_id=event.event_id,
            ok=True,
            events=(event, *resolution_events),
            outbound_messages=(Outbound(Visibility.PUBLIC, event.public_text),),
        )

    def execute_player(
        self,
        grimoire: Grimoire,
        target_id: str,
        *,
        cause: str = "execution",
        nomination_id: str | None = None,
        yes_count: int | None = None,
        threshold: int | None = None,
    ) -> ActionResult:
        if target_id not in grimoire.players or target_id not in grimoire.assignments:
            return ActionResult(action_id="execution-rejected", ok=False, error="unknown execution target")
        target_assignment = grimoire.assignments[target_id]
        if not target_assignment.is_alive:
            return ActionResult(action_id="execution-rejected", ok=False, error="target is already dead")

        phase_event = self._change_phase(grimoire, GamePhase.EXECUTION)
        target_assignment.is_alive = False
        state = self._day_state(grimoire)
        state["executed_player_id"] = target_id
        nomination = self._nomination_by_id(grimoire, nomination_id) if nomination_id else None
        if nomination:
            nomination["executed"] = True

        execution_event = GameEvent.create(
            EventType.EXECUTION_RESULT,
            grimoire.phase,
            grimoire.day,
            actor_id="__storyteller__",
            visibility=Visibility.PUBLIC,
            public_text=f"{grimoire.players[target_id].display_name} was executed and died.",
            payload={
                "nomination_id": nomination_id,
                "target_id": target_id,
                "yes_count": yes_count,
                "threshold": threshold,
                "executed": True,
                "cause": cause,
            },
            tags=("day", "execution"),
        )
        death_event = GameEvent.create(
            EventType.DEATH,
            grimoire.phase,
            grimoire.day,
            actor_id="__storyteller__",
            visibility=Visibility.PUBLIC,
            public_text=f"{grimoire.players[target_id].display_name} died.",
            payload={"target_id": target_id, "cause": cause},
            tags=("death",),
        )
        grimoire.append_event(execution_event)
        grimoire.append_event(death_event)

        pre_resolution_event_count = len(grimoire.events)
        win_result = self._check_special_execution_win(grimoire, target_id)
        if not win_result.winner:
            win_result = self.check_win(grimoire)
        resolution_events = tuple(grimoire.events[pre_resolution_event_count:])
        if not win_result.winner:
            day_event = self._change_phase(grimoire, GamePhase.DAY)
            events = (phase_event, execution_event, death_event, *resolution_events, day_event)
        else:
            events = (phase_event, execution_event, death_event, *resolution_events)

        return ActionResult(
            action_id=execution_event.event_id,
            ok=True,
            events=events,
            outbound_messages=(Outbound(Visibility.PUBLIC, execution_event.public_text),),
        )

    def check_win(self, grimoire: Grimoire) -> WinResult:
        existing = grimoire.pipeline_state.get("winner")
        if existing:
            return WinResult(Alignment(existing), str(grimoire.pipeline_state.get("win_reason", "")))

        self._maybe_transfer_scarlet_woman(grimoire)
        demon_alive = any(
            assignment.is_alive and self.script.role(assignment.role_id).role_type == RoleType.DEMON
            for assignment in grimoire.assignments.values()
        )
        if not demon_alive:
            return self._set_winner(grimoire, Alignment.GOOD, "all demons are dead")
        if len(grimoire.living_player_ids()) <= 2:
            return self._set_winner(grimoire, Alignment.EVIL, "two living players remain while a demon lives")
        return WinResult(None)

    def _check_mayor_win(self, grimoire: Grimoire) -> WinResult:
        state = self._day_state(grimoire)
        if state.get("executed_player_id"):
            return WinResult(None)
        if len(grimoire.living_player_ids()) != 3:
            return WinResult(None)
        mayor_alive = any(
            assignment.is_alive
            and assignment.role_id == "mayor"
            and not assignment.is_drunk
            and not assignment.is_poisoned
            for assignment in grimoire.assignments.values()
        )
        if not mayor_alive:
            return WinResult(None)
        return self._set_winner(grimoire, Alignment.GOOD, "mayor ended the day with three living players")

    def _validate_nomination(self, grimoire: Grimoire, nominator_id: str, target_id: str) -> str | None:
        if grimoire.phase != GamePhase.DAY:
            return "nominations can only start during day"
        if grimoire.day <= 0:
            return "day has not started"
        if self._active_nomination(grimoire):
            return "another nomination is active"
        if nominator_id not in grimoire.players or nominator_id not in grimoire.assignments:
            return "unknown nominator"
        if target_id not in grimoire.players or target_id not in grimoire.assignments:
            return "unknown nomination target"
        if not grimoire.assignments[target_id].is_alive:
            return "nomination target is already dead"

        state = self._day_state(grimoire)
        if nominator_id in state["used_nominators"]:
            return "nominator has already nominated today"
        if target_id in state["used_targets"]:
            return "target has already been nominated today"
        if state.get("executed_player_id"):
            return "an execution has already happened today"
        return None

    def _validate_slayer_shot(self, grimoire: Grimoire, slayer_id: str, target_id: str) -> str | None:
        if grimoire.phase != GamePhase.DAY:
            return "slayer can only shoot during day"
        if slayer_id not in grimoire.players or slayer_id not in grimoire.assignments:
            return "unknown slayer"
        if target_id not in grimoire.players or target_id not in grimoire.assignments:
            return "unknown slayer target"
        slayer = grimoire.assignments[slayer_id]
        if not slayer.is_alive:
            return "dead slayer cannot shoot"
        if not grimoire.assignments[target_id].is_alive:
            return "slayer target is already dead"
        if slayer.visible_role_id != "slayer":
            return "player does not have the slayer ability"
        if slayer.ability_used:
            return "slayer ability already used"
        return None

    def _validate_butler_vote(
        self,
        grimoire: Grimoire,
        voter_id: str,
        nomination: dict[str, Any],
    ) -> str | None:
        assignment = grimoire.assignments[voter_id]
        if assignment.role_id != "butler" or assignment.is_drunk or assignment.is_poisoned:
            return None
        master_id = self._butler_master(assignment.reminders)
        if not master_id:
            return None
        if nomination["votes"].get(master_id) is True:
            return None
        return "butler can only vote yes if their master is voting yes"

    @staticmethod
    def _butler_master(reminders: list[str]) -> str | None:
        for reminder in reversed(reminders):
            if reminder.startswith("butler_master:"):
                return reminder.split(":", 1)[1]
        return None

    def _maybe_trigger_virgin(
        self,
        grimoire: Grimoire,
        nomination: dict[str, Any],
        nominator_id: str,
        target_id: str,
    ) -> ActionResult | None:
        target = grimoire.assignments[target_id]
        nominator = grimoire.assignments[nominator_id]
        if target.role_id != "virgin" or target.ability_used:
            return None
        target.ability_used = True
        if target.is_drunk or target.is_poisoned:
            return None
        if self.script.role(nominator.role_id).role_type != RoleType.TOWNSFOLK:
            return None

        nomination["closed"] = True
        self._day_state(grimoire)["active_nomination_id"] = None
        trigger_event = GameEvent.create(
            EventType.PLAYER_TARGETED,
            grimoire.phase,
            grimoire.day,
            actor_id=target_id,
            visibility=Visibility.PUBLIC,
            public_text=(
                f"{grimoire.players[target_id].display_name}'s Virgin ability triggered on "
                f"{grimoire.players[nominator_id].display_name}."
            ),
            payload={
                "role_id": "virgin",
                "target_id": nominator_id,
                "nomination_id": nomination["nomination_id"],
            },
            tags=("day", "virgin"),
        )
        grimoire.append_event(trigger_event)
        execution_result = self.execute_player(
            grimoire,
            nominator_id,
            cause="virgin_ability",
            nomination_id=nomination["nomination_id"],
        )
        return ActionResult(
            action_id=trigger_event.event_id,
            ok=execution_result.ok,
            events=(trigger_event, *execution_result.events),
            outbound_messages=(
                Outbound(Visibility.PUBLIC, trigger_event.public_text),
                *execution_result.outbound_messages,
            ),
            error=execution_result.error,
        )

    def _check_special_execution_win(self, grimoire: Grimoire, target_id: str) -> WinResult:
        assignment = grimoire.assignments[target_id]
        if assignment.role_id == "saint":
            return self._set_winner(grimoire, Alignment.EVIL, "saint was executed")
        return WinResult(None)

    def _maybe_redirect_mayor_death(
        self,
        grimoire: Grimoire,
        target_id: str,
        *,
        source_role: object,
        source_player_id: str | None,
        cause: str,
    ) -> GameEvent | None:
        target = grimoire.assignments[target_id]
        if grimoire.phase not in {GamePhase.NIGHT, GamePhase.FIRST_NIGHT}:
            return None
        if source_role.role_type != RoleType.DEMON:
            return None
        if target.role_id != "mayor" or target.is_drunk or target.is_poisoned:
            return None

        candidates = tuple(
            player_id
            for player_id, assignment in grimoire.assignments.items()
            if player_id != target_id and assignment.is_alive
        )
        if not candidates:
            return None

        request = DecisionRequest.create(
            DecisionType.OPTIONAL_DEATH,
            actor_id=source_player_id,
            role_id="mayor",
            prompt="Choose whether the Mayor death redirects to another living player.",
            allowed_outputs=(*candidates, "__no_redirect__"),
            true_value=target_id,
            constraints=(
                "Only choose a living player other than the Mayor, or __no_redirect__.",
                "Do not reveal this decision publicly unless a death happens.",
            ),
            context={
                "mayor_id": target_id,
                "cause": cause,
                "candidate_ids": candidates,
            },
            fallback_output=candidates[0],
        )
        decision = self.decision_engine.decide(request)
        selected = decision.proposal.selected_output
        decision_event = GameEvent.create(
            EventType.DECISION_APPLIED,
            grimoire.phase,
            grimoire.day,
            actor_id="__storyteller__",
            visibility=Visibility.STORYTELLER,
            recipients=("__storyteller__",),
            private_text=decision.proposal.reason,
            payload={
                "decision_id": request.decision_id,
                "decision_type": request.decision_type.value,
                "selected_output": selected,
                "true_value": request.true_value,
                "validator_notes": list(decision.validator_notes),
            },
            tags=("decision", "mayor"),
        )
        grimoire.append_event(decision_event)
        if selected == "__no_redirect__":
            return None

        event = GameEvent.create(
            EventType.PLAYER_TARGETED,
            grimoire.phase,
            grimoire.day,
            actor_id=source_player_id or "__storyteller__",
            visibility=Visibility.STORYTELLER,
            recipients=("__storyteller__",),
            private_text=f"Mayor death redirected from {target_id} to {selected}.",
            payload={
                "mayor_id": target_id,
                "redirect_target_id": selected,
                "source_role_id": source_role.role_id,
                "cause": cause,
            },
            tags=("death_redirect", "mayor"),
        )
        grimoire.append_event(event)
        return event

    def _maybe_transfer_scarlet_woman(self, grimoire: Grimoire) -> bool:
        demon_alive = any(
            assignment.is_alive and self.script.role(assignment.role_id).role_type == RoleType.DEMON
            for assignment in grimoire.assignments.values()
        )
        if demon_alive:
            return False
        if len(grimoire.living_player_ids()) < 5:
            return False

        scarlet_player_id = next(
            (
                player_id
                for player_id, assignment in grimoire.assignments.items()
                if assignment.is_alive
                and assignment.role_id == "scarlet_woman"
                and assignment.alignment == Alignment.EVIL
                and not assignment.is_drunk
                and not assignment.is_poisoned
            ),
            None,
        )
        if not scarlet_player_id:
            return False

        assignment = grimoire.assignments[scarlet_player_id]
        assignment.role_id = "imp"
        assignment.shown_role_id = None
        assignment.reminders.append("became_demon")
        grimoire.pipeline_state["scarlet_woman_transfer"] = {
            "player_id": scarlet_player_id,
            "role_id": "imp",
            "day": grimoire.day,
        }
        event = GameEvent.create(
            EventType.ROLE_ASSIGNED,
            grimoire.phase,
            grimoire.day,
            actor_id="__storyteller__",
            visibility=Visibility.STORYTELLER,
            recipients=("__storyteller__",),
            private_text=f"{scarlet_player_id} became the Imp.",
            payload={
                "player_id": scarlet_player_id,
                "old_role_id": "scarlet_woman",
                "role_id": "imp",
                "reason": "scarlet_woman_transfer",
            },
            tags=("role_change", "scarlet_woman"),
        )
        grimoire.append_event(event)
        return True

    def _set_winner(self, grimoire: Grimoire, winner: Alignment, reason: str) -> WinResult:
        grimoire.pipeline_state["winner"] = winner.value
        grimoire.pipeline_state["win_reason"] = reason
        self._change_phase(grimoire, GamePhase.GAME_OVER)
        grimoire.events[-1].payload["winner"] = winner.value
        grimoire.events[-1].payload["reason"] = reason
        return WinResult(winner, reason)

    def _day_state(self, grimoire: Grimoire) -> dict[str, Any]:
        state = grimoire.pipeline_state.get("day_state")
        if not state or state.get("day") != grimoire.day:
            state = {
                "day": grimoire.day,
                "nominations": [],
                "active_nomination_id": None,
                "used_nominators": [],
                "used_targets": [],
                "executed_player_id": None,
            }
            grimoire.pipeline_state["day_state"] = state
        return state

    def _active_nomination(self, grimoire: Grimoire) -> dict[str, Any] | None:
        state = self._day_state(grimoire)
        active_id = state.get("active_nomination_id")
        if not active_id:
            return None
        return self._nomination_by_id(grimoire, str(active_id))

    def _nomination_by_id(self, grimoire: Grimoire, nomination_id: str | None) -> dict[str, Any] | None:
        if not nomination_id:
            return None
        for nomination in self._day_state(grimoire)["nominations"]:
            if nomination["nomination_id"] == nomination_id:
                return nomination
        return None

    @staticmethod
    def _yes_count(nomination: dict[str, Any]) -> int:
        return sum(1 for yes in nomination["votes"].values() if yes)

    @staticmethod
    def _change_phase(grimoire: Grimoire, phase: GamePhase) -> GameEvent:
        grimoire.change_phase(phase)
        return grimoire.events[-1]

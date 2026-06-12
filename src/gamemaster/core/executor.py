from __future__ import annotations

from dataclasses import dataclass

from .actions import ActionResult, GameAction
from .decisions import StorytellerDecision
from .effects import ApplyConditionEffect, GiveInfoEffect, KillEffect
from .events import GameEvent
from .grimoire import Grimoire
from .types import ActionType, EventType, Visibility


@dataclass(frozen=True)
class Outbound:
    visibility: Visibility
    text: str
    recipient_id: str | None = None


class ActionExecutor:
    def execute_effect(self, grimoire: Grimoire, effect: object) -> ActionResult:
        if isinstance(effect, GiveInfoEffect):
            action = GameAction.create(
                ActionType.GIVE_INFO,
                actor_id="__storyteller__",
                targets=(effect.recipient_id,),
                payload={
                    "message": effect.message,
                    "value": effect.value,
                    "role_id": effect.role_id,
                    "tags": list(effect.tags),
                },
            )
            return self.execute(grimoire, action)
        if isinstance(effect, ApplyConditionEffect):
            assignment = grimoire.assignments[effect.target_id]
            if effect.condition == "poisoned":
                assignment.is_poisoned = True
            elif effect.condition == "drunk":
                assignment.is_drunk = True
            else:
                assignment.reminders.append(effect.condition)
            event = GameEvent.create(
                EventType.CONDITION_APPLIED,
                grimoire.phase,
                grimoire.day,
                actor_id=effect.source_player_id or "__storyteller__",
                visibility=Visibility.STORYTELLER,
                recipients=("__storyteller__",),
                private_text=f"{effect.condition} applied to {effect.target_id}.",
                payload={
                    "target_id": effect.target_id,
                    "condition": effect.condition,
                    "source_role_id": effect.source_role_id,
                    "duration": effect.duration,
                    **effect.metadata,
                },
                tags=("condition",),
            )
            grimoire.append_event(event)
            return ActionResult(action_id=event.event_id, ok=True, events=(event,))
        if isinstance(effect, KillEffect):
            grimoire.assignments[effect.target_id].is_alive = False
            event = GameEvent.create(
                EventType.DEATH,
                grimoire.phase,
                grimoire.day,
                actor_id=effect.source_player_id or "__storyteller__",
                visibility=Visibility.PUBLIC,
                public_text=f"{grimoire.players[effect.target_id].display_name} died.",
                payload={
                    "target_id": effect.target_id,
                    "source_role_id": effect.source_role_id,
                    "cause": effect.cause,
                },
                tags=("death",),
            )
            grimoire.append_event(event)
            return ActionResult(
                action_id=event.event_id,
                ok=True,
                events=(event,),
                outbound_messages=(Outbound(Visibility.PUBLIC, event.public_text),),
            )
        return ActionResult(action_id="unsupported-effect", ok=False, error=f"Unsupported effect: {effect}")

    def execute(self, grimoire: Grimoire, action: GameAction) -> ActionResult:
        if action.action_type == ActionType.GIVE_INFO:
            recipient_id = action.targets[0]
            message = str(action.payload["message"])
            event = GameEvent.create(
                EventType.INFO_GIVEN,
                grimoire.phase,
                grimoire.day,
                actor_id="__storyteller__",
                visibility=Visibility.PRIVATE,
                recipients=(recipient_id,),
                private_text=message,
                payload=dict(action.payload),
                tags=("info",),
            )
            grimoire.append_event(event)
            return ActionResult(
                action_id=action.action_id,
                ok=True,
                events=(event,),
                outbound_messages=(Outbound(Visibility.PRIVATE, message, recipient_id),),
            )

        return ActionResult(
            action_id=action.action_id,
            ok=False,
            error=f"Unsupported action type: {action.action_type}",
        )

    def apply_decision(self, grimoire: Grimoire, decision: StorytellerDecision) -> ActionResult:
        request = decision.request
        proposal = decision.proposal
        decision_event = GameEvent.create(
            EventType.DECISION_APPLIED,
            grimoire.phase,
            grimoire.day,
            actor_id="__storyteller__",
            visibility=Visibility.STORYTELLER,
            recipients=("__storyteller__",),
            private_text=proposal.reason,
            payload={
                "decision_id": request.decision_id,
                "decision_type": request.decision_type.value,
                "selected_output": proposal.selected_output,
                "true_value": request.true_value,
                "validator_notes": list(decision.validator_notes),
            },
            tags=("decision",),
        )
        grimoire.append_event(decision_event)

        if request.decision_type.value == "false_information" and request.actor_id:
            message = proposal.message_to_player or self._default_info_message(
                request.role_id, proposal.selected_output
            )
            action = GameAction.create(
                ActionType.GIVE_INFO,
                actor_id="__storyteller__",
                targets=(request.actor_id,),
                payload={
                    "message": message,
                    "value": proposal.selected_output,
                    "decision_id": request.decision_id,
                    "role_id": request.role_id,
                },
                source="storyteller_decision",
            )
            result = self.execute(grimoire, action)
            return ActionResult(
                action_id=action.action_id,
                ok=result.ok,
                events=(decision_event, *result.events),
                outbound_messages=result.outbound_messages,
                error=result.error,
            )

        if request.decision_type.value == "setup_selection" and request.actor_id:
            true_candidate = request.true_value
            selected = proposal.selected_output
            if request.role_id == "washerwoman":
                true_role = grimoire.assignments[true_candidate].role_id
                message = proposal.message_to_player or (
                    f"You learn that one of {grimoire.players[true_candidate].display_name} "
                    f"and {grimoire.players[selected].display_name} is the {true_role}."
                )
            else:
                message = proposal.message_to_player or f"You receive setup information: {selected}."
            action = GameAction.create(
                ActionType.GIVE_INFO,
                actor_id="__storyteller__",
                targets=(request.actor_id,),
                payload={
                    "message": message,
                    "value": selected,
                    "true_value": true_candidate,
                    "decision_id": request.decision_id,
                    "role_id": request.role_id,
                },
                source="storyteller_decision",
            )
            result = self.execute(grimoire, action)
            return ActionResult(
                action_id=action.action_id,
                ok=result.ok,
                events=(decision_event, *result.events),
                outbound_messages=result.outbound_messages,
                error=result.error,
            )

        return ActionResult(action_id=request.decision_id, ok=True, events=(decision_event,))

    @staticmethod
    def _default_info_message(role_id: str | None, value: object) -> str:
        if role_id == "empath":
            return f"You learn that {value} of your alive neighbors are evil."
        return f"You receive this information: {value}"

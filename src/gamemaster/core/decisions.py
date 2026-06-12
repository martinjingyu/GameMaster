from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Any

from .types import DecisionType


@dataclass(frozen=True)
class DecisionRequest:
    decision_id: str
    decision_type: DecisionType
    actor_id: str | None
    role_id: str | None
    prompt: str
    allowed_outputs: tuple[Any, ...]
    true_value: Any = None
    constraints: tuple[str, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)
    fallback_output: Any = None

    @classmethod
    def create(
        cls,
        decision_type: DecisionType,
        *,
        actor_id: str | None = None,
        role_id: str | None = None,
        prompt: str,
        allowed_outputs: tuple[Any, ...],
        true_value: Any = None,
        constraints: tuple[str, ...] = (),
        context: dict[str, Any] | None = None,
        fallback_output: Any = None,
    ) -> "DecisionRequest":
        return cls(
            decision_id=secrets.token_hex(8),
            decision_type=decision_type,
            actor_id=actor_id,
            role_id=role_id,
            prompt=prompt,
            allowed_outputs=allowed_outputs,
            true_value=true_value,
            constraints=constraints,
            context=context or {},
            fallback_output=fallback_output,
        )


@dataclass(frozen=True)
class DecisionProposal:
    decision_id: str
    selected_output: Any
    message_to_player: str = ""
    public_message: str = ""
    reason: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class StorytellerDecision:
    request: DecisionRequest
    proposal: DecisionProposal
    applied: bool
    validator_notes: tuple[str, ...] = ()

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .decisions import DecisionProposal, DecisionRequest, StorytellerDecision


class DecisionProvider(Protocol):
    def propose(self, request: DecisionRequest) -> DecisionProposal: ...


class FallbackDecisionProvider:
    def propose(self, request: DecisionRequest) -> DecisionProposal:
        selected = request.fallback_output
        if selected is None and request.allowed_outputs:
            selected = request.allowed_outputs[0]
        return DecisionProposal(
            decision_id=request.decision_id,
            selected_output=selected,
            reason="Fallback storyteller decision.",
            confidence=0.0,
        )


@dataclass
class DecisionValidator:
    def validate(self, request: DecisionRequest, proposal: DecisionProposal) -> tuple[bool, tuple[str, ...]]:
        notes: list[str] = []
        if proposal.decision_id != request.decision_id:
            notes.append("proposal decision_id does not match request")
        if request.allowed_outputs and proposal.selected_output not in request.allowed_outputs:
            notes.append("selected_output is not in allowed_outputs")
        return (not notes, tuple(notes))


class StorytellerDecisionEngine:
    def __init__(
        self,
        provider: DecisionProvider | None = None,
        fallback_provider: DecisionProvider | None = None,
        validator: DecisionValidator | None = None,
    ) -> None:
        self.provider = provider or FallbackDecisionProvider()
        self.fallback_provider = fallback_provider or FallbackDecisionProvider()
        self.validator = validator or DecisionValidator()

    def decide(self, request: DecisionRequest) -> StorytellerDecision:
        proposal = self.provider.propose(request)
        ok, notes = self.validator.validate(request, proposal)
        if not ok:
            fallback = self.fallback_provider.propose(request)
            fallback_ok, fallback_notes = self.validator.validate(request, fallback)
            return StorytellerDecision(
                request=request,
                proposal=fallback,
                applied=fallback_ok,
                validator_notes=(*notes, *fallback_notes),
            )
        return StorytellerDecision(request=request, proposal=proposal, applied=True)

from __future__ import annotations

import json
import re
from typing import Any

from ..llm import LLMError, OpenAICompatibleClient
from .decisions import DecisionProposal, DecisionRequest


class LLMDecisionProvider:
    def __init__(self, client: OpenAICompatibleClient | None = None) -> None:
        self.client = client or OpenAICompatibleClient()

    def propose(self, request: DecisionRequest) -> DecisionProposal:
        try:
            raw = self.client.complete(self._messages(request), response_format="json")
            data = self._parse_json_object(raw)
            return DecisionProposal(
                decision_id=str(data.get("decision_id") or request.decision_id),
                selected_output=data.get("selected_output"),
                message_to_player=str(data.get("message_to_player") or ""),
                public_message=str(data.get("public_message") or ""),
                reason=str(data.get("reason") or "LLM storyteller decision."),
                confidence=float(data.get("confidence") or 0.0),
            )
        except Exception as exc:
            return DecisionProposal(
                decision_id=request.decision_id,
                selected_output=self._fallback_output(request),
                reason=f"LLM decision provider failed: {exc}",
                confidence=0.0,
            )

    def _messages(self, request: DecisionRequest) -> list[dict[str, str]]:
        payload = {
            "decision_id": request.decision_id,
            "decision_type": request.decision_type.value,
            "actor_id": request.actor_id,
            "role_id": request.role_id,
            "prompt": request.prompt,
            "allowed_outputs": list(request.allowed_outputs),
            "true_value_storyteller_only": request.true_value,
            "constraints": list(request.constraints),
            "context": request.context,
            "required_response_schema": {
                "decision_id": request.decision_id,
                "selected_output": "one exact value from allowed_outputs",
                "message_to_player": "optional private message, no leaks",
                "public_message": "optional public message",
                "reason": "short storyteller-only reason",
                "confidence": "number from 0 to 1",
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are the AI Storyteller decision module for Blood on the Clocktower. "
                    "Return one JSON object only. The selected_output must be exactly one of "
                    "the allowed_outputs. Never reveal hidden true values or poisoning/drunkenness "
                    "in player-facing messages."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    @staticmethod
    def _fallback_output(request: DecisionRequest) -> Any:
        if request.fallback_output is not None:
            return request.fallback_output
        if request.allowed_outputs:
            return request.allowed_outputs[0]
        return None

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as first_error:
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                raise LLMError(f"LLM did not return JSON: {raw}") from first_error
            return json.loads(match.group(0))

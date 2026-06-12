from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gamemaster.core.decision_engine import StorytellerDecisionEngine
from gamemaster.core.decisions import DecisionRequest
from gamemaster.core.llm_provider import LLMDecisionProvider
from gamemaster.core.types import DecisionType


class FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.messages = None
        self.response_format = None

    def complete(self, messages, response_format="text") -> str:
        self.messages = messages
        self.response_format = response_format
        return self.response


class CoreLLMProviderTest(unittest.TestCase):
    def make_request(self) -> DecisionRequest:
        return DecisionRequest.create(
            DecisionType.FALSE_INFORMATION,
            actor_id="u1",
            role_id="empath",
            prompt="Choose a number.",
            allowed_outputs=(0, 1, 2),
            true_value=2,
            fallback_output=0,
        )

    def test_provider_parses_valid_json(self) -> None:
        request = self.make_request()
        client = FakeClient(
            json.dumps(
                {
                    "decision_id": request.decision_id,
                    "selected_output": 1,
                    "message_to_player": "You learn 1.",
                    "reason": "Useful false info.",
                    "confidence": 0.8,
                }
            )
        )
        provider = LLMDecisionProvider(client)

        proposal = provider.propose(request)

        self.assertEqual(proposal.decision_id, request.decision_id)
        self.assertEqual(proposal.selected_output, 1)
        self.assertEqual(proposal.message_to_player, "You learn 1.")
        self.assertEqual(client.response_format, "json")

    def test_provider_falls_back_on_invalid_json(self) -> None:
        request = self.make_request()
        provider = LLMDecisionProvider(FakeClient("not-json"))

        proposal = provider.propose(request)

        self.assertEqual(proposal.decision_id, request.decision_id)
        self.assertEqual(proposal.selected_output, 0)
        self.assertIn("failed", proposal.reason)

    def test_decision_engine_rejects_llm_output_outside_allowed_values(self) -> None:
        request = self.make_request()
        provider = LLMDecisionProvider(
            FakeClient(json.dumps({"decision_id": request.decision_id, "selected_output": 99}))
        )
        engine = StorytellerDecisionEngine(provider=provider)

        decision = engine.decide(request)

        self.assertEqual(decision.proposal.selected_output, 0)
        self.assertTrue(decision.validator_notes)


if __name__ == "__main__":
    unittest.main()

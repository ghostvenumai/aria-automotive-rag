from __future__ import annotations

from app.workflow.agents import IntentClassifierAgent
from app.workflow.state import AskWorkflowState


def test_intent_classifier_detects_financing() -> None:
    agent = IntentClassifierAgent()
    state = AskWorkflowState(
        request_id="test-request",
        raw_input="Can you explain leasing and financing for a used SUV?",
    )

    trace = agent.classify(state)

    assert trace["decision"] == "financing"
    assert trace["metadata"]["keyword_hits"] >= 2


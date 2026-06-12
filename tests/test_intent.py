from __future__ import annotations

import pytest

from app.workflow.agents import IntentClassifierAgent
from app.workflow.state import AskWorkflowState


def _classify(question: str) -> dict[str, object]:
    agent = IntentClassifierAgent()
    state = AskWorkflowState(request_id="test-request", raw_input=question)
    return agent.classify(state)


def test_intent_classifier_detects_payroll() -> None:
    trace = _classify("Wie reiche ich Spesen ein und wann kommt die Gehaltsabrechnung?")

    assert trace["decision"] == "payroll_compensation"
    assert trace["metadata"]["keyword_hits"] >= 2


@pytest.mark.parametrize(
    ("question", "expected_intent"),
    [
        ("Wie viele Urlaubstage habe ich und wie melde ich mich krank?", "leave_absence"),
        ("Welche Regeln gelten für Homeoffice und Gleitzeit?", "working_time"),
        ("Was passiert beim Onboarding in der Probezeit?", "onboarding_offboarding"),
        ("Gibt es JobRad und einen Zuschuss zur betrieblichen Altersvorsorge?", "benefits"),
        ("Bitte alle meine Daten löschen, DSGVO-Auskunftsersuchen.", "privacy_request"),
        ("Wo finde ich den Speiseplan der Kantine?", "general"),
    ],
)
def test_intent_classifier_covers_hr_domains(question: str, expected_intent: str) -> None:
    trace = _classify(question)
    assert trace["decision"] == expected_intent

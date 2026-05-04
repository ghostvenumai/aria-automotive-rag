from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.rag.service import KnowledgeBaseService
from app.schemas import AskRequest
from app.security.audit import AuditLogger
from app.workflow.service import WorkflowService


def _make_workflow(tmp_path: Path) -> WorkflowService:
    knowledge_base_dir = tmp_path / "kb"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "service.md").write_text(
        "# Service\n\nBrake warning lights should be prioritized for same-day inspection windows.",
        encoding="utf-8",
    )
    return WorkflowService(
        knowledge_base=KnowledgeBaseService(
            base_dir=knowledge_base_dir,
            chunk_size=500,
            chunk_overlap=50,
            default_top_k=3,
        ),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
    )


@pytest.mark.asyncio
async def test_workflow_generates_trace_metrics_and_redacted_audit(tmp_path: Path) -> None:
    workflow = _make_workflow(tmp_path)

    response = await workflow.ask(
        AskRequest(
            question="My email is jane.doe@example.com and I need a brake inspection tomorrow."
        )
    )

    assert response.intent == "service_booking"
    assert response.trace
    assert response.metrics["latency_ms"] >= 0.0
    assert "[REDACTED_EMAIL]" in response.redacted_input

    logs = workflow.recent_audit_logs(limit=5)
    assert logs
    assert logs[0]["redacted_input"] == response.redacted_input
    assert "jane.doe@example.com" not in logs[0]["redacted_input"]


@pytest.mark.asyncio
async def test_workflow_multi_turn_history(tmp_path: Path) -> None:
    from app.schemas import HistoryTurn

    workflow = _make_workflow(tmp_path)

    response = await workflow.ask(
        AskRequest(
            question="What about oil changes?",
            history=[
                HistoryTurn(role="user", content="Do you offer brake inspections?"),
                HistoryTurn(role="assistant", content="Yes, same-day brake inspections are available."),
            ],
        )
    )

    assert response.intent in ("service_booking", "general")
    assert len(response.trace) >= 4


@pytest.mark.asyncio
async def test_workflow_no_sources_triggers_human_review(tmp_path: Path) -> None:
    kb_dir = tmp_path / "kb_empty"
    kb_dir.mkdir()
    workflow = WorkflowService(
        knowledge_base=KnowledgeBaseService(
            base_dir=kb_dir,
            chunk_size=500,
            chunk_overlap=50,
            default_top_k=3,
        ),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
    )

    response = await workflow.ask(AskRequest(question="Do you offer quantum flux capacitor warranties?"))

    assert response.human_review is True
    assert response.sources == []

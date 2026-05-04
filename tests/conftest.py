from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def configured_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    knowledge_base_dir = tmp_path / "knowledge_base"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "financing.md").write_text(
        "# Financing\n\nUsed SUV financing should stay within approved monthly rate bands and escalate binding approvals.",
        encoding="utf-8",
    )
    (knowledge_base_dir / "service.md").write_text(
        "# Service\n\nBrake warning light requests should be prioritized for same-day inspection whenever possible.",
        encoding="utf-8",
    )
    audit_log_file = tmp_path / "audit.jsonl"

    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(knowledge_base_dir))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_log_file))

    return {
        "knowledge_base_dir": knowledge_base_dir,
        "audit_log_file": audit_log_file,
    }


@pytest.fixture
def client(configured_paths: dict[str, Path]) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client

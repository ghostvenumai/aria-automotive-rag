from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def configured_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    knowledge_base_dir = tmp_path / "knowledge_base"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "spesen.md").write_text(
        "# Spesen\n\nReisekosten und Spesen werden innerhalb von 30 Tagen über das Spesentool eingereicht und mit der nächsten Gehaltsabrechnung erstattet.",
        encoding="utf-8",
    )
    (knowledge_base_dir / "urlaub.md").write_text(
        "# Urlaub\n\nVollzeitbeschäftigte haben 30 Urlaubstage pro Jahr, Resturlaub muss bis zum 31. März des Folgejahres genommen werden.",
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

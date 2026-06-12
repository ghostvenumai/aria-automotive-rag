from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health_and_root_page(client: TestClient) -> None:
    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "KLARA" in index_response.text


def test_ask_metrics_and_audit_log_endpoints(
    client: TestClient,
    configured_paths: dict[str, Path],
) -> None:
    ask_response = client.post(
        "/api/v1/ask",
        json={"question": "Wie reiche ich Reisekosten und Spesen zur Erstattung ein?"},
    )
    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["intent"] == "payroll_compensation"
    assert ask_payload["sources"]

    metrics_response = client.get("/api/v1/metrics")
    assert metrics_response.status_code == 200
    assert metrics_response.json()["requests_total"] >= 1

    audit_response = client.get("/api/v1/audit-logs")
    assert audit_response.status_code == 200
    entries = audit_response.json()["entries"]
    assert entries
    assert "redacted_input" in entries[0]
    assert str(configured_paths["audit_log_file"]).endswith("audit.jsonl")


def test_ingest_endpoint_updates_index(client: TestClient) -> None:
    ingest_response = client.post(
        "/api/v1/ingest",
        json={
            "documents": [
                {
                    "title": "JobRad Leitfaden",
                    "content": "JobRad Leasing läuft über Entgeltumwandlung, pro Person können bis zu zwei Fahrräder geleast werden.",
                    "category": "benefits",
                    "tags": ["jobrad", "benefits"],
                }
            ]
        },
    )
    assert ingest_response.status_code == 200
    payload = ingest_response.json()
    assert payload["ingested_documents"] == 1
    assert payload["total_chunks"] >= 1

    ask_response = client.post(
        "/api/v1/ask",
        json={"question": "Wie funktioniert das JobRad Leasing über Entgeltumwandlung?"},
    )
    assert ask_response.status_code == 200
    assert ask_response.json()["sources"]

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_health_and_root_page(client: TestClient) -> None:
    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "Autohaus AI RAG Agent Backend" in index_response.text


def test_ask_metrics_and_audit_log_endpoints(
    client: TestClient,
    configured_paths: dict[str, Path],
) -> None:
    ask_response = client.post(
        "/api/v1/ask",
        json={"question": "Can you explain financing for a used SUV with low monthly payments?"},
    )
    assert ask_response.status_code == 200
    ask_payload = ask_response.json()
    assert ask_payload["intent"] == "financing"
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
                    "title": "Warranty Guide",
                    "content": "Battery warranty claims for certified EV inventory need supervisor approval after a seven year threshold.",
                    "category": "warranty",
                    "tags": ["ev", "warranty"],
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
        json={"question": "How do battery warranty claims work for certified EV inventory?"},
    )
    assert ask_response.status_code == 200
    assert ask_response.json()["sources"]

from __future__ import annotations

from pathlib import Path

from app.rag.service import KnowledgeBaseService


def test_retriever_returns_scored_sources(tmp_path: Path) -> None:
    knowledge_base_dir = tmp_path / "kb"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "tradein.md").write_text(
        "# Trade In\n\nTrade-in valuations require mileage, service history, and an on-site inspection.",
        encoding="utf-8",
    )

    service = KnowledgeBaseService(
        base_dir=knowledge_base_dir,
        chunk_size=500,
        chunk_overlap=50,
        default_top_k=3,
    )

    results = service.search("What do you need for a trade-in valuation?")

    assert results
    assert results[0].score > 0.0
    assert "inspection" in results[0].snippet.lower()


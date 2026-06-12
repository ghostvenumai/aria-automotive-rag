from __future__ import annotations

from pathlib import Path

from app.rag.service import KnowledgeBaseService


def test_retriever_returns_scored_sources(tmp_path: Path) -> None:
    knowledge_base_dir = tmp_path / "kb"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "spesen.md").write_text(
        "# Spesen\n\nReisekosten und Spesen werden über das Spesentool eingereicht und nach Freigabe erstattet.",
        encoding="utf-8",
    )

    service = KnowledgeBaseService(
        base_dir=knowledge_base_dir,
        chunk_size=500,
        chunk_overlap=50,
        default_top_k=3,
    )

    results = service.search("Wie werden Reisekosten und Spesen eingereicht und erstattet?")

    assert results
    assert results[0].score > 0.0
    assert "spesen" in results[0].snippet.lower()


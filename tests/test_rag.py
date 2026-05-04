from pathlib import Path

from app.rag.service import KnowledgeBaseService
from app.schemas import IngestDocument


def test_retriever_returns_ranked_sources(tmp_path: Path) -> None:
    knowledge_base_dir = tmp_path / "kb"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "service-intake.md").write_text(
        "# Service Intake\n\nService advisors should prioritize brake warning repairs for same-day inspection.",
        encoding="utf-8",
    )

    service = KnowledgeBaseService(
        base_dir=knowledge_base_dir,
        chunk_size=500,
        chunk_overlap=50,
        default_top_k=3,
    )

    sources = service.search("How should service advisors handle brake warning repairs?")

    assert sources
    assert sources[0].title == "Service Intake"
    assert float(sources[0].score) > 0


class FakeSupabaseStore:
    def __init__(self) -> None:
        self.upserted: list[IngestDocument] = []

    def fetch_documents(self):
        return [
            type(
                "RemoteDoc",
                (),
                {
                    "doc_id": "remote-finance",
                    "title": "Remote Finance Guide",
                    "text": "Leasing with lower monthly payments is often a good fit for used SUVs.",
                    "source_path": "supabase://rag_documents/remote-finance",
                    "metadata": {"source": "supabase"},
                },
            )()
        ]

    def upsert_documents(self, documents: list[IngestDocument]) -> int:
        self.upserted.extend(documents)
        return len(documents)


def test_retriever_can_include_supabase_documents(tmp_path: Path) -> None:
    service = KnowledgeBaseService(
        base_dir=tmp_path / "kb",
        chunk_size=500,
        chunk_overlap=50,
        default_top_k=3,
        remote_store=FakeSupabaseStore(),
    )

    sources = service.search("Which option helps with lower monthly payments for a used SUV?")

    assert sources
    assert sources[0].title == "Remote Finance Guide"
    assert service.status()["remote_sync_enabled"] is True


def test_ingest_can_push_documents_to_supabase_store(tmp_path: Path) -> None:
    remote_store = FakeSupabaseStore()
    service = KnowledgeBaseService(
        base_dir=tmp_path / "kb",
        chunk_size=500,
        chunk_overlap=50,
        default_top_k=3,
        remote_store=remote_store,
    )

    service.ingest_documents(
        [
            IngestDocument(
                title="Trade-In Policy",
                content="Trade-in evaluations require mileage, service history, and a quick inspection.",
                source_id="trade-in-policy",
                category="trade_in",
                tags=["valuation"],
            )
        ]
    )

    assert remote_store.upserted
    assert remote_store.upserted[0].title == "Trade-In Policy"

from pathlib import Path

from app.rag.service import KnowledgeBaseService
from app.schemas import IngestDocument


def test_retriever_returns_ranked_sources(tmp_path: Path) -> None:
    knowledge_base_dir = tmp_path / "kb"
    knowledge_base_dir.mkdir()
    (knowledge_base_dir / "krankmeldung.md").write_text(
        "# Krankmeldung\n\nDie Krankmeldung erfolgt vor Arbeitsbeginn an die Führungskraft, eine AU-Bescheinigung ist ab dem dritten Kalendertag erforderlich.",
        encoding="utf-8",
    )

    service = KnowledgeBaseService(
        base_dir=knowledge_base_dir,
        chunk_size=500,
        chunk_overlap=50,
        default_top_k=3,
    )

    sources = service.search("Wann brauche ich eine AU-Bescheinigung für die Krankmeldung?")

    assert sources
    assert sources[0].title == "Krankmeldung"
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
                    "doc_id": "remote-homeoffice",
                    "title": "Remote Homeoffice Guide",
                    "text": "Mobiles Arbeiten ist an bis zu drei Tagen pro Woche möglich, Anträge laufen über das HR-Portal.",
                    "source_path": "supabase://rag_documents/remote-homeoffice",
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

    sources = service.search("An wie vielen Tagen pro Woche ist mobiles Arbeiten möglich?")

    assert sources
    assert sources[0].title == "Remote Homeoffice Guide"
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
                title="Spesenrichtlinie",
                content="Spesen und Reisekosten werden innerhalb von 30 Tagen über das Spesentool eingereicht.",
                source_id="spesenrichtlinie",
                category="payroll_compensation",
                tags=["spesen"],
            )
        ]
    )

    assert remote_store.upserted
    assert remote_store.upserted[0].title == "Spesenrichtlinie"

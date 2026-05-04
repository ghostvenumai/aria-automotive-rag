from __future__ import annotations

import re
from pathlib import Path

from app.rag.chunking import chunk_document
from app.rag.embeddings import OpenAIEmbeddingClient, cosine_similarity
from app.rag.loader import load_documents
from app.rag.models import Chunk, Document, RetrievedSource
from app.rag.retriever import hybrid_search, search_chunks
from app.rag.supabase_store import SupabaseKnowledgeStore
from app.schemas import IngestDocument


class KnowledgeBaseService:
    def __init__(
        self,
        *,
        base_dir: Path,
        chunk_size: int,
        chunk_overlap: int,
        default_top_k: int,
        openai_api_key: str | None = None,
        openai_embedding_model: str = "text-embedding-3-small",
        remote_store: SupabaseKnowledgeStore | None = None,
        hybrid_enabled: bool = True,
    ) -> None:
        self.base_dir = base_dir
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_top_k = default_top_k
        self.openai_api_key = openai_api_key
        self.openai_embedding_model = openai_embedding_model
        self.remote_store = remote_store
        self.hybrid_enabled = hybrid_enabled
        self.documents: list[Document] = []
        self.chunks: list[Chunk] = []
        self.embedding_mode = "local"
        self.remote_sync_enabled = remote_store is not None
        self.remote_sync_healthy = False
        self._openai_client: OpenAIEmbeddingClient | None = None

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._enable_openai_if_possible()
        self.reload()

    def reload(self) -> None:
        documents_by_id = {document.doc_id: document for document in load_documents(self.base_dir)}
        self.remote_sync_healthy = False
        if self.remote_store is not None:
            try:
                remote_documents = self.remote_store.fetch_documents()
                for document in remote_documents:
                    documents_by_id[document.doc_id] = document
                self.remote_sync_healthy = True
            except Exception:
                self.remote_sync_healthy = False
        self.documents = list(documents_by_id.values())
        self.chunks = []
        for document in self.documents:
            self.chunks.extend(
                chunk_document(
                    document,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                )
            )
        self._refresh_chunk_embeddings()

    def search(self, query: str, *, top_k: int | None = None) -> list[RetrievedSource]:
        k = top_k or self.default_top_k
        if self._openai_client and self.chunks:
            try:
                query_embedding = self._openai_client.embed_texts([query])[0]
                if self.hybrid_enabled:
                    self.embedding_mode = "hybrid_rrf"
                    return hybrid_search(query, query_embedding, self.chunks, top_k=k)
                self.embedding_mode = "dense"
                return self._dense_search_with_embedding(query_embedding, top_k=k)
            except Exception:
                self.embedding_mode = "local"
                self._openai_client = None
        return search_chunks(query, self.chunks, top_k=k)

    def ingest_documents(self, documents: list[IngestDocument]) -> tuple[int, int]:
        for index, document in enumerate(documents, start=1):
            safe_stem = self._safe_stem(document.source_id or document.title, index=index)
            target = self.base_dir / f"{safe_stem}.md"
            metadata_block = []
            if document.category:
                metadata_block.append(f"category: {document.category}")
            if document.tags:
                metadata_block.append(f"tags: {', '.join(document.tags)}")
            header = f"# {document.title}\n\n"
            if metadata_block:
                header += "\n".join(f"- {line}" for line in metadata_block) + "\n\n"
            target.write_text(header + document.content.strip() + "\n", encoding="utf-8")

        if self.remote_store is not None:
            try:
                self.remote_store.upsert_documents(documents)
                self.remote_sync_healthy = True
            except Exception:
                self.remote_sync_healthy = False

        self.reload()
        return len(documents), len(self.chunks)

    def status(self) -> dict[str, int | str]:
        return {
            "documents_indexed": len(self.documents),
            "chunks_indexed": len(self.chunks),
            "embedding_mode": self.embedding_mode,
            "remote_sync_enabled": self.remote_sync_enabled,
            "remote_sync_healthy": self.remote_sync_healthy,
        }

    def _safe_stem(self, raw_value: str, *, index: int) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", raw_value.lower()).strip("-")
        return normalized or f"ingested-document-{index}"

    def _enable_openai_if_possible(self) -> None:
        if not self.openai_api_key:
            self.embedding_mode = "local"
            return
        try:
            self._openai_client = OpenAIEmbeddingClient(
                api_key=self.openai_api_key,
                model=self.openai_embedding_model,
            )
            self.embedding_mode = "openai"
        except RuntimeError:
            self._openai_client = None
            self.embedding_mode = "local"

    def _refresh_chunk_embeddings(self) -> None:
        if not self._openai_client or not self.chunks:
            return
        embeddings = self._openai_client.embed_texts([chunk.text for chunk in self.chunks])
        for chunk, embedding in zip(self.chunks, embeddings, strict=False):
            chunk.embedding = embedding

    def _dense_search_with_embedding(self, query_embedding: list[float], *, top_k: int) -> list[RetrievedSource]:
        from app.rag.retriever import dense_search_chunks
        return dense_search_chunks(query_embedding, self.chunks, top_k=top_k)

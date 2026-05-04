from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.rag.models import Document
from app.schemas import IngestDocument


@dataclass(slots=True)
class SupabaseDocumentRecord:
    doc_id: str
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SupabaseKnowledgeStore:
    def __init__(
        self,
        *,
        project_url: str,
        service_role_key: str,
        table_name: str = "rag_documents",
        timeout: float = 10.0,
    ) -> None:
        self.project_url = project_url.rstrip("/")
        self.service_role_key = service_role_key
        self.table_name = table_name
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }

    @property
    def _endpoint(self) -> str:
        return f"{self.project_url}/rest/v1/{self.table_name}"

    def fetch_documents(self) -> list[Document]:
        params = {"select": "doc_id,title,content,category,tags,updated_at", "limit": "500"}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self._endpoint, headers=self._headers, params=params)
            response.raise_for_status()
            payload = response.json()

        documents: list[Document] = []
        for item in payload:
            doc_id = str(item.get("doc_id") or item.get("title") or "supabase-document")
            title = str(item.get("title") or doc_id)
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            documents.append(
                Document(
                    doc_id=doc_id,
                    title=title,
                    text=content,
                    source_path=f"supabase://{self.table_name}/{doc_id}",
                    metadata={
                        "extension": ".supabase",
                        "category": item.get("category"),
                        "tags": item.get("tags") or [],
                        "updated_at": item.get("updated_at"),
                        "source": "supabase",
                    },
                )
            )
        return documents

    def upsert_documents(self, documents: list[IngestDocument]) -> int:
        if not documents:
            return 0

        payload = [
            {
                "doc_id": document.source_id or document.title.lower().replace(" ", "-"),
                "title": document.title,
                "content": document.content,
                "category": document.category,
                "tags": document.tags,
            }
            for document in documents
        ]
        headers = {**self._headers, "Prefer": "resolution=merge-duplicates"}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self._endpoint, headers=headers, json=payload)
            response.raise_for_status()
        return len(payload)

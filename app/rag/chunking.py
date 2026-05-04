from __future__ import annotations

from app.rag.models import Chunk, Document


def chunk_document(document: Document, *, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    text = document.text.strip()
    if len(text) <= chunk_size:
        return [
            Chunk(
                chunk_id=f"{document.doc_id}-chunk-1",
                doc_id=document.doc_id,
                title=document.title,
                text=text,
                metadata={"source_path": document.source_path, **document.metadata},
            )
        ]

    chunks: list[Chunk] = []
    start = 0
    chunk_index = 1
    step = max(chunk_size - chunk_overlap, 1)

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    chunk_id=f"{document.doc_id}-chunk-{chunk_index}",
                    doc_id=document.doc_id,
                    title=document.title,
                    text=chunk_text,
                    metadata={"source_path": document.source_path, **document.metadata},
                )
            )
            chunk_index += 1
        if end >= len(text):
            break
        start += step

    return chunks


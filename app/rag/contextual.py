from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.llm import ClaudeInferenceClient
    from app.rag.models import Chunk, Document

_CONTEXTUAL_SYSTEM = """\
Du bist ein Experte für Dokumentenanalyse. Schreibe eine 1-2 Sätze lange Kontextbeschreibung
für den gegebenen Textabschnitt, die erklärt, was dieser im Kontext des Gesamtdokuments aussagt.
Antworte NUR mit der Beschreibung – keine Einleitung, kein Kommentar.
"""


async def enrich_chunks_contextually(
    chunks: list[Chunk],
    documents: list[Document],
    llm: ClaudeInferenceClient,
    *,
    max_chunks: int = 100,
) -> int:
    """Anthropic Contextual Retrieval: prepend a situating sentence to each chunk.

    Each chunk is enriched with a 1-2 sentence description that explains its meaning
    within the parent document. This dramatically improves retrieval accuracy because
    the embedding now captures the document-level context, not just the isolated chunk.

    Reference: https://www.anthropic.com/news/contextual-retrieval
    Returns the number of successfully enriched chunks.
    """
    doc_map = {doc.doc_id: doc for doc in documents}
    results: list[int] = []

    async def _enrich(chunk: Chunk) -> int:
        doc = doc_map.get(chunk.doc_id)
        if not doc:
            return 0
        prompt = (
            f"<dokument>\n{doc.text[:6000]}\n</dokument>\n\n"
            f"<abschnitt>\n{chunk.text}\n</abschnitt>\n\n"
            "Erkläre in 1-2 Sätzen, was dieser Abschnitt im Kontext des gesamten Dokuments aussagt."
        )
        try:
            response = await llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system=_CONTEXTUAL_SYSTEM,
            )
            context_sentence = response.text.strip()
            if context_sentence:
                chunk.text = f"{context_sentence}\n\n{chunk.text}"
                return 1
        except Exception:
            pass
        return 0

    target = chunks[:max_chunks]
    results = await asyncio.gather(*[_enrich(c) for c in target])
    return sum(results)

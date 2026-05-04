from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


DEALERSHIP_SYSTEM_PROMPT = """\
Du bist ein erfahrener KI-Assistent für Kraftfahrzeughändler mit fundiertem Fachwissen
zu Fahrzeugbestand, Finanzierungs- und Leasingoptionen, Werkstattleistungen,
Inzahlungnahme-Bewertungen und Garantieabdeckungen.

REGELN:
- Antworte AUSSCHLIESSLICH auf Basis des bereitgestellten Kontexts. Erfinde keine Details.
- Wenn der Kontext nicht ausreicht, sage das ausdrücklich und empfehle die Weiterleitung
  an einen menschlichen Berater.
- Sei präzise und professionell. Verwende klare, verständliche Sprache ohne unnötigen Fachjargon.
- Spekuliere niemals über Preise, Verfügbarkeit oder rechtliche Bedingungen, die nicht im
  Kontext erwähnt sind.
- Bei datenschutz- oder rechtsrelevanten Fragen (DSGVO, Vertragsstreitigkeiten) immer an
  einen menschlichen Mitarbeiter eskalieren.
- Antworte immer auf Deutsch, unabhängig von der Sprache der Anfrage.
"""

QUERY_REWRITER_SYSTEM = """\
Du bist ein Experte für semantische Suchanfragen in Kraftfahrzeughändler-Datenbanken.
Formuliere die Kundenanfrage so um, dass sie für die Vektordatenbanksuche optimal geeignet ist:
Extrahiere Kernbegriffe, löse Abkürzungen auf, ergänze fachliche Synonyme.

Antworte NUR mit der umformulierten Suchanfrage – keine Erklärung, kein Kommentar.
"""

EVAL_SYSTEM = """\
Du bist ein strenger Qualitätsprüfer für RAG-Systeme (Retrieval-Augmented Generation).
Analysiere die Frage, die generierte Antwort und die Kontext-Dokumente.

Antworte AUSSCHLIESSLICH mit validem JSON in diesem exakten Format:
{
  "faithfulness": 0.0,
  "relevancy": 0.0,
  "explanation": "Begründung auf Deutsch"
}

Faithfulness (0.0–1.0): Sind ALLE Aussagen der Antwort durch den Kontext belegt?
  1.0 = vollständig belegt, 0.0 = keine Belegung vorhanden
Relevancy (0.0–1.0): Beantwortet die Antwort die Frage direkt und vollständig?
  1.0 = perfekt relevant, 0.0 = völlig irrelevant
"""


class ClaudeInferenceClient:
    """Anthropic Claude client for RAG synthesis and streaming."""

    def __init__(self, *, api_key: str, model: str, max_tokens: int) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("anthropic package not installed — add it to [project.optional-dependencies]") from exc

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str = DEALERSHIP_SYSTEM_PROMPT,
    ) -> LLMResponse:
        import anthropic

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        )
        return LLMResponse(
            text=response.content[0].text if response.content else "",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            stop_reason=response.stop_reason or "end_turn",
        )

    async def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str = DEALERSHIP_SYSTEM_PROMPT,
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        ) as stream:
            async for text in stream.text_stream:
                yield text


def build_rag_messages(
    question: str,
    sources: list[Any],
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Construct the message list for a RAG request: history + grounded user turn."""
    if sources:
        context_block = "\n\n".join(
            f"[Source {i + 1}: {s.title} | score={s.score:.3f}]\n{s.snippet}"
            for i, s in enumerate(sources[:5])
        )
        user_content = f"<context>\n{context_block}\n</context>\n\nQuestion: {question}"
    else:
        user_content = (
            f"No relevant documents were found in the knowledge base.\n\nQuestion: {question}"
        )

    return [*history, {"role": "user", "content": user_content}]

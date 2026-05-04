from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    source_id: str
    title: str
    score: float = Field(ge=0.0)
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTraceStep(BaseModel):
    agent: str
    decision: str
    rationale: str
    latency_ms: float = Field(ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HistoryTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=4000)
    customer_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    history: list[HistoryTurn] = Field(
        default_factory=list,
        max_length=10,
        description="Previous conversation turns for multi-turn context (max 10).",
    )


class AskResponse(BaseModel):
    request_id: str
    intent: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    human_review: bool
    hallucination_risk: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Anteil der Antwortsätze ohne Token-Überlappung mit den abgerufenen Quellen. "
            "0.0 = vollständig belegt, 1.0 = kein Satz durch Quellen gedeckt."
        ),
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Sätze der Antwort, die nicht durch abgerufene Quellen belegt werden konnten.",
    )
    redacted_input: str
    sources: list[SourceItem]
    trace: list[AgentTraceStep]
    metrics: dict[str, Any]
    token_usage: dict[str, Any] | None = None


class IngestDocument(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=20, max_length=20000)
    source_id: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    documents: list[IngestDocument] = Field(min_length=1, max_length=25)
    contextual_enrichment: bool = Field(
        default=False,
        description=(
            "Aktiviert Anthropic Contextual Retrieval: Claude generiert für jeden Chunk "
            "eine Kontextbeschreibung, die vor dem Embedding vorangestellt wird. "
            "Verbessert die Retrieval-Präzision deutlich, erhöht aber die Ingest-Latenz."
        ),
    )


class IngestResponse(BaseModel):
    request_id: str
    ingested_documents: int
    total_chunks: int
    embedding_mode: str


class MetricsResponse(BaseModel):
    requests_total: int
    ingest_requests_total: int
    average_latency_ms: float
    average_confidence: float
    human_review_rate: float
    fallback_request_rate: float
    total_llm_input_tokens: int = 0
    total_llm_output_tokens: int = 0
    intent_distribution: dict[str, int]
    documents_indexed: int
    chunks_indexed: int
    embedding_mode: str


class AuditLogEntryResponse(BaseModel):
    timestamp: str
    event_type: str
    request_id: str
    redacted_input: str
    metadata: dict[str, Any]


class AuditLogsResponse(BaseModel):
    entries: list[AuditLogEntryResponse]


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    embedding_mode: str
    documents_indexed: int
    chunks_indexed: int


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorPayload


# ── RAG Evaluation (RAGAS-style) ─────────────────────────────────────────────

class EvalRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    answer: str = Field(min_length=5, max_length=8000)
    contexts: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Abgerufene Kontext-Dokumente, die zur Antwortgenerierung verwendet wurden.",
    )


class EvalResponse(BaseModel):
    faithfulness: float | None = Field(
        description="0–1: Sind alle Aussagen der Antwort durch den Kontext belegt?"
    )
    relevancy: float | None = Field(
        description="0–1: Beantwortet die Antwort die Frage direkt?"
    )
    overall: float | None = Field(description="Durchschnitt aus faithfulness und relevancy.")
    explanation: str = ""
    latency_ms: float = 0.0
    llm_model: str = ""
    error: str | None = None


# ── Contextual Ingest Response ────────────────────────────────────────────────

class ContextualIngestResponse(BaseModel):
    request_id: str
    ingested_documents: int
    total_chunks: int
    enriched_chunks: int
    embedding_mode: str
    contextual_retrieval: bool


# ── Debug Retrieval ───────────────────────────────────────────────────────────

class RetrievalDebugItem(BaseModel):
    rank: int
    source_id: str
    title: str
    score: float
    retrieval_mode: str
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalDebugResponse(BaseModel):
    query: str
    embedding_mode: str
    total_chunks_indexed: int
    results: list[RetrievalDebugItem]
    latency_ms: float


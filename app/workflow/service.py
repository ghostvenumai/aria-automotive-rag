from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.rag.llm import EVAL_SYSTEM, ClaudeInferenceClient
from app.rag.service import KnowledgeBaseService
from app.schemas import AskRequest, AskResponse, IngestRequest, IngestResponse, SourceItem
from app.security.audit import AuditLogger
from app.workflow.agents import (
    GroundingVerifierAgent,
    IntentClassifierAgent,
    MetricsAgent,
    PrivacyGuardAgent,
    QualityGuardAgent,
    QueryRewriterAgent,
    ResponseComposerAgent,
    RetrieverAgent,
)
from app.workflow.state import AskWorkflowState


@dataclass(slots=True)
class WorkflowMetricsSnapshot:
    requests_total: int = 0
    ingest_requests_total: int = 0
    total_latency_ms: float = 0.0
    total_confidence: float = 0.0
    human_review_total: int = 0
    fallback_total: int = 0
    total_llm_input_tokens: int = 0
    total_llm_output_tokens: int = 0
    intent_distribution: Counter[str] = field(default_factory=Counter)


class WorkflowService:
    def __init__(
        self,
        *,
        knowledge_base: KnowledgeBaseService,
        audit_logger: AuditLogger,
        llm: ClaudeInferenceClient | None = None,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.audit_logger = audit_logger
        self.llm = llm
        self.intent_agent = IntentClassifierAgent()
        self.privacy_agent = PrivacyGuardAgent()
        self.query_rewriter_agent = QueryRewriterAgent()
        self.retriever_agent = RetrieverAgent()
        self.response_agent = ResponseComposerAgent()
        self.grounding_agent = GroundingVerifierAgent()
        self.quality_agent = QualityGuardAgent()
        self.metrics_agent = MetricsAgent()
        self._metrics = WorkflowMetricsSnapshot()

    async def ask(self, request: AskRequest) -> AskResponse:
        request_id = str(uuid4())
        started_at = perf_counter()

        history = [
            {"role": turn.role, "content": turn.content}
            for turn in (request.history or [])
        ]

        state = AskWorkflowState(
            request_id=request_id,
            raw_input=request.question,
            history=history,
        )

        # ── Pipeline ─────────────────────────────────────────────────────────
        state.trace.append(self.privacy_agent.inspect(state))

        intent_trace = self.intent_agent.classify(state)
        state.intent = str(intent_trace["decision"])
        state.trace.append(intent_trace)

        state.trace.append(await self.query_rewriter_agent.rewrite(state, self.llm))
        state.trace.append(await self.retriever_agent.retrieve(state, self.knowledge_base))

        quality_trace = self.quality_agent.evaluate(state)
        state.trace.append(quality_trace)

        state.trace.append(await self.response_agent.compose(state, self.llm))
        state.trace.append(self.grounding_agent.verify(state))

        metrics_trace = self.metrics_agent.finalize(
            state,
            started_at=started_at,
            source_count=len(state.sources),
        )
        state.trace.append(metrics_trace)

        self.audit_logger.log_event(
            event_type="ask",
            request_id=request_id,
            redacted_input=state.redacted_input,
            metadata={
                "intent": state.intent,
                "confidence": state.confidence,
                "human_review": state.human_review,
                "source_count": len(state.sources),
                "pii_types": state.pii_types,
                "session_id": request.session_id,
                "customer_id_present": bool(request.customer_id),
                "llm_model": state.llm_usage.get("model"),
                "llm_input_tokens": state.llm_usage.get("input_tokens", 0),
                "llm_output_tokens": state.llm_usage.get("output_tokens", 0),
                "rewritten_query": state.rewritten_query != state.raw_input,
            },
        )
        self._record_metrics(state)

        return AskResponse(
            request_id=request_id,
            intent=state.intent,
            answer=state.answer,
            confidence=state.confidence,
            human_review=state.human_review,
            hallucination_risk=state.hallucination_risk,
            unsupported_claims=state.unsupported_claims,
            redacted_input=state.redacted_input,
            sources=[
                SourceItem(
                    source_id=source.source_id,
                    title=source.title,
                    score=source.score,
                    snippet=source.snippet,
                    metadata=source.metadata,
                )
                for source in state.sources
            ],
            trace=state.trace,
            metrics=state.metrics,
            token_usage=state.llm_usage or None,
        )

    async def ask_stream(self, request: AskRequest):
        """Async generator that yields SSE-formatted chunks for streaming responses."""
        request_id = str(uuid4())
        started_at = perf_counter()
        history = [
            {"role": turn.role, "content": turn.content}
            for turn in (request.history or [])
        ]
        state = AskWorkflowState(
            request_id=request_id,
            raw_input=request.question,
            history=history,
        )

        state.trace.append(self.privacy_agent.inspect(state))
        intent_trace = self.intent_agent.classify(state)
        state.intent = str(intent_trace["decision"])
        state.trace.append(intent_trace)
        state.trace.append(await self.query_rewriter_agent.rewrite(state, self.llm))
        state.trace.append(await self.retriever_agent.retrieve(state, self.knowledge_base))
        state.trace.append(self.quality_agent.evaluate(state))

        yield f"event: sources\ndata: {json.dumps([s.__dict__ for s in state.sources])}\n\n"

        full_answer = ""
        if self.llm is not None and not state.human_review:
            from app.rag.llm import build_rag_messages
            messages = build_rag_messages(state.raw_input, state.sources, state.history)
            try:
                async for token in self.llm.stream(messages=messages):
                    full_answer += token
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
            except Exception as exc:
                full_answer = self.response_agent._template_answer(state.intent, state.sources)
                yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
        else:
            full_answer = self.response_agent._template_answer(state.intent, state.sources)
            yield f"event: token\ndata: {json.dumps({'text': full_answer})}\n\n"

        state.answer = full_answer
        metrics_trace = self.metrics_agent.finalize(
            state, started_at=started_at, source_count=len(state.sources)
        )
        state.trace.append(metrics_trace)
        self._record_metrics(state)

        yield f"event: done\ndata: {json.dumps({'request_id': request_id, 'metrics': state.metrics, 'confidence': state.confidence, 'human_review': state.human_review})}\n\n"

    def ingest(self, request: IngestRequest) -> IngestResponse:
        request_id = str(uuid4())
        ingested_documents, total_chunks = self.knowledge_base.ingest_documents(request.documents)
        self.audit_logger.log_event(
            event_type="ingest",
            request_id=request_id,
            redacted_input="[INGEST_PAYLOAD_REDACTED]",
            metadata={"document_count": ingested_documents},
        )
        self._metrics.ingest_requests_total += 1
        return IngestResponse(
            request_id=request_id,
            ingested_documents=ingested_documents,
            total_chunks=total_chunks,
            embedding_mode=self.knowledge_base.embedding_mode,
        )

    async def ingest_with_context(self, request: IngestRequest) -> dict[str, object]:
        """Ingest documents and enrich each chunk using Anthropic Contextual Retrieval.

        After standard ingestion, Claude generates a 1-2 sentence situating description
        for every chunk (within its parent document). This is then prepended to the chunk
        text before re-embedding, dramatically improving retrieval precision for
        fragmented or context-heavy documents.
        """
        from app.rag.contextual import enrich_chunks_contextually

        base_response = self.ingest(request)
        enriched_count = 0

        if self.llm is not None:
            enriched_count = await enrich_chunks_contextually(
                self.knowledge_base.chunks,
                self.knowledge_base.documents,
                self.llm,
            )
            # Re-embed after enrichment so vectors reflect the new context sentences
            self.knowledge_base._refresh_chunk_embeddings()

        return {
            "request_id": base_response.request_id,
            "ingested_documents": base_response.ingested_documents,
            "total_chunks": base_response.total_chunks,
            "enriched_chunks": enriched_count,
            "embedding_mode": base_response.embedding_mode,
            "contextual_retrieval": enriched_count > 0,
        }

    async def evaluate_rag(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> dict[str, object]:
        """RAGAS-style evaluation: score faithfulness and relevancy via Claude judge."""
        started_at = perf_counter()

        if self.llm is None:
            return {
                "error": "Kein LLM konfiguriert – Evaluation nicht verfügbar.",
                "faithfulness": None,
                "relevancy": None,
            }

        context_block = "\n\n".join(
            f"[Kontext {i + 1}]\n{ctx[:800]}" for i, ctx in enumerate(contexts[:5])
        )
        prompt = (
            f"Frage: {question}\n\n"
            f"Generierte Antwort: {answer}\n\n"
            f"Verwendete Kontext-Dokumente:\n{context_block}"
        )

        try:
            response = await self.llm.complete(
                messages=[{"role": "user", "content": prompt}],
                system=EVAL_SYSTEM,
            )
            raw = response.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import json as _json
            scores = _json.loads(raw)
            faithfulness = float(scores.get("faithfulness", 0.0))
            relevancy = float(scores.get("relevancy", 0.0))
            explanation = str(scores.get("explanation", ""))
        except Exception as exc:
            return {
                "error": f"Evaluation fehlgeschlagen: {exc!s}",
                "faithfulness": None,
                "relevancy": None,
            }

        return {
            "faithfulness": round(min(max(faithfulness, 0.0), 1.0), 3),
            "relevancy": round(min(max(relevancy, 0.0), 1.0), 3),
            "overall": round((faithfulness + relevancy) / 2, 3),
            "explanation": explanation,
            "latency_ms": round((perf_counter() - started_at) * 1000, 3),
            "llm_model": self.llm._model,
        }

    def debug_retrieval(self, query: str) -> dict[str, object]:
        """Return detailed retrieval diagnostics for a given query."""
        from time import perf_counter as _pc

        started_at = _pc()
        sources = self.knowledge_base.search(query)
        latency_ms = round((_pc() - started_at) * 1000, 3)

        return {
            "query": query,
            "embedding_mode": self.knowledge_base.embedding_mode,
            "total_chunks_indexed": len(self.knowledge_base.chunks),
            "results": [
                {
                    "rank": i + 1,
                    "source_id": s.source_id,
                    "title": s.title,
                    "score": s.score,
                    "retrieval_mode": s.metadata.get("retrieval_mode", "lexical"),
                    "snippet": s.snippet,
                    "metadata": s.metadata,
                }
                for i, s in enumerate(sources)
            ],
            "latency_ms": latency_ms,
        }

    def metrics_snapshot(self) -> dict[str, object]:
        status = self.knowledge_base.status()
        req = self._metrics.requests_total or 1
        return {
            "requests_total": self._metrics.requests_total,
            "ingest_requests_total": self._metrics.ingest_requests_total,
            "average_latency_ms": round(self._metrics.total_latency_ms / req, 3),
            "average_confidence": round(self._metrics.total_confidence / req, 3),
            "human_review_rate": round(self._metrics.human_review_total / req, 3),
            "fallback_request_rate": round(self._metrics.fallback_total / req, 3),
            "total_llm_input_tokens": self._metrics.total_llm_input_tokens,
            "total_llm_output_tokens": self._metrics.total_llm_output_tokens,
            "intent_distribution": dict(self._metrics.intent_distribution),
            **status,
        }

    def recent_audit_logs(self, *, limit: int) -> list[dict[str, object]]:
        return self.audit_logger.read_recent(limit=limit)

    def _record_metrics(self, state: AskWorkflowState) -> None:
        self._metrics.requests_total += 1
        self._metrics.total_latency_ms += float(state.metrics.get("latency_ms", 0.0))
        self._metrics.total_confidence += state.confidence
        self._metrics.human_review_total += int(state.human_review)
        self._metrics.fallback_total += int(state.fallback_used)
        self._metrics.total_llm_input_tokens += int(state.llm_usage.get("input_tokens", 0))
        self._metrics.total_llm_output_tokens += int(state.llm_usage.get("output_tokens", 0))
        self._metrics.intent_distribution[state.intent] += 1


AgentWorkflowService = WorkflowService

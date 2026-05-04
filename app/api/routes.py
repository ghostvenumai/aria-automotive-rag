from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_settings, get_workflow_service
from app.core.settings import Settings
from app.schemas import (
    AskRequest,
    AskResponse,
    AuditLogsResponse,
    ContextualIngestResponse,
    EvalRequest,
    EvalResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    MetricsResponse,
    RetrievalDebugResponse,
)
from app.workflow.service import WorkflowService

ui_router = APIRouter()
api_router = APIRouter()


@ui_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    templates = Jinja2Templates(directory=str(request.app.state.settings.template_dir))
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": request.app.state.settings.app_name},
    )


@ui_router.get("/health", response_model=HealthResponse, include_in_schema=False)
@api_router.get("/health", response_model=HealthResponse)
async def health(
    settings: Settings = Depends(get_settings),
    workflow: WorkflowService = Depends(get_workflow_service),
) -> HealthResponse:
    metrics = workflow.metrics_snapshot()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        embedding_mode=str(metrics["embedding_mode"]),
        documents_indexed=int(metrics["documents_indexed"]),
        chunks_indexed=int(metrics["chunks_indexed"]),
    )


@api_router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    workflow: WorkflowService = Depends(get_workflow_service),
) -> AskResponse:
    return await workflow.ask(payload)


@api_router.post(
    "/ask/stream",
    summary="Ask with streaming (SSE)",
    description=(
        "Streams the answer token-by-token as Server-Sent Events. "
        "Event types: `sources` (JSON array of citations), `token` (text chunk), "
        "`error` (non-fatal LLM error), `done` (final metrics payload)."
    ),
)
async def ask_stream(
    payload: AskRequest,
    workflow: WorkflowService = Depends(get_workflow_service),
) -> StreamingResponse:
    return StreamingResponse(
        workflow.ask_stream(payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.post("/ingest", response_model=IngestResponse)
async def ingest(
    payload: IngestRequest,
    workflow: WorkflowService = Depends(get_workflow_service),
) -> IngestResponse:
    if payload.contextual_enrichment:
        result = await workflow.ingest_with_context(payload)
        return ContextualIngestResponse(**result)
    return workflow.ingest(payload)


@api_router.post(
    "/eval/run",
    response_model=EvalResponse,
    summary="RAG-Qualitätsevaluation (RAGAS-Stil)",
    description=(
        "Bewertet eine RAG-Antwort mittels Claude-Richter nach zwei Dimensionen: "
        "**Faithfulness** (sind alle Aussagen durch den Kontext belegt?) und "
        "**Relevancy** (beantwortet die Antwort die Frage direkt?). "
        "Erfordert einen konfigurierten LLM-Client."
    ),
)
async def eval_run(
    payload: EvalRequest,
    workflow: WorkflowService = Depends(get_workflow_service),
) -> EvalResponse:
    result = await workflow.evaluate_rag(
        question=payload.question,
        answer=payload.answer,
        contexts=payload.contexts,
    )
    return EvalResponse(**result)


@api_router.get(
    "/debug/retrieval",
    response_model=RetrievalDebugResponse,
    summary="Retrieval-Diagnose",
    description=(
        "Zeigt detaillierte Retrieval-Ergebnisse für eine Suchanfrage: Rang, Score, "
        "Retrieval-Modus (hybrid_rrf / dense / lexical) und Metadaten pro Chunk. "
        "Nützlich zur Diagnose von Retrieval-Problemen und Score-Kalibrierung."
    ),
)
async def debug_retrieval(
    q: str = Query(min_length=3, max_length=500, description="Suchanfrage"),
    workflow: WorkflowService = Depends(get_workflow_service),
) -> RetrievalDebugResponse:
    result = workflow.debug_retrieval(q)
    return RetrievalDebugResponse(**result)


@api_router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    workflow: WorkflowService = Depends(get_workflow_service),
) -> MetricsResponse:
    return MetricsResponse(**workflow.metrics_snapshot())


@api_router.get("/audit-logs", response_model=AuditLogsResponse)
async def audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    workflow: WorkflowService = Depends(get_workflow_service),
) -> AuditLogsResponse:
    return AuditLogsResponse(entries=workflow.recent_audit_logs(limit=limit))

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router, ui_router
from app.core.errors import AppError, app_error_handler, unhandled_exception_handler
from app.core.logging import configure_logging
from app.core.settings import Settings
from app.rag.llm import ClaudeInferenceClient
from app.rag.service import KnowledgeBaseService
from app.rag.supabase_store import SupabaseKnowledgeStore
from app.security.audit import AuditLogger
from app.workflow.service import WorkflowService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    logger = configure_logging()

    remote_store = None
    if settings.supabase_enabled:
        remote_store = SupabaseKnowledgeStore(
            project_url=str(settings.supabase_url),
            service_role_key=str(settings.supabase_service_role_key),
            table_name=settings.supabase_documents_table,
        )

    knowledge_base = KnowledgeBaseService(
        base_dir=settings.knowledge_base_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        default_top_k=settings.retrieval_top_k,
        openai_api_key=settings.openai_api_key,
        openai_embedding_model=settings.openai_embedding_model,
        remote_store=remote_store,
        hybrid_enabled=settings.hybrid_search_enabled,
    )

    llm: ClaudeInferenceClient | None = None
    if settings.anthropic_api_key:
        try:
            llm = ClaudeInferenceClient(
                api_key=settings.anthropic_api_key,
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
            )
            logger.info("Claude LLM client initialised", extra={"model": settings.llm_model})
        except RuntimeError as exc:
            logger.warning("Claude client could not be initialised: %s — falling back to template responses", exc)

    audit_logger = AuditLogger(settings.audit_log_file)
    workflow_service = WorkflowService(
        knowledge_base=knowledge_base,
        audit_logger=audit_logger,
        llm=llm,
    )

    app.state.settings = settings
    app.state.logger = logger
    app.state.knowledge_base = knowledge_base
    app.state.audit_logger = audit_logger
    app.state.workflow_service = workflow_service
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Autohaus AI RAG Agent Backend",
        version="0.2.0",
        description=(
            "Privacy-aware RAG backend for automotive dealership AI workflows. "
            "Features hybrid RRF retrieval, Claude-powered synthesis, "
            "multi-turn conversation history, streaming SSE, and full agent tracing."
        ),
        lifespan=lifespan,
    )
    settings = Settings()
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
    app.include_router(ui_router)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    return app


app = create_app()

from __future__ import annotations

from fastapi import Request

from app.core.settings import Settings
from app.rag.service import KnowledgeBaseService
from app.security.audit import AuditLogger
from app.workflow.service import WorkflowService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_knowledge_base(request: Request) -> KnowledgeBaseService:
    return request.app.state.knowledge_base


def get_audit_logger(request: Request) -> AuditLogger:
    return request.app.state.audit_logger


def get_workflow_service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


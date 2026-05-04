from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ARIA – Automotive Retrieval Intelligence Assistant"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_prefix: str = "/api/v1"
    knowledge_base_path: str = "data/knowledge_base"
    audit_log_path: str = "logs/audit.jsonl"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_documents_table: str = "rag_documents"
    retrieval_top_k: int = Field(default=4, ge=1, le=10)
    chunk_size: int = Field(default=700, ge=200, le=2000)
    chunk_overlap: int = Field(default=120, ge=0, le=400)
    max_audit_entries: int = Field(default=100, ge=10, le=500)
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-4-7"
    llm_max_tokens: int = Field(default=1024, ge=256, le=4096)
    hybrid_search_enabled: bool = True
    session_history_turns: int = Field(default=3, ge=0, le=10)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @cached_property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return self.project_root / path

    @property
    def knowledge_base_dir(self) -> Path:
        return self.resolve_path(self.knowledge_base_path)

    @property
    def audit_log_file(self) -> Path:
        return self.resolve_path(self.audit_log_path)

    @property
    def static_dir(self) -> Path:
        return self.project_root / "app" / "static"

    @property
    def template_dir(self) -> Path:
        return self.project_root / "app" / "templates"

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


def get_settings() -> Settings:
    return Settings()

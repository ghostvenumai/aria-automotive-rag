from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.rag.models import RetrievedSource


@dataclass(slots=True)
class AskWorkflowState:
    request_id: str
    raw_input: str
    redacted_input: str = ""
    intent: str = "general"
    answer: str = ""
    confidence: float = 0.0
    human_review: bool = False
    pii_types: list[str] = field(default_factory=list)
    sources: list[RetrievedSource] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    fallback_used: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    # LLM-reformulated query for optimised retrieval (QueryRewriterAgent output)
    rewritten_query: str = ""
    # Hallucination detection results (GroundingVerifierAgent output)
    hallucination_risk: float = 0.0
    unsupported_claims: list[str] = field(default_factory=list)
    # Conversation history passed in per request (serialised {role, content} dicts)
    history: list[dict[str, Any]] = field(default_factory=list)
    # LLM token usage captured after synthesis
    llm_usage: dict[str, Any] = field(default_factory=dict)


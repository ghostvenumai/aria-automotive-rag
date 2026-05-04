from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Document:
    doc_id: str
    title: str
    text: str
    source_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    term_weights: dict[str, float] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass(slots=True)
class RetrievedSource:
    source_id: str
    title: str
    score: float
    snippet: str
    metadata: dict[str, Any] = field(default_factory=dict)


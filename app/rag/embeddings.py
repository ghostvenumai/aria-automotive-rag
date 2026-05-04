from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]{2,}")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def compute_term_weights(text: str) -> dict[str, float]:
    counts = Counter(tokenize(text))
    total = sum(counts.values()) or 1
    return {term: count / total for term, count in counts.items()}


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


class OpenAIEmbeddingClient:
    def __init__(self, *, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError("Optional openai dependency is not installed.") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response: Any = self._client.embeddings.create(model=self._model, input=texts)
        return [list(item.embedding) for item in response.data]

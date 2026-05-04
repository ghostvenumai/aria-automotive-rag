from __future__ import annotations

from app.rag.embeddings import compute_term_weights, cosine_similarity, tokenize
from app.rag.models import Chunk, RetrievedSource


def lexical_score(query: str, chunk: Chunk) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    if not chunk.term_weights:
        chunk.term_weights = compute_term_weights(chunk.text)

    overlap_score = 0.0
    for token in query_tokens:
        overlap_score += chunk.term_weights.get(token, 0.0)

    coverage_bonus = len({token for token in query_tokens if token in chunk.term_weights}) / len(query_tokens)
    return round(overlap_score + (0.15 * coverage_bonus), 6)


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score. Higher rank (lower index) → higher score."""
    return 1.0 / (k + rank + 1)


def search_chunks(query: str, chunks: list[Chunk], *, top_k: int) -> list[RetrievedSource]:
    """Lexical-only search (BM25-style term overlap)."""
    scored = []
    for chunk in chunks:
        score = lexical_score(query, chunk)
        if score <= 0.0:
            continue
        scored.append(
            RetrievedSource(
                source_id=chunk.chunk_id,
                title=chunk.title,
                score=score,
                snippet=chunk.text.replace("\n", " ")[:220].strip(),
                metadata={"doc_id": chunk.doc_id, **chunk.metadata},
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]


def dense_search_chunks(
    query_embedding: list[float],
    chunks: list[Chunk],
    *,
    top_k: int,
) -> list[RetrievedSource]:
    """Dense vector search using cosine similarity."""
    scored = []
    for chunk in chunks:
        if chunk.embedding is None:
            continue
        score = max(cosine_similarity(query_embedding, chunk.embedding), 0.0)
        if score <= 0.0:
            continue
        scored.append(
            RetrievedSource(
                source_id=chunk.chunk_id,
                title=chunk.title,
                score=round(score, 6),
                snippet=chunk.text.replace("\n", " ")[:220].strip(),
                metadata={"doc_id": chunk.doc_id, **chunk.metadata},
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:top_k]


def hybrid_search(
    query: str,
    query_embedding: list[float] | None,
    chunks: list[Chunk],
    *,
    top_k: int,
    rrf_k: int = 60,
) -> list[RetrievedSource]:
    """Hybrid retrieval: fuses lexical and dense rankings via Reciprocal Rank Fusion (RRF).

    RRF is provider-agnostic, requires no score normalisation, and consistently
    outperforms linear combination across benchmark datasets (Cormack et al., 2009).
    Falls back to lexical-only when embeddings are unavailable.
    """
    candidate_pool = top_k * 4  # oversample before fusion cut

    lexical_results = search_chunks(query, chunks, top_k=candidate_pool)
    lexical_ranks: dict[str, int] = {r.source_id: i for i, r in enumerate(lexical_results)}

    # Build a quick lookup for the full RetrievedSource objects
    sources_by_id: dict[str, RetrievedSource] = {r.source_id: r for r in lexical_results}

    if query_embedding:
        dense_results = dense_search_chunks(query_embedding, chunks, top_k=candidate_pool)
        dense_ranks: dict[str, int] = {r.source_id: i for i, r in enumerate(dense_results)}
        for r in dense_results:
            sources_by_id.setdefault(r.source_id, r)
    else:
        dense_ranks = {}

    all_ids = set(lexical_ranks) | set(dense_ranks)
    fused: list[tuple[float, str]] = []
    for sid in all_ids:
        lex_rank = lexical_ranks.get(sid, candidate_pool)
        den_rank = dense_ranks.get(sid, candidate_pool)
        fused_score = _rrf_score(lex_rank, rrf_k) + _rrf_score(den_rank, rrf_k)
        fused.append((fused_score, sid))

    fused.sort(key=lambda t: t[0], reverse=True)

    results: list[RetrievedSource] = []
    for fused_score, sid in fused[:top_k]:
        source = sources_by_id[sid]
        results.append(
            RetrievedSource(
                source_id=source.source_id,
                title=source.title,
                score=round(fused_score, 6),
                snippet=source.snippet,
                metadata={**source.metadata, "retrieval_mode": "hybrid_rrf"},
            )
        )
    return results

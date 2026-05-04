# Architecture Overview

## System Goals

- Showcase backend-oriented AI systems engineering rather than a toy chatbot.
- Run fully offline by default while supporting optional OpenAI embeddings.
- Keep privacy boundaries explicit through PII redaction and redacted audit logs.
- Make orchestration traceable through agent-level decision traces and metrics.

## Project Structure

- `app/api`: HTTP routes, dependency accessors, response contracts.
- `app/core`: settings, logging, exception types and framework bootstrapping support.
- `app/rag`: document loading, chunking, retrieval and ingestion.
- `app/security`: PII redaction and audit log persistence.
- `app/workflow`: internal agent orchestration and runtime metrics.
- `app/templates` and `app/static`: lightweight demo UI.
- `data/knowledge_base`: dealership-oriented seed documents.
- `tests`: API, workflow, retrieval and privacy verification.

## Data Flow

1. A user sends `POST /api/v1/ask`.
2. `PrivacyGuardAgent` redacts the raw text for logging and flags sensitive PII classes.
3. `IntentClassifierAgent` assigns a dealership intent.
4. `RetrieverAgent` queries the local knowledge base and returns scored sources.
5. `ResponseComposerAgent` builds the final answer using retrieved evidence.
6. `QualityGuardAgent` sets confidence and human-review requirements.
7. `MetricsAgent` records latency, fallback mode, source count and confidence.
8. `AuditLogger` stores only redacted input plus non-secret metadata.

## API Contracts

- `GET /health`: application status, retrieval mode, indexed counts.
- `POST /api/v1/ask`: question in, answer with intent, confidence, sources, trace and metrics out.
- `POST /api/v1/ingest`: add internal dealership documents to the knowledge base.
- `GET /api/v1/metrics`: aggregate latency, confidence and fallback metrics.
- `GET /api/v1/audit-logs`: recent redacted audit entries.
- `GET /`: demo UI.

## RAG Strategy

- Default mode uses a deterministic local lexical retriever with chunk-level scoring.
- If `OPENAI_API_KEY` is set and the optional dependency is installed, the service can request embeddings.
- The backend downgrades gracefully to local retrieval on any embedding failure and records the fallback.

## Security Notes

- No endpoint persists raw user questions to audit storage.
- The audit logger drops keys that look like secrets and redacts secret-like values recursively.
- Seed data is synthetic and dealership-oriented; it contains no real customer information.

## Maintainability Notes

- `WorkflowService` acts as the integration seam between HTTP and internal agents.
- Retrieval and privacy are isolated so they can be replaced independently.
- The UI is static and framework-free to keep the repository backend-focused.


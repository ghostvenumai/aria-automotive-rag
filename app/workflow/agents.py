from __future__ import annotations

from time import perf_counter
from typing import Any

from app.rag.embeddings import tokenize
from app.rag.llm import QUERY_REWRITER_SYSTEM, ClaudeInferenceClient, build_rag_messages
from app.rag.models import RetrievedSource
from app.rag.service import KnowledgeBaseService
from app.security.pii import PIIRedactor
from app.workflow.state import AskWorkflowState


def _trace_step(
    agent: str,
    decision: str,
    rationale: str,
    started_at: float,
    **metadata: object,
) -> dict[str, object]:
    return {
        "agent": agent,
        "decision": decision,
        "rationale": rationale,
        "latency_ms": round((perf_counter() - started_at) * 1000, 3),
        "metadata": metadata,
    }


class IntentClassifierAgent:
    INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("privacy_request", ("privacy", "dsgvo", "gdpr", "daten löschen", "daten entfernen", "delete my data", "remove my data", "kontaktdaten")),
        ("vehicle_inventory", ("bestand", "verfügbar", "suv", "limousine", "lager", "fahrzeug", "auto", "modell", "inventory", "available", "stock", "vehicle", "car", "model")),
        ("financing", ("finanzierung", "finanzieren", "leasing", "rate", "monatlich", "kredit", "anzahlung", "laufzeit", "finance", "financing", "lease", "monthly", "installment", "loan")),
        ("service_booking", ("service", "werkstatt", "wartung", "inspektion", "reparatur", "termin", "ölwechsel", "maintenance", "inspection", "repair", "appointment", "oil change")),
        ("trade_in", ("inzahlungnahme", "eintausch", "bewertung", "verkaufen", "trade-in", "trade in", "valuation", "resale", "sell my car")),
        ("warranty", ("garantie", "gewährleistung", "deckung", "warranty", "coverage", "guarantee", "extended warranty")),
    )

    def classify(self, state: AskWorkflowState) -> dict[str, object]:
        started_at = perf_counter()
        lowered = state.raw_input.lower()
        best_intent = "general"
        best_score = 0
        for intent, keywords in self.INTENT_RULES:
            score = sum(1 for keyword in keywords if keyword in lowered)
            if score > best_score:
                best_intent = intent
                best_score = score
        return _trace_step(
            "IntentClassifierAgent",
            best_intent,
            "Domänen-Keywords mit Autohaus-Intents abgeglichen.",
            started_at,
            keyword_hits=best_score,
        )


class PrivacyGuardAgent:
    def __init__(self) -> None:
        self.redactor = PIIRedactor()

    def inspect(self, state: AskWorkflowState) -> dict[str, object]:
        started_at = perf_counter()
        result = self.redactor.redact(state.raw_input)
        state.redacted_input = result.redacted_text
        state.pii_types = result.pii_types
        return _trace_step(
            "PrivacyGuardAgent",
            "redigiert" if result.redaction_count else "sauber",
            "Sensible Muster erkannt und für das Audit-Log anonymisiert.",
            started_at,
            pii_types=result.pii_types,
            redaction_count=result.redaction_count,
        )


class QueryRewriterAgent:
    """Reformulates the user query for optimal vector retrieval.

    Handles German compound words, abbreviations, and colloquial phrasing that
    would otherwise cause low lexical overlap with the knowledge base.
    Falls back to the original query when no LLM is available.
    """

    async def rewrite(
        self,
        state: AskWorkflowState,
        llm: ClaudeInferenceClient | None,
    ) -> dict[str, object]:
        started_at = perf_counter()

        if llm is None:
            state.rewritten_query = state.raw_input
            return _trace_step(
                "QueryRewriterAgent",
                "übersprungen",
                "Kein LLM verfügbar – Originalanfrage wird direkt verwendet.",
                started_at,
            )

        messages = [{"role": "user", "content": f"Kundenanfrage: {state.raw_input}"}]
        try:
            # max_tokens=80: rewriter only needs a short keyword phrase, not a full answer
            response = await llm.complete(messages=messages, system=QUERY_REWRITER_SYSTEM, max_tokens=80)
            rewritten = response.text.strip()
            state.rewritten_query = rewritten if rewritten else state.raw_input
        except Exception as exc:
            state.rewritten_query = state.raw_input
            return _trace_step(
                "QueryRewriterAgent",
                "fehler_fallback",
                f"Umformulierung fehlgeschlagen ({exc!s}) – Originalanfrage verwendet.",
                started_at,
            )

        changed = state.rewritten_query != state.raw_input
        return _trace_step(
            "QueryRewriterAgent",
            "umformuliert" if changed else "unverändert",
            "Anfrage für optimale Vektordatenbanksuche aufbereitet.",
            started_at,
            original=state.raw_input[:120],
            umformuliert=state.rewritten_query[:120],
        )


class RetrieverAgent:
    async def retrieve(
        self,
        state: AskWorkflowState,
        knowledge_base: KnowledgeBaseService,
    ) -> dict[str, object]:
        started_at = perf_counter()
        # Use the LLM-rewritten query when available; fall back to raw input
        retrieval_query = state.rewritten_query or state.raw_input
        state.sources = knowledge_base.search(retrieval_query)
        state.fallback_used = knowledge_base.embedding_mode == "local"
        return _trace_step(
            "RetrieverAgent",
            "quellen_gefunden" if state.sources else "keine_quellen",
            "Wissensdatenbank via hybridem RRF-Retrieval abgefragt.",
            started_at,
            source_count=len(state.sources),
            embedding_mode=knowledge_base.embedding_mode,
            query_used=retrieval_query[:120],
        )


class ResponseComposerAgent:
    """Synthesises a grounded answer using Claude.

    Falls back to a template-based response when no LLM client is available,
    so the service remains functional in environments without an Anthropic key.
    """

    async def compose(
        self,
        state: AskWorkflowState,
        llm: ClaudeInferenceClient | None,
    ) -> dict[str, object]:
        started_at = perf_counter()

        # LLM runs whenever it's available — human_review means "also escalate", not "skip LLM"
        if llm is not None:
            try:
                messages = build_rag_messages(
                    question=state.raw_input,
                    sources=state.sources,
                    history=state.history,
                )
                response = await llm.complete(messages=messages)
                state.answer = response.text
                state.llm_usage = {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "model": response.model,
                }
                return _trace_step(
                    "ResponseComposerAgent",
                    "llm_synthetisiert",
                    "Antwort von Claude aus dem abgerufenen Kontext synthetisiert.",
                    started_at,
                    source_count=len(state.sources),
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
            except Exception as exc:
                state.answer = self._template_answer(state.intent, state.sources)
                return _trace_step(
                    "ResponseComposerAgent",
                    "llm_fehler_fallback",
                    f"LLM-Aufruf fehlgeschlagen ({exc!s}) – Template-Antwort verwendet.",
                    started_at,
                    source_count=len(state.sources),
                )

        # No LLM available — template fallback
        state.answer = self._template_answer(state.intent, state.sources)
        if state.pii_types:
            state.answer += " Personenbezogene Daten wurden aus dem Audit-Log entfernt."
        return _trace_step(
            "ResponseComposerAgent",
            "template_erstellt",
            "Template-Antwort verwendet – kein LLM konfiguriert.",
            started_at,
            source_count=len(state.sources),
        )

    def _template_answer(self, intent: str, sources: list[RetrievedSource]) -> str:
        if not sources:
            return (
                "Zu Ihrer Anfrage konnten keine relevanten Informationen in der "
                "Wissensdatenbank gefunden werden. Bitte wenden Sie sich an einen "
                "unserer Verkaufs- oder Servicemitarbeiter für eine verbindliche Auskunft."
            )
        lead = {
            "vehicle_inventory": "Aus dem aktuellen Fahrzeugbestand ergibt sich Folgendes:",
            "financing": "Die Finanzierungsoptionen in unserer Wissensdatenbank umfassen Folgendes:",
            "service_booking": "Laut unserem Serviceleitfaden empfehlen wir Folgendes:",
            "trade_in": "Zu Ihrer Inzahlungnahme-Anfrage haben wir folgende Informationen:",
            "warranty": "Die Garantiebedingungen besagen Folgendes:",
            "general": "Aus unserer Wissensdatenbank ergibt sich Folgendes:",
        }.get(intent, "Aus unserer Wissensdatenbank ergibt sich Folgendes:")
        snippets = " ".join(source.snippet for source in sources[:2])
        return f"{lead} {snippets}"


class GroundingVerifierAgent:
    """Detects hallucinations by checking each answer sentence against retrieved sources.

    Uses token overlap: a sentence is considered grounded if at least 25 % of its
    meaningful tokens appear in at least one source snippet. Sentences with fewer than
    5 meaningful tokens are skipped (transition phrases, greetings, etc.).

    This runs entirely offline — no extra LLM call, no added latency budget.
    """

    _STOP_WORDS = frozenset({
        "die", "der", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
        "eines", "und", "oder", "aber", "auch", "nicht", "ist", "sind", "war", "hat",
        "haben", "wird", "werden", "von", "zu", "in", "an", "auf", "mit", "für",
        "aus", "bei", "nach", "über", "unter", "vor", "durch", "als", "wie", "sich",
        "sie", "er", "wir", "ich", "es", "du", "ihr", "uns", "mir", "ihm", "ihn",
        "the", "a", "an", "and", "or", "is", "are", "was", "has", "have", "will",
        "be", "of", "to", "in", "on", "at", "with", "for", "from", "by", "as",
        "that", "this", "it", "we", "you", "he", "she", "they", "not",
    })

    def _meaningful_tokens(self, text: str) -> set[str]:
        return {t for t in tokenize(text) if t not in self._STOP_WORDS and len(t) > 2}

    def _is_grounded(self, sentence: str, source_token_pool: set[str]) -> bool:
        tokens = self._meaningful_tokens(sentence)
        if len(tokens) < 5:
            return True  # Too short to verify meaningfully
        overlap = len(tokens & source_token_pool) / len(tokens)
        return overlap >= 0.25

    def _split_sentences(self, text: str) -> list[str]:
        import re
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if len(p.strip()) > 20]

    def verify(self, state: AskWorkflowState) -> dict[str, object]:
        started_at = perf_counter()

        if not state.answer or not state.sources:
            state.hallucination_risk = 0.0
            state.unsupported_claims = []
            return _trace_step(
                "GroundingVerifierAgent",
                "übersprungen",
                "Keine Antwort oder keine Quellen vorhanden – Verifikation nicht möglich.",
                started_at,
            )

        # Build a combined token pool from all retrieved source snippets
        source_token_pool: set[str] = set()
        for source in state.sources:
            source_token_pool.update(self._meaningful_tokens(source.snippet))

        sentences = self._split_sentences(state.answer)
        if not sentences:
            state.hallucination_risk = 0.0
            state.unsupported_claims = []
            return _trace_step(
                "GroundingVerifierAgent",
                "sauber",
                "Antwort vollständig durch abgerufene Quellen gedeckt.",
                started_at,
                sentences_checked=0,
                ungrounded=0,
            )

        ungrounded = [s for s in sentences if not self._is_grounded(s, source_token_pool)]
        risk = round(len(ungrounded) / len(sentences), 3)

        state.hallucination_risk = risk
        state.unsupported_claims = ungrounded

        decision = (
            "halluzinationsrisiko_hoch" if risk > 0.5
            else "halluzinationsrisiko_mittel" if risk > 0.0
            else "vollständig_belegt"
        )
        rationale = (
            f"{len(ungrounded)} von {len(sentences)} Sätzen nicht durch Quellen gedeckt "
            f"(Risiko: {risk:.0%})."
            if ungrounded
            else f"Alle {len(sentences)} geprüften Sätze durch abgerufene Quellen belegt."
        )
        return _trace_step(
            "GroundingVerifierAgent",
            decision,
            rationale,
            started_at,
            sentences_checked=len(sentences),
            ungrounded_count=len(ungrounded),
            hallucination_risk=risk,
        )


class QualityGuardAgent:
    def evaluate(self, state: AskWorkflowState) -> dict[str, object]:
        started_at = perf_counter()
        top_score = state.sources[0].score if state.sources else 0.0

        # Confidence: blend retrieval quality with LLM availability signal
        has_llm_answer = state.llm_usage.get("output_tokens", 0) > 0
        base_confidence = min(1.0, round(top_score * 3.5, 3))
        confidence = min(base_confidence + (0.10 if has_llm_answer else 0.0), 1.0)

        human_review = (
            not state.sources
            or confidence < 0.45
            or "credit_card" in state.pii_types
            or state.intent == "privacy_request"
        )
        if human_review and state.sources:
            confidence = min(confidence, 0.55)

        state.confidence = round(confidence, 3)
        state.human_review = human_review
        rationale = (
            "Geringe Evidenzabdeckung oder sensible Inhalte erfordern menschliche Prüfung."
            if human_review
            else "Evidenzqualität und LLM-Konfidenz ausreichend für automatische Antwort."
        )
        return _trace_step(
            "QualityGuardAgent",
            "menschliche_pruefung" if human_review else "automatische_antwort",
            rationale,
            started_at,
            top_source_score=top_score,
            confidence=state.confidence,
            llm_synthetisiert=has_llm_answer,
        )


class MetricsAgent:
    def finalize(
        self,
        state: AskWorkflowState,
        *,
        started_at: float,
        source_count: int,
    ) -> dict[str, object]:
        total_latency_ms = round((perf_counter() - started_at) * 1000, 3)
        state.metrics = {
            "latency_ms": total_latency_ms,
            "source_count": source_count,
            "fallback_used": state.fallback_used,
            "pii_detected": bool(state.pii_types),
            "llm_input_tokens": state.llm_usage.get("input_tokens", 0),
            "llm_output_tokens": state.llm_usage.get("output_tokens", 0),
            "llm_model": state.llm_usage.get("model", "keins"),
        }
        return {
            "agent": "MetricsAgent",
            "decision": "erfasst",
            "rationale": "Betriebs- und Kostenmetriken für diese Anfrage protokolliert.",
            "latency_ms": 0.0,
            "metadata": state.metrics,
        }

from __future__ import annotations

from dataclasses import dataclass

from app.security.pii import PIIRedactor


@dataclass
class RedactionResult:
    redacted_text: str
    pii_entities: list[str]
    human_review_required: bool


def redact_pii(text: str) -> RedactionResult:
    result = PIIRedactor().redact(text)
    human_review_required = any(entity in {"credit_card", "iban"} for entity in result.pii_types)
    return RedactionResult(
        redacted_text=result.redacted_text,
        pii_entities=result.pii_types,
        human_review_required=human_review_required,
    )

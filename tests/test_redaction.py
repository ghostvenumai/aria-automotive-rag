from app.security.redaction import redact_pii


def test_redact_pii_masks_sensitive_entities() -> None:
    result = redact_pii(
        "Contact jane.doe@example.com or +49 170 1234567 with card 4111111111111111."
    )

    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert "[REDACTED_CREDIT_CARD]" in result.redacted_text
    assert "credit_card" in result.pii_entities
    assert result.human_review_required is True


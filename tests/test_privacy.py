from __future__ import annotations

from app.security.pii import PIIRedactor


def test_pii_redaction_masks_email_phone_and_vin() -> None:
    redactor = PIIRedactor()

    result = redactor.redact(
        "Contact me at jane.doe@example.com or +49 170 1234567 about VIN WBA3A5C50CF123456."
    )

    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert "[REDACTED_VIN]" in result.redacted_text
    assert set(result.pii_types) == {"email", "phone", "vin"}


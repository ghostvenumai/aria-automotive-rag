from __future__ import annotations

from app.security.pii import PIIRedactor


def test_pii_redaction_masks_email_phone_and_svnr() -> None:
    redactor = PIIRedactor()

    result = redactor.redact(
        "Meine E-Mail ist jana.beispiel@example.com, Telefon +49 170 1234567, "
        "Sozialversicherungsnummer 12 190878 M 512."
    )

    assert "[REDACTED_EMAIL]" in result.redacted_text
    assert "[REDACTED_PHONE]" in result.redacted_text
    assert "[REDACTED_SVNR]" in result.redacted_text
    assert set(result.pii_types) == {"email", "phone", "svnr"}


def test_pii_redaction_masks_iban() -> None:
    redactor = PIIRedactor()

    result = redactor.redact(
        "Bitte überweist mein Gehalt künftig auf DE89370400440532013000."
    )

    assert "[REDACTED_IBAN]" in result.redacted_text
    assert "iban" in result.pii_types

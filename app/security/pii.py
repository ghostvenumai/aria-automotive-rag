from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class RedactionResult:
    redacted_text: str
    pii_types: list[str]
    redaction_count: int


class PIIRedactor:
    PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
        # Deutsche Sozialversicherungsnummer: 12 190878 M 512 (mit/ohne Leerzeichen)
        ("svnr", re.compile(r"\b\d{2}\s?\d{6}\s?[A-Z]\s?\d{3}\b")),
        ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
        ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
        (
            "phone",
            re.compile(
                r"(?<!\w)(?:\+|00)?\d{1,4}(?:[\s.-]\(?\d{2,4}\)?){1,3}[\s.-]?\d{2,8}(?!\w)"
            ),
        ),
    )

    def redact(self, text: str) -> RedactionResult:
        redacted = text
        pii_types: list[str] = []
        redaction_count = 0

        for pii_type, pattern in self.PATTERNS:
            replacement = f"[REDACTED_{pii_type.upper()}]"
            redacted, replacements = pattern.subn(replacement, redacted)
            if replacements:
                pii_types.append(pii_type)
                redaction_count += replacements

        return RedactionResult(
            redacted_text=redacted,
            pii_types=pii_types,
            redaction_count=redaction_count,
        )

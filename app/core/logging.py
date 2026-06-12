from __future__ import annotations

import logging
import re


class SecretRedactionFilter(logging.Filter):
    _secret_pattern = re.compile(r"sk-[A-Za-z0-9_-]{12,}")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._secret_pattern.sub("[REDACTED_SECRET]", record.msg)
        if record.args:
            record.args = tuple(
                self._secret_pattern.sub("[REDACTED_SECRET]", str(arg)) for arg in record.args
            )
        return True


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("klara")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    handler.addFilter(SecretRedactionFilter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


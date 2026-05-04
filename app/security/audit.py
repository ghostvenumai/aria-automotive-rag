from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_file: Path) -> None:
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, nested_value in value.items():
                lowered = key.lower()
                if any(marker in lowered for marker in ("token", "secret", "password", "api_key", "authorization")):
                    continue
                sanitized[key] = self._sanitize_value(nested_value)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        if isinstance(value, str) and value.startswith("sk-"):
            return "[REDACTED_SECRET]"
        return value

    def log_event(
        self,
        *,
        event_type: str,
        request_id: str,
        redacted_input: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "request_id": request_id,
            "redacted_input": redacted_input,
            "metadata": self._sanitize_value(metadata or {}),
        }
        with self._lock:
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=True))
                handle.write("\n")

    def read_recent(self, *, limit: int) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []
        with self._lock:
            lines = self.log_file.read_text(encoding="utf-8").splitlines()
        recent = lines[-limit:]
        return [json.loads(line) for line in reversed(recent) if line.strip()]


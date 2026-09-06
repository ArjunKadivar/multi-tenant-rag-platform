"""
Structured, JSON-formatted logging so log aggregators (ELK, Loki, Datadog)
can index fields directly instead of regex-parsing plain text.
"""
import logging
import sys
from datetime import datetime, timezone

import json


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Extra structured fields attached via `logger.info(..., extra={"tenant_id": ...})`
        for key in ("tenant_id", "request_id", "path", "duration_ms", "status_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

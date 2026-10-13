"""Structured logging setup for the application."""
from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Optional

from app.config import get_settings

# Request-scoped context propagated to every log record. Set by middleware and
# cleared at the end of each request, so nested logs carry request_id/user_id.
_request_id: contextvars.ContextVar = contextvars.ContextVar("request_id", default=None)
_user_id: contextvars.ContextVar = contextvars.ContextVar("user_id", default=None)
_request_path: contextvars.ContextVar = contextvars.ContextVar("request_path", default=None)
_request_method: contextvars.ContextVar = contextvars.ContextVar("request_method", default=None)
_request_duration_ms: contextvars.ContextVar = contextvars.ContextVar("request_duration_ms", default=None)


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Bind context fields for the current async task."""
    if request_id is not None:
        _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)
    if path is not None:
        _request_path.set(path)
    if method is not None:
        _request_method.set(method)
    if duration_ms is not None:
        _request_duration_ms.set(duration_ms)


def clear_request_context() -> None:
    for var in (_request_id, _user_id, _request_path, _request_method, _request_duration_ms):
        var.set(None)


class RequestContextFilter(logging.Filter):
    """Attach the current request context to every log record as `extra_fields`."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = {
            "request_id": _request_id.get(),
            "user_id": _user_id.get(),
            "path": _request_path.get(),
            "method": _request_method.get(),
            "duration_ms": _request_duration_ms.get(),
        }
        record.context = {k: v for k, v in context.items() if v is not None}
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        context = getattr(record, "context", None)
        if context:
            payload["context"] = context
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload["extra"] = extra
        return json.dumps(payload, default=str)


class TextContextFormatter(logging.Formatter):
    """Console formatter that appends request context when present."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context = getattr(record, "context", None)
        if not context:
            return base
        suffix = " ".join(f"{k}={v}" for k, v in context.items())
        return f"{base} [{suffix}]"


def configure_logging(level: Optional[str] = None, as_json: Optional[bool] = None) -> None:
    settings = get_settings()
    log_level = (level or settings.LOG_LEVEL).upper()
    log_json = settings.LOG_JSON if as_json is None else as_json

    if log_json:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = TextContextFormatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    root = logging.getLogger()
    root.setLevel(log_level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    if hasattr(sys.stdout, "reconfigure"):  # Python 3.7+; avoids UnicodeEncodeError on cp1252 consoles
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    stream.setFormatter(formatter)
    stream.addFilter(RequestContextFilter())
    root.addHandler(stream)

    for noisy in ("uvicorn.access", "boto3", "botocore", "s3transfer", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def bind_context(logger: logging.Logger, **fields: object) -> logging.LoggerAdapter:
    """Attach extra structured context to a logger (e.g. request_id, user_id)."""
    return logging.LoggerAdapter(logger, {"extra_fields": fields})

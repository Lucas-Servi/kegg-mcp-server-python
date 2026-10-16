"""Structured JSON logging to stderr.

All records go to stderr; stdout is reserved for MCP stdio transport framing.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_RESERVED_LOG_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class _JsonFormatter(logging.Formatter):
    def __init__(self, *, log_tracebacks: bool = False) -> None:
        super().__init__()
        self._log_tracebacks = log_tracebacks

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            if self._log_tracebacks:
                payload["exc"] = self.formatException(record.exc_info)
            else:
                exc_type, exc_val, _ = record.exc_info
                payload["exc_type"] = exc_type.__name__ if exc_type else None
                payload["exc_msg"] = str(exc_val) if exc_val else None
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", log_tracebacks: bool = False) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter(log_tracebacks=log_tracebacks))

    logger = logging.getLogger("kegg_mcp_server")
    try:
        logger.setLevel(level.upper())
    except ValueError:
        logger.setLevel("INFO")  # unknown level: don't crash startup over verbosity
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    # httpx logs every full request URL at INFO, bypassing our redacted request log.
    logging.getLogger("httpx").setLevel(logging.WARNING)

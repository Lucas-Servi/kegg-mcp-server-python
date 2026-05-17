"""Structured JSON logging to stderr.

All records go to stderr; stdout is reserved for MCP stdio transport framing.
"""

from __future__ import annotations

import json
import logging
import os
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


_LOG_TRACEBACKS = os.getenv("KEGG_MCP_LOG_TRACEBACKS", "0") == "1"


class _JsonFormatter(logging.Formatter):
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
            if _LOG_TRACEBACKS:
                payload["exc"] = self.formatException(record.exc_info)
            else:
                exc_type, exc_val, _ = record.exc_info
                payload["exc_type"] = exc_type.__name__ if exc_type else None
                payload["exc_msg"] = str(exc_val) if exc_val else None
        return json.dumps(payload, default=str)


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())

    logger = logging.getLogger("kegg_mcp_server")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

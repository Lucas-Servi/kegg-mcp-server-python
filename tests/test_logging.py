"""Tests for the structured JSON stderr logger."""

from __future__ import annotations

import io
import json
import logging
import sys

import pytest

from kegg_mcp_server.logging import setup_logging


@pytest.fixture(autouse=True)
def _reset_logger() -> None:
    logger = logging.getLogger("kegg_mcp_server")
    original_level = logger.level
    original_handlers = logger.handlers[:]
    original_propagate = logger.propagate
    yield
    logger.level = original_level
    logger.handlers[:] = original_handlers
    logger.propagate = original_propagate


def test_setup_writes_json_to_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    setup_logging()
    logging.getLogger("kegg_mcp_server.client").warning(
        "kegg http error", extra={"path": "/get/x", "status": 500}
    )
    out = buf.getvalue().strip()
    assert out, "expected a log line"
    payload = json.loads(out.splitlines()[-1])
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "kegg_mcp_server.client"
    assert payload["msg"] == "kegg http error"
    assert payload["path"] == "/get/x"
    assert payload["status"] == 500


def test_respects_log_level_env(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    setup_logging()
    logging.getLogger("kegg_mcp_server").warning("ignored")
    logging.getLogger("kegg_mcp_server").error("visible")
    lines = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["msg"] == "visible"


def test_setup_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    setup_logging()
    setup_logging()
    logging.getLogger("kegg_mcp_server").info("hi")
    # Two setup calls should not duplicate handlers
    assert len(buf.getvalue().splitlines()) == 1


def test_exception_serialized_without_traceback_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.delenv("KEGG_MCP_LOG_TRACEBACKS", raising=False)
    setup_logging()
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("kegg_mcp_server").exception("caught")
    payload = json.loads(buf.getvalue().splitlines()[-1])
    assert payload["exc_type"] == "ValueError"
    assert payload["exc_msg"] == "boom"
    assert "exc" not in payload


def test_exception_serialized_with_full_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setenv("KEGG_MCP_LOG_TRACEBACKS", "1")
    # Need to reimport to pick up env change
    import kegg_mcp_server.logging as log_mod

    monkeypatch.setattr(log_mod, "_LOG_TRACEBACKS", True)
    setup_logging()
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("kegg_mcp_server").exception("caught")
    payload = json.loads(buf.getvalue().splitlines()[-1])
    assert "exc" in payload
    assert "ValueError" in payload["exc"]

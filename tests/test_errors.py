"""Tests for the kegg_tool decorator and ErrorResult shape."""

from __future__ import annotations

import pytest

from kegg_mcp_server.errors import KEGGAPIError
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.tools._common import kegg_tool


async def test_kegg_tool_passes_through_success() -> None:
    @kegg_tool
    async def ok() -> str:
        return "fine"

    assert await ok() == "fine"


async def test_kegg_tool_converts_retryable_error_to_error_result() -> None:
    @kegg_tool
    async def fail() -> str:
        raise KEGGAPIError("boom", status=503, path="/get/x", retryable=True)

    result = await fail()
    assert isinstance(result, ErrorResult)
    assert result.status == 503
    assert result.path == "/get/x"
    assert result.retryable is True
    assert "try again" in (result.hint or "").lower()


async def test_kegg_tool_converts_non_retryable_error_to_error_result() -> None:
    @kegg_tool
    async def fail() -> str:
        raise KEGGAPIError("nope", status=400, path="/get/x", retryable=False)

    result = await fail()
    assert isinstance(result, ErrorResult)
    assert result.retryable is False
    assert result.status == 400
    assert "check the identifier" in (result.hint or "").lower()


async def test_kegg_tool_does_not_swallow_other_exceptions() -> None:
    @kegg_tool
    async def fail() -> str:
        raise ValueError("something else")

    with pytest.raises(ValueError, match="something else"):
        await fail()


def test_error_result_has_stable_code_default() -> None:
    err = ErrorResult(error="x")
    assert err.code == "kegg_api_error"
    assert err.retryable is False

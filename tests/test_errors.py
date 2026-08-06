"""Tests for the kegg_tool decorator and ErrorResult shape."""

from __future__ import annotations

from pydantic import BaseModel

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


async def test_kegg_tool_converts_value_error_to_error_result() -> None:
    @kegg_tool
    async def fail() -> str:
        raise ValueError("something else")

    result = await fail()
    assert isinstance(result, ErrorResult)
    assert result.code == "validation_error"
    assert "something else" in result.error
    assert result.retryable is False


async def test_kegg_tool_reports_a_model_build_failure_as_a_parse_error() -> None:
    """A response model that won't build is OUR bug, not the caller's input.

    Pydantic v2's ``ValidationError`` subclasses ``ValueError``, so before the
    branches were split this returned ``code="validation_error"`` with the hint
    "Check the identifier format and try again" — blaming the identifier for a
    server-side parse defect. ``get_brite_info`` failed exactly this way on every
    valid BRITE id, which is why the report read as "the identifier is wrong".
    """

    class Strict(BaseModel):
        entry: str

    @kegg_tool
    async def fail() -> Strict:
        return Strict()  # missing required field → ValidationError

    result = await fail()
    assert isinstance(result, ErrorResult)
    assert result.code == "parse_error"
    assert result.retryable is False
    assert "fail" in result.error
    hint = (result.hint or "").lower()
    assert "not in the request" in hint
    assert "check the identifier format" not in hint


async def test_kegg_tool_still_maps_plain_value_error_to_validation_error() -> None:
    """The ordering guard: ``ValueError`` must keep meaning 'bad input'.

    ``validators.py`` raises plain ``ValueError`` for malformed identifiers, and
    D4's conv-pair validator relies on that mapping.
    """

    @kegg_tool
    async def fail() -> str:
        raise ValueError("Invalid pathway ID: 'xyz'")

    result = await fail()
    assert result.code == "validation_error"
    assert "check the identifier format" in (result.hint or "").lower()


def test_error_result_has_stable_code_default() -> None:
    err = ErrorResult(error="x")
    assert err.code == "kegg_api_error"
    assert err.retryable is False

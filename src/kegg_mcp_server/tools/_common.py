"""Shared tool helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from mcp.types import ToolAnnotations

from kegg_mcp_server.errors import KEGGAPIError
from kegg_mcp_server.models.common import SearchResult
from kegg_mcp_server.models.errors import ErrorResult

# Every KEGG tool is a pure read against the public KEGG REST API.
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

# Hard cap so a pathological max_results value can't dump the whole KEGG DB
# into a single tool response.
MAX_ENTRIES_CAP = 100


def build_search_result(
    query: str,
    database: str,
    all_results: dict[str, str],
    max_results: int,
) -> SearchResult:
    """Apply bounds to `max_results`, truncate, and report whether results were cut."""
    bounded = max(1, min(max_results, MAX_ENTRIES_CAP))
    limited = dict(list(all_results.items())[:bounded])
    return SearchResult(
        query=query,
        database=database,
        total_found=len(all_results),
        returned_count=len(limited),
        results=limited,
        truncated=len(all_results) > len(limited),
    )


P = ParamSpec("P")
R = TypeVar("R")


def kegg_tool(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R | ErrorResult]]:
    """Convert KEGGAPIError into an ErrorResult return value.

    KEGG 404 responses are handled at the HTTP layer by returning an empty
    string, so tools produce their normal empty result (e.g. a SearchResult
    with total_found=0). This decorator only catches genuine API failures
    (5xx, timeouts, network errors).
    """

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | ErrorResult:
        try:
            return await fn(*args, **kwargs)
        except KEGGAPIError as exc:
            return ErrorResult(
                error=str(exc),
                retryable=exc.retryable,
                status=exc.status,
                path=exc.path,
                hint=(
                    "KEGG REST API is rate-limited or temporarily unavailable; "
                    "try again shortly."
                    if exc.retryable
                    else "KEGG REST API rejected the request; check the identifier "
                    "or database name."
                ),
            )

    return wrapper

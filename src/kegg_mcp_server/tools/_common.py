"""Shared tool helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from mcp.types import ToolAnnotations
from pydantic import ValidationError

from kegg_mcp_server.errors import KEGGAPIError
from kegg_mcp_server.models.common import SearchResult
from kegg_mcp_server.models.errors import ErrorResult

# Every KEGG tool is a pure read against the public KEGG REST API.
# Field names are snake_case under mcp>=2 (the wire JSON stays camelCase via
# aliases). camelCase kwargs still construct, but reading `.readOnlyHint` back
# raises AttributeError, so keep both sides on the new spelling.
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    idempotent_hint=True,
    destructive_hint=False,
    # True: these hit a live external API, so results can change under us.
    open_world_hint=True,
)

# Hard cap so a pathological max_results value can't dump the whole KEGG DB
# into a single tool response.
MAX_ENTRIES_CAP = 100


def not_found_result(
    entity_type: str, identifier: str, *, path_identifier: str | None = None
) -> ErrorResult:
    """Build the stable result returned when a point lookup has no KEGG entry."""
    return ErrorResult(
        error=f"KEGG {entity_type} not found: {identifier}",
        code="not_found",
        retryable=False,
        status=404,
        path=f"/get/{path_identifier or identifier}",
        hint="Check that the identifier exists in KEGG and belongs to the expected database.",
    )


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
    string. Point-lookup tools convert that value to a typed not-found result,
    while searches produce their normal empty result. This decorator catches
    genuine API failures (5xx, timeouts, network errors) and invalid inputs.

    ``ValidationError`` is caught FIRST, and the order is load-bearing: Pydantic
    v2's ``ValidationError`` subclasses ``ValueError``, so a response model that
    fails to build — a parser producing the wrong keys, i.e. a bug in *this*
    server — used to be reported as ``validation_error`` with the hint "Check the
    identifier format and try again", blaming the caller's input for a defect it
    had nothing to do with. ``get_brite_info`` failed exactly this way on every
    valid BRITE id. ``ValueError`` keeps meaning "bad input" (that is the
    contract the ``validators`` module raises against).
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
        except ValidationError as exc:
            # Must precede the ValueError branch — see the docstring.
            return ErrorResult(
                error=f"Failed to build the response for {fn.__name__}: {exc.error_count()} "
                f"field error(s) — {exc.errors()[0].get('msg', 'invalid')}",
                code="parse_error",
                retryable=False,
                hint=(
                    "The identifier was accepted but this server could not parse "
                    "KEGG's response into the expected shape. This is a bug in the "
                    f"{fn.__name__} tool, not in the request."
                ),
            )
        except ValueError as exc:
            return ErrorResult(
                error=str(exc),
                code="validation_error",
                retryable=False,
                hint="Check the identifier format and try again.",
            )

    return wrapper

"""Shared tool helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, NoReturn, ParamSpec, TypeVar

import defusedxml.ElementTree as ET
from mcp.server.mcpserver.exceptions import ToolError
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
) -> NoReturn:
    """Raise the stable not-found `ToolError` (`is_error=True`) for a point lookup."""
    raise ToolError(
        ErrorResult(
            error=f"KEGG {entity_type} not found: {identifier}",
            code="not_found",
            retryable=False,
            status=404,
            path=f"/get/{path_identifier or identifier}",
            hint="Check that the identifier exists in KEGG and belongs to the expected database.",
        ).model_dump_json()
    )


def cap_mapping(
    items: dict[str, Any], max_results: int = MAX_ENTRIES_CAP
) -> tuple[dict[str, Any], int, bool]:
    """Bound a mapping to `max_results` (≤ MAX_ENTRIES_CAP); returns (limited, total, truncated)."""
    bounded = max(1, min(max_results, MAX_ENTRIES_CAP))
    limited = dict(list(items.items())[:bounded])
    return limited, len(items), len(items) > len(limited)


def cap_list(items: list[Any], max_results: int = MAX_ENTRIES_CAP) -> tuple[list[Any], int, bool]:
    """List counterpart of `cap_mapping`, for pair/row-shaped outputs."""
    bounded = max(1, min(max_results, MAX_ENTRIES_CAP))
    limited = items[:bounded]
    return limited, len(items), len(items) > len(limited)


def build_search_result(
    query: str,
    database: str,
    all_results: dict[str, str],
    max_results: int,
) -> SearchResult:
    """Apply bounds to `max_results`, truncate, and report whether results were cut."""
    limited, total, truncated = cap_mapping(all_results, max_results)
    return SearchResult(
        query=query,
        database=database,
        total_found=total,
        returned_count=len(limited),
        results=limited,
        truncated=truncated,
    )


P = ParamSpec("P")
R = TypeVar("R")


def kegg_tool(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Convert known failures into a `ToolError` so the MCP call reports `is_error=True`.

    KEGG 404 responses are handled at the HTTP layer by returning an empty
    string. Point-lookup tools convert that value to a typed not-found result,
    while searches produce their normal empty result. This decorator catches
    genuine API failures (5xx, timeouts, network errors), invalid inputs, and
    this server's own parse bugs — raising `ToolError` with the `ErrorResult`
    JSON as its message, which the SDK turns into `CallToolResult(is_error=True)`
    with that JSON as the text content.

    ``ValidationError`` is caught FIRST, and the order is load-bearing: Pydantic
    v2's ``ValidationError`` subclasses ``ValueError``, so a response model that
    fails to build — a parser producing the wrong keys, i.e. a bug in *this*
    server — used to be reported as ``validation_error`` with the hint "Check the
    identifier format and try again", blaming the caller's input for a defect it
    had nothing to do with. ``get_brite_info`` failed exactly this way on every
    valid BRITE id. ``ValueError`` keeps meaning "bad input" (that is the
    contract the ``validators`` module raises against) — a server-side parse bug
    that also happens to raise ``ValueError`` (e.g. a malformed KGML attribute)
    is reported as `ET.ParseError` by its caller instead, so it lands here, not
    in the plain-``ValueError`` branch.
    """

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except KEGGAPIError as exc:
            raise ToolError(
                ErrorResult(
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
                ).model_dump_json()
            ) from exc
        except ValidationError as exc:
            # Must precede the ValueError branch — see the docstring.
            raise ToolError(
                ErrorResult(
                    error=f"Failed to build the response for {fn.__name__}: "
                    f"{exc.error_count()} field error(s) — "
                    f"{exc.errors()[0].get('msg', 'invalid')}",
                    code="parse_error",
                    retryable=False,
                    hint=(
                        "The identifier was accepted but this server could not parse "
                        "KEGG's response into the expected shape. This is a bug in the "
                        f"{fn.__name__} tool, not in the request."
                    ),
                ).model_dump_json()
            ) from exc
        except ET.ParseError as exc:
            # Malformed KGML (bad XML, or a numeric attribute that failed to
            # parse) is this server's problem, not the caller's identifier.
            raise ToolError(
                ErrorResult(
                    error=f"Failed to parse KGML in {fn.__name__}: {exc}",
                    code="parse_error",
                    retryable=False,
                    hint="KEGG returned KGML this server could not parse. This is a "
                    f"bug in the {fn.__name__} tool, not in the request.",
                ).model_dump_json()
            ) from exc
        except ValueError as exc:
            raise ToolError(
                ErrorResult(
                    error=str(exc),
                    code="validation_error",
                    retryable=False,
                    hint="Check the identifier format and try again.",
                ).model_dump_json()
            ) from exc

    return wrapper

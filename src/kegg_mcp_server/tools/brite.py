from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.brite import BriteInfo
from kegg_mcp_server.models.common import EntrySummary, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list, summarize_flat_entry
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool
from kegg_mcp_server.validators import validate_brite_id, validate_query

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_brite(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG BRITE functional hierarchy databases.

        Args:
            query: Hierarchy name (e.g. 'KEGG pathway', 'transporter', 'ribosome').
            max_results: Maximum number of results to return (capped at 100).
        """
        query = validate_query(query)
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("brite", query))
        return build_search_result(query, "brite", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_brite_info(
        brite_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> BriteInfo | EntrySummary | ErrorResult:
        """Get information and hierarchy content for a KEGG BRITE entry.

        Args:
            brite_id: KEGG BRITE hierarchy ID (e.g. 'br:ko00001' for KO hierarchy).
            detail_level: 'summary' (default, compact — omits raw_content) or 'full'
                (includes the complete raw hierarchy text, which can be very large).
        """
        brite_id = validate_brite_id(brite_id)
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(brite_id)
        parsed = parse_flat_entry(raw)
        if detail_level != "full":
            return EntrySummary(**summarize_flat_entry(parsed))
        return BriteInfo(
            entry=parsed.get("entry", brite_id),
            name=parsed.get("name", ""),
            definition=parsed.get("definition"),
            dblinks=parsed.get("dblinks"),
            raw_content=raw,
        )

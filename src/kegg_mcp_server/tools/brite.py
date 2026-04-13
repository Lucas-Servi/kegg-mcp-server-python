from __future__ import annotations
from typing import TYPE_CHECKING
from mcp.server.fastmcp import Context
from kegg_mcp_server.models.brite import BriteInfo
from kegg_mcp_server.models.common import SearchResult
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_brite(query: str, max_results: int = 50, ctx: Context = None) -> SearchResult:
        """Search KEGG BRITE functional hierarchy databases.

        Args:
            query: Hierarchy name (e.g. 'KEGG pathway', 'transporter', 'ribosome').
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("brite", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(query=query, database="brite", total_found=len(results), returned_count=len(limited), results=limited)

    @mcp.tool()
    async def get_brite_info(brite_id: str, ctx: Context = None) -> BriteInfo:
        """Get information and hierarchy content for a KEGG BRITE entry.

        Args:
            brite_id: KEGG BRITE hierarchy ID (e.g. 'br:ko00001' for KO hierarchy).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.get(brite_id)
        p = parse_flat_entry(raw)
        return BriteInfo(
            entry=p.get("entry", brite_id), name=p.get("name", ""),
            definition=p.get("definition"), dblinks=p.get("dblinks"), raw_content=raw,
        )

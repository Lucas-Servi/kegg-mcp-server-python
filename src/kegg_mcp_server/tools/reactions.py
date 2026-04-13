from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import Reference, SearchResult
from kegg_mcp_server.models.reaction import ReactionInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> ReactionInfo:
    return ReactionInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        definition=p.get("definition"),
        equation=p.get("equation"),
        enzyme=p.get("enzyme"),
        pathway=p.get("pathway"),
        module=p.get("module"),
        orthology=p.get("orthology"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def search_reactions(
        query: str, max_results: int = 50, ctx: Context = None
    ) -> SearchResult:
        """Search KEGG reactions by keyword.

        Args:
            query: Search term (reaction name or description).
            max_results: Maximum number of results to return.
        """
        kegg = ctx.request_context.lifespan_context.kegg
        raw = await kegg.find("reaction", query)
        results = parse_tab_list(raw)
        limited = dict(list(results.items())[:max_results])
        return SearchResult(
            query=query,
            database="reaction",
            total_found=len(results),
            returned_count=len(limited),
            results=limited,
        )

    @mcp.tool()
    async def get_reaction_info(reaction_id: str, ctx: Context = None) -> ReactionInfo:
        """Get detailed information for a KEGG reaction.

        Args:
            reaction_id: KEGG reaction ID (e.g. 'R00756' for glucose phosphorylation).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        return _build(parse_flat_entry(await kegg.get(reaction_id)))

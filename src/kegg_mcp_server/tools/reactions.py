from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.reaction import ReactionInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list, summarize_flat_entry
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

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

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_reactions(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG reactions by keyword.

        Args:
            query: Search term (reaction name or description).
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("reaction", query))
        return build_search_result(query, "reaction", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_reaction_info(
        reaction_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> ReactionInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG reaction.

        Args:
            reaction_id: KEGG reaction ID (e.g. 'R00756' for glucose phosphorylation).
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(reaction_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))

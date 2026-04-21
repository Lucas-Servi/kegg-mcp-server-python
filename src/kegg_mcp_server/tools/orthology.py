from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.models.orthology import KOInfo
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list, summarize_flat_entry
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> KOInfo:
    return KOInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        definition=p.get("definition"),
        pathway=p.get("pathway"),
        module=p.get("module"),
        disease=p.get("disease"),
        network=p.get("network"),
        brite=p.get("brite"),
        genes=p.get("gene"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_ko_entries(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG Orthology (KO) entries by keyword.

        Args:
            query: Gene function (e.g. 'hexokinase', 'ribosomal protein', 'cytochrome').
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("ko", query))
        return build_search_result(query, "ko", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_ko_info(
        ko_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> KOInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG Orthology (KO) entry.

        Args:
            ko_id: KEGG KO identifier (e.g. 'K00844' for hexokinase).
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        parsed = parse_flat_entry(await kegg.get(ko_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))

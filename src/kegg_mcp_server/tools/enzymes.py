from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import Context

from kegg_mcp_server.models.common import EntrySummary, Reference, SearchResult
from kegg_mcp_server.models.enzyme import EnzymeInfo
from kegg_mcp_server.models.errors import ErrorResult
from kegg_mcp_server.parsers import parse_flat_entry, parse_tab_list, summarize_flat_entry
from kegg_mcp_server.tools._common import READ_ONLY, build_search_result, kegg_tool

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _build(p: dict) -> EnzymeInfo:
    return EnzymeInfo(
        entry=p.get("entry", ""),
        name=p.get("name", ""),
        cls=p.get("cls"),
        sysname=p.get("sysname"),
        reaction=p.get("reaction"),
        substrate=p.get("substrate"),
        product=p.get("product"),
        comment=p.get("comment"),
        pathway=p.get("pathway"),
        orthology=p.get("orthology"),
        genes=p.get("gene"),
        dblinks=p.get("dblinks"),
        references=[Reference(**r) for r in p.get("references", [])],
    )


def register(mcp: FastMCP) -> None:

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def search_enzymes(
        query: str, max_results: int = 25, ctx: Context = None
    ) -> SearchResult | ErrorResult:
        """Search KEGG enzymes by EC number or name.

        Args:
            query: EC number (e.g. '1.1.1.1') or enzyme name (e.g. 'kinase', 'oxidase').
            max_results: Maximum number of results to return (capped at 100).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        results = parse_tab_list(await kegg.find("enzyme", query))
        return build_search_result(query, "enzyme", results, max_results)

    @mcp.tool(annotations=READ_ONLY)
    @kegg_tool
    async def get_enzyme_info(
        enzyme_id: str,
        detail_level: Literal["summary", "full"] = "summary",
        ctx: Context = None,
    ) -> EnzymeInfo | EntrySummary | ErrorResult:
        """Get detailed information for a KEGG enzyme (EC number).

        Args:
            enzyme_id: EC number (e.g. '1.1.1.1') or prefixed ID (e.g. 'ec:1.1.1.1').
            detail_level: 'summary' (default, compact) or 'full' (complete flat-file parse).
        """
        kegg = ctx.request_context.lifespan_context.kegg
        entry_id = enzyme_id if enzyme_id.startswith("ec:") else f"ec:{enzyme_id}"
        parsed = parse_flat_entry(await kegg.get(entry_id))
        if detail_level == "full":
            return _build(parsed)
        return EntrySummary(**summarize_flat_entry(parsed))
